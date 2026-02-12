"""Policy Engine - Evaluates and enforces runtime governance constraints."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from aegis_ai.governance.schemas import (
    PolicyRules,
    PolicyCheckResult,
    PolicyDecision,
    PolicyViolation,
    PolicyViolationType,
)


class PolicyViolationError(Exception):
    """Raised when a policy violation produces a hard stop."""
    
    def __init__(self, violations: List[PolicyViolation], message: str = "Policy violation"):
        self.violations = violations
        self.message = message
        super().__init__(self.message)


class PolicyEngine:
    """Evaluates policies before actions execute.
    """
    
    # Default policy file path
    DEFAULT_POLICY_FILE = Path(__file__).parent.parent.parent.parent.parent / "config" / "policy_rules.yaml"
    
    def __init__(self, policy_file: Optional[str] = None):
        self.policy_file = Path(policy_file) if policy_file else self.DEFAULT_POLICY_FILE
        self.rules: PolicyRules = self._load_policies()
        self._consecutive_high_risk_count: Dict[str, int] = {}
        self._action_counts: Dict[str, Dict[str, int]] = {}
    
    def _load_policies(self) -> PolicyRules:
        """Load and validate policies from YAML file."""
        if not self.policy_file.exists():
            raise FileNotFoundError(f"Policy file not found: {self.policy_file}")
        
        with open(self.policy_file, "r") as f:
            raw_config = yaml.safe_load(f)
        
        # Validate and parse into Pydantic model
        return PolicyRules.model_validate(raw_config)
    
    def reload_policies(self) -> None:
        self.rules = self._load_policies()
    
    @property
    def policy_version(self) -> str:
        """Get current policy version."""
        return self.rules.metadata.version
    
    def evaluate(
        self, proposed_action: str, confidence_score: float, risk_score: float,
        disagreement_score: float, user_id: str, session_id: str,
        agent_outputs: Optional[Dict[str, Any]] = None,
    ) -> PolicyCheckResult:
        """Evaluate action against all policy rules."""
        violations = []
        violations.extend(self._check_action_allowed(proposed_action))
        violations.extend(self._check_confidence(confidence_score, proposed_action))
        violations.extend(self._check_disagreement(disagreement_score))
        violations.extend(self._check_critical_risk(risk_score))
        violations.extend(self._check_rate_limits(user_id, proposed_action))
        violations.extend(self._check_consecutive_high_risk(user_id, risk_score))
        
        decision, veto_reason, escalation_reason = self._determine_decision(violations)
        if decision == PolicyDecision.APPROVE:
            self._track_action(user_id, proposed_action)
        
        return PolicyCheckResult(
            decision=decision, policy_version=self.policy_version, violations=violations,
            approved_action=proposed_action if decision == PolicyDecision.APPROVE else None,
            veto_reason=veto_reason, escalation_reason=escalation_reason,
            metadata={
                "session_id": session_id, "user_id": user_id,
                "confidence_score": confidence_score, "risk_score": risk_score,
                "disagreement_score": disagreement_score, "proposed_action": proposed_action,
            }
        )
    
    def _check_action_allowed(self, action: str) -> List[PolicyViolation]:
        """Check if action is allowed."""
        violations = []
        if action in self.rules.actions.human_only_actions:
            violations.append(PolicyViolation(
                violation_type=PolicyViolationType.HUMAN_ONLY_ACTION,
                policy_rule="actions.human_only_actions",
                actual_value=action, threshold_value=self.rules.actions.human_only_actions,
                severity="hard_stop",
                message=f"Action '{action}' requires human approval."
            ))
            return violations
        
        if action not in self.rules.actions.allowed_actions:
            violations.append(PolicyViolation(
                violation_type=PolicyViolationType.ACTION_NOT_ALLOWED,
                policy_rule="actions.allowed_actions",
                actual_value=action, threshold_value=self.rules.actions.allowed_actions,
                severity="hard_stop",
                message=f"Action '{action}' is not allowed."
            ))
        
        if "PERMANENT" in action.upper() and not self.rules.actions.permanent_block_allowed:
            violations.append(PolicyViolation(
                violation_type=PolicyViolationType.ACTION_NOT_ALLOWED,
                policy_rule="actions.permanent_block_allowed",
                actual_value=action, threshold_value=False,
                severity="hard_stop",
                message="Permanent blocks are not allowed."
            ))
        
        return violations
    
    def _check_confidence(self, confidence: float, action: str) -> List[PolicyViolation]:
        """Check confidence thresholds."""
        violations = []
        confidence = min(confidence, self.rules.confidence.max_confidence_cap)
        
        if confidence < self.rules.confidence.min_to_allow and action != "ESCALATE":
            msg = (f"Confidence {confidence:.2f} below threshold "
                   f"{self.rules.confidence.min_to_allow}. Human review required.")
            violations.append(PolicyViolation(
                violation_type=PolicyViolationType.CONFIDENCE_TOO_LOW,
                policy_rule="confidence.min_to_allow",
                actual_value=confidence, threshold_value=self.rules.confidence.min_to_allow,
                severity="hard_stop", message=msg
            ))
        
        return violations
    
    def _check_disagreement(self, disagreement: float) -> List[PolicyViolation]:
        """Check agent disagreement threshold."""
        if disagreement > self.rules.escalation.disagreement_threshold:
            return [PolicyViolation(
                violation_type=PolicyViolationType.DISAGREEMENT_TOO_HIGH,
                policy_rule="escalation.disagreement_threshold",
                actual_value=disagreement, threshold_value=self.rules.escalation.disagreement_threshold,
                severity="hard_stop",
                message=f"Disagreement {disagreement:.2f} exceeds {self.rules.escalation.disagreement_threshold}."
            )]
        return []
    
    def _check_critical_risk(self, risk_score: float) -> List[PolicyViolation]:
        """Check for critical risk threshold."""
        if risk_score >= self.rules.risk_thresholds.critical_risk_threshold:
            return [PolicyViolation(
                violation_type=PolicyViolationType.CRITICAL_RISK,
                policy_rule="risk_thresholds.critical_risk_threshold",
                actual_value=risk_score, threshold_value=self.rules.risk_thresholds.critical_risk_threshold,
                severity="hard_stop",
                message=f"Risk {risk_score:.2f} is critical. Mandatory escalation."
            )]
        return []
    
    def _check_rate_limits(self, user_id: str, action: str) -> List[PolicyViolation]:
        """Check rate limits for user."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if user_id not in self._action_counts:
            self._action_counts[user_id] = {}
        if today not in self._action_counts[user_id]:
            self._action_counts[user_id][today] = 0
        
        current = self._action_counts[user_id][today]
        max_allowed = self.rules.actions.max_actions_per_user_per_day
        
        if current >= max_allowed:
            return [PolicyViolation(
                violation_type=PolicyViolationType.RATE_LIMIT_EXCEEDED,
                policy_rule="actions.max_actions_per_user_per_day",
                actual_value=current, threshold_value=max_allowed,
                severity="hard_stop",
                message=f"User reached daily limit ({max_allowed})."
            )]
        return []
    
    def _check_consecutive_high_risk(self, user_id: str, risk_score: float) -> List[PolicyViolation]:
        """Check consecutive high-risk decisions."""
        if risk_score >= self.rules.risk_thresholds.high_risk_min:
            self._consecutive_high_risk_count[user_id] = self._consecutive_high_risk_count.get(user_id, 0) + 1
        else:
            self._consecutive_high_risk_count[user_id] = 0
        
        count = self._consecutive_high_risk_count.get(user_id, 0)
        limit = self.rules.escalation.consecutive_high_risk_limit
        
        if count >= limit:
            return [PolicyViolation(
                violation_type=PolicyViolationType.CONSECUTIVE_HIGH_RISK,
                policy_rule="escalation.consecutive_high_risk_limit",
                actual_value=count, threshold_value=limit,
                severity="hard_stop",
                message=f"Consecutive high-risk limit reached ({count}/{limit})."
            )]
        return []
    
    def _determine_decision(
        self, violations: List[PolicyViolation]
    ) -> tuple[PolicyDecision, Optional[str], Optional[str]]:
        """Determine final decision based on violations."""
        if not violations:
            return PolicyDecision.APPROVE, None, None
        
        hard_stops = [v for v in violations if v.severity == "hard_stop"]
        if not hard_stops:
            return PolicyDecision.APPROVE, None, None
        
        veto_types = {
            PolicyViolationType.ACTION_NOT_ALLOWED,
            PolicyViolationType.HUMAN_ONLY_ACTION,
            PolicyViolationType.RATE_LIMIT_EXCEEDED,
        }
        escalation_types = {
            PolicyViolationType.CONFIDENCE_TOO_LOW,
            PolicyViolationType.DISAGREEMENT_TOO_HIGH,
            PolicyViolationType.CONSECUTIVE_HIGH_RISK,
            PolicyViolationType.CRITICAL_RISK,
        }
        
        has_veto = any(v.violation_type in veto_types for v in hard_stops)
        if has_veto:
            veto_msgs = [v.message for v in hard_stops if v.violation_type in veto_types]
            return PolicyDecision.VETO, "; ".join(veto_msgs), None
        
        has_escalation = any(v.violation_type in escalation_types for v in hard_stops)
        if has_escalation:
            esc_msgs = [v.message for v in hard_stops if v.violation_type in escalation_types]
            return PolicyDecision.ESCALATE, None, "; ".join(esc_msgs)
        
        return PolicyDecision.APPROVE, None, None
    
    def _track_action(self, user_id: str, action: str) -> None:
        """Track action for rate limiting."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if user_id not in self._action_counts:
            self._action_counts[user_id] = {}
        if today not in self._action_counts[user_id]:
            self._action_counts[user_id][today] = 0
        self._action_counts[user_id][today] += 1
    
    def enforce(
        self, proposed_action: str, confidence_score: float, risk_score: float,
        disagreement_score: float, user_id: str, session_id: str,
        agent_outputs: Optional[Dict[str, Any]] = None,
        raise_on_violation: bool = True,
    ) -> PolicyCheckResult:
        """Enforce policies with optional exception on violation."""
        result = self.evaluate(
            proposed_action=proposed_action, confidence_score=confidence_score,
            risk_score=risk_score, disagreement_score=disagreement_score,
            user_id=user_id, session_id=session_id, agent_outputs=agent_outputs,
        )
        
        if raise_on_violation and result.is_vetoed:
            raise PolicyViolationError(violations=result.violations, message=result.veto_reason or "Policy violation")
        
        return result
    
    def get_action_for_risk(self, risk_score: float) -> str:
        """Get recommended action based on risk score."""
        if risk_score <= self.rules.risk_thresholds.low_risk_max:
            return "ALLOW"
        elif risk_score <= self.rules.risk_thresholds.medium_risk_max:
            return "CHALLENGE"
        elif risk_score >= self.rules.risk_thresholds.critical_risk_threshold:
            return "ESCALATE"
        else:
            return "BLOCK_TEMPORARY"
    
    def reset_tracking(self, user_id: Optional[str] = None) -> None:
        """Reset rate limit and consecutive risk tracking."""
        if user_id:
            self._action_counts.pop(user_id, None)
            self._consecutive_high_risk_count.pop(user_id, None)
        else:
            self._action_counts.clear()
            self._consecutive_high_risk_count.clear()

