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
        """Initialize policy engine with rules from YAML.
        
        Args:
            policy_file: Path to policy_rules.yaml. Uses default if not provided.
        """
        self.policy_file = Path(policy_file) if policy_file else self.DEFAULT_POLICY_FILE
        self.rules: PolicyRules = self._load_policies()
        self._consecutive_high_risk_count: Dict[str, int] = {}  # user_id -> count
        self._action_counts: Dict[str, Dict[str, int]] = {}  # user_id -> {date -> count}
    
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
        self,
        proposed_action: str,
        confidence_score: float,
        risk_score: float,
        disagreement_score: float,
        user_id: str,
        session_id: str,
        agent_outputs: Optional[Dict[str, Any]] = None,
    ) -> PolicyCheckResult:
        """Evaluate a proposed action against all policy rules.
        
        This is the main entry point. Checks ALL rules and returns
        a single verdict: approve, veto, or escalate.
        
        Args:
            proposed_action: The action AI wants to take
            confidence_score: AI confidence (0-1)
            risk_score: Aggregated risk score (0-1)
            disagreement_score: Agent disagreement (0-1)
            user_id: Target user ID
            session_id: Session ID
            agent_outputs: Optional agent output summary
            
        Returns:
            PolicyCheckResult with decision and any violations
        """
        violations: List[PolicyViolation] = []
        
        # Check 1: Is the action allowed at all?
        action_violations = self._check_action_allowed(proposed_action)
        violations.extend(action_violations)
        
        # Check 2: Confidence threshold
        confidence_violations = self._check_confidence(confidence_score, proposed_action)
        violations.extend(confidence_violations)
        
        # Check 3: Disagreement threshold
        disagreement_violations = self._check_disagreement(disagreement_score)
        violations.extend(disagreement_violations)
        
        # Check 4: Critical risk check
        risk_violations = self._check_critical_risk(risk_score)
        violations.extend(risk_violations)
        
        # Check 5: Rate limits
        rate_violations = self._check_rate_limits(user_id, proposed_action)
        violations.extend(rate_violations)
        
        # Check 6: Consecutive high risk
        consecutive_violations = self._check_consecutive_high_risk(user_id, risk_score)
        violations.extend(consecutive_violations)
        
        # Determine final decision based on violations
        decision, veto_reason, escalation_reason = self._determine_decision(violations)
        
        # Update tracking (only if action proceeds)
        if decision == PolicyDecision.APPROVE:
            self._track_action(user_id, proposed_action)
        
        return PolicyCheckResult(
            decision=decision,
            policy_version=self.policy_version,
            violations=violations,
            approved_action=proposed_action if decision == PolicyDecision.APPROVE else None,
            veto_reason=veto_reason,
            escalation_reason=escalation_reason,
            metadata={
                "session_id": session_id,
                "user_id": user_id,
                "confidence_score": confidence_score,
                "risk_score": risk_score,
                "disagreement_score": disagreement_score,
                "proposed_action": proposed_action,
            }
        )
    
    def _check_action_allowed(self, action: str) -> List[PolicyViolation]:
        """Check if action is in the allowed list.
        
        Args:
            action: Proposed action
            
        Returns:
            List of violations (empty if action is allowed)
        """
        violations = []
        
        # Check if action is human-only
        if action in self.rules.actions.human_only_actions:
            violations.append(PolicyViolation(
                violation_type=PolicyViolationType.HUMAN_ONLY_ACTION,
                policy_rule="actions.human_only_actions",
                actual_value=action,
                threshold_value=self.rules.actions.human_only_actions,
                severity="hard_stop",
                message=f"Action '{action}' requires human approval. AI cannot execute."
            ))
            return violations
        
        # Check if action is in allowed list
        if action not in self.rules.actions.allowed_actions:
            violations.append(PolicyViolation(
                violation_type=PolicyViolationType.ACTION_NOT_ALLOWED,
                policy_rule="actions.allowed_actions",
                actual_value=action,
                threshold_value=self.rules.actions.allowed_actions,
                severity="hard_stop",
                message=f"Action '{action}' is not in the allowed actions list."
            ))
        
        # Special check for permanent block
        if "PERMANENT" in action.upper() and not self.rules.actions.permanent_block_allowed:
            violations.append(PolicyViolation(
                violation_type=PolicyViolationType.ACTION_NOT_ALLOWED,
                policy_rule="actions.permanent_block_allowed",
                actual_value=action,
                threshold_value=False,
                severity="hard_stop",
                message="Permanent blocks are not allowed. AI cannot permanently block accounts."
            ))
        
        return violations
    
    def _check_confidence(self, confidence: float, action: str) -> List[PolicyViolation]:
        """Check confidence thresholds.
        
        Args:
            confidence: Confidence score (0-1)
            action: Proposed action
            
        Returns:
            List of violations
        """
        violations = []
        
        # Cap confidence at maximum
        if confidence > self.rules.confidence.max_confidence_cap:
            confidence = self.rules.confidence.max_confidence_cap
        
        # Check if confidence is too low to allow autonomous action
        if confidence < self.rules.confidence.min_to_allow:
            # Any confidence below min_to_allow requires escalation
            if action != "ESCALATE":  # Don't block escalations
                # All low confidence violations are hard stops requiring escalation
                if confidence < self.rules.confidence.min_to_escalate:
                    message = (f"Confidence {confidence:.2f} is critically low "
                              f"(below escalation threshold {self.rules.confidence.min_to_escalate}). "
                              f"Immediate human review required.")
                else:
                    message = (f"Confidence {confidence:.2f} is below autonomous action threshold "
                              f"{self.rules.confidence.min_to_allow}. Human review required.")
                
                violations.append(PolicyViolation(
                    violation_type=PolicyViolationType.CONFIDENCE_TOO_LOW,
                    policy_rule="confidence.min_to_allow",
                    actual_value=confidence,
                    threshold_value=self.rules.confidence.min_to_allow,
                    severity="hard_stop",  # Always hard stop below min_to_allow
                    message=message
                ))
        
        return violations
    
    def _check_disagreement(self, disagreement: float) -> List[PolicyViolation]:
        """Check agent disagreement threshold.
        
        Args:
            disagreement: Disagreement score (0-1)
            
        Returns:
            List of violations
        """
        violations = []
        
        if disagreement > self.rules.escalation.disagreement_threshold:
            violations.append(PolicyViolation(
                violation_type=PolicyViolationType.DISAGREEMENT_TOO_HIGH,
                policy_rule="escalation.disagreement_threshold",
                actual_value=disagreement,
                threshold_value=self.rules.escalation.disagreement_threshold,
                severity="hard_stop",
                message=f"Agent disagreement {disagreement:.2f} exceeds threshold "
                        f"{self.rules.escalation.disagreement_threshold}. Escalation required."
            ))
        
        return violations
    
    def _check_critical_risk(self, risk_score: float) -> List[PolicyViolation]:
        """Check for critical risk threshold.
        
        Args:
            risk_score: Risk score (0-1)
            
        Returns:
            List of violations
        """
        violations = []
        
        if risk_score >= self.rules.risk_thresholds.critical_risk_threshold:
            violations.append(PolicyViolation(
                violation_type=PolicyViolationType.CRITICAL_RISK,
                policy_rule="risk_thresholds.critical_risk_threshold",
                actual_value=risk_score,
                threshold_value=self.rules.risk_thresholds.critical_risk_threshold,
                severity="hard_stop",
                message=f"Risk score {risk_score:.2f} is at critical level. "
                        f"Mandatory escalation regardless of confidence."
            ))
        
        return violations
    
    def _check_rate_limits(self, user_id: str, action: str) -> List[PolicyViolation]:
        """Check rate limits for user.
        
        Args:
            user_id: User ID
            action: Proposed action
            
        Returns:
            List of violations
        """
        violations = []
        
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        if user_id not in self._action_counts:
            self._action_counts[user_id] = {}
        
        if today not in self._action_counts[user_id]:
            self._action_counts[user_id][today] = 0
        
        current_count = self._action_counts[user_id][today]
        max_allowed = self.rules.actions.max_actions_per_user_per_day
        
        if current_count >= max_allowed:
            violations.append(PolicyViolation(
                violation_type=PolicyViolationType.RATE_LIMIT_EXCEEDED,
                policy_rule="actions.max_actions_per_user_per_day",
                actual_value=current_count,
                threshold_value=max_allowed,
                severity="hard_stop",
                message=f"User {user_id} has reached daily action limit ({max_allowed}). "
                        f"No more autonomous actions allowed today."
            ))
        
        return violations
    
    def _check_consecutive_high_risk(self, user_id: str, risk_score: float) -> List[PolicyViolation]:
        """Check consecutive high-risk decisions.
        
        Args:
            user_id: User ID
            risk_score: Current risk score
            
        Returns:
            List of violations
        """
        violations = []
        
        # Track high-risk decisions
        if risk_score >= self.rules.risk_thresholds.high_risk_min:
            if user_id not in self._consecutive_high_risk_count:
                self._consecutive_high_risk_count[user_id] = 0
            self._consecutive_high_risk_count[user_id] += 1
        else:
            # Reset on non-high-risk
            self._consecutive_high_risk_count[user_id] = 0
        
        count = self._consecutive_high_risk_count.get(user_id, 0)
        limit = self.rules.escalation.consecutive_high_risk_limit
        
        if count >= limit:
            violations.append(PolicyViolation(
                violation_type=PolicyViolationType.CONSECUTIVE_HIGH_RISK,
                policy_rule="escalation.consecutive_high_risk_limit",
                actual_value=count,
                threshold_value=limit,
                severity="hard_stop",
                message=f"User {user_id} has {count} consecutive high-risk decisions. "
                        f"Forced escalation after {limit}."
            ))
        
        return violations
    
    def _determine_decision(
        self,
        violations: List[PolicyViolation]
    ) -> tuple[PolicyDecision, Optional[str], Optional[str]]:
        """Determine final decision based on violations.
        
        Args:
            violations: List of policy violations
            
        Returns:
            Tuple of (decision, veto_reason, escalation_reason)
        """
        if not violations:
            return PolicyDecision.APPROVE, None, None
        
        # Check for hard stops (vetoes)
        hard_stops = [v for v in violations if v.severity == "hard_stop"]
        
        if hard_stops:
            # Determine if this should be veto or escalate
            # Human-only actions and rate limits are vetoes
            # Low confidence and disagreement are escalations
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
            has_escalation = any(v.violation_type in escalation_types for v in hard_stops)
            
            if has_veto:
                veto_reasons = [v.message for v in hard_stops if v.violation_type in veto_types]
                return PolicyDecision.VETO, "; ".join(veto_reasons), None
            
            if has_escalation:
                escalation_reasons = [v.message for v in hard_stops if v.violation_type in escalation_types]
                return PolicyDecision.ESCALATE, None, "; ".join(escalation_reasons)
        
        # Warnings only - still approve but with notes
        return PolicyDecision.APPROVE, None, None
    
    def _track_action(self, user_id: str, action: str) -> None:
        """Track action for rate limiting.
        
        Args:
            user_id: User ID
            action: Action taken
        """
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        if user_id not in self._action_counts:
            self._action_counts[user_id] = {}
        
        if today not in self._action_counts[user_id]:
            self._action_counts[user_id][today] = 0
        
        self._action_counts[user_id][today] += 1
    
    def enforce(
        self,
        proposed_action: str,
        confidence_score: float,
        risk_score: float,
        disagreement_score: float,
        user_id: str,
        session_id: str,
        agent_outputs: Optional[Dict[str, Any]] = None,
        raise_on_violation: bool = True,
    ) -> PolicyCheckResult:
        """Enforce policies with optional exception on violation.
        
        Args:
            proposed_action: The action AI wants to take
            confidence_score: AI confidence (0-1)
            risk_score: Aggregated risk score (0-1)
            disagreement_score: Agent disagreement (0-1)
            user_id: Target user ID
            session_id: Session ID
            agent_outputs: Optional agent output summary
            raise_on_violation: If True, raise exception on violation
            
        Returns:
            PolicyCheckResult
            
        Raises:
            PolicyViolationError: If raise_on_violation and policy violated
        """
        result = self.evaluate(
            proposed_action=proposed_action,
            confidence_score=confidence_score,
            risk_score=risk_score,
            disagreement_score=disagreement_score,
            user_id=user_id,
            session_id=session_id,
            agent_outputs=agent_outputs,
        )
        
        if raise_on_violation and result.is_vetoed:
            raise PolicyViolationError(
                violations=result.violations,
                message=result.veto_reason or "Policy violation"
            )
        
        return result
    
    def get_action_for_risk(self, risk_score: float) -> str:
        """Get recommended action based on risk score.
        
        Args:
            risk_score: Risk score (0-1)
            
        Returns:
            Recommended action string
        """
        if risk_score <= self.rules.risk_thresholds.low_risk_max:
            return "ALLOW"
        elif risk_score <= self.rules.risk_thresholds.medium_risk_max:
            return "CHALLENGE"
        elif risk_score >= self.rules.risk_thresholds.critical_risk_threshold:
            return "ESCALATE"
        else:
            return "BLOCK_TEMPORARY"
    
    def reset_tracking(self, user_id: Optional[str] = None) -> None:
        """Reset rate limit and consecutive risk tracking.
        
        Args:
            user_id: If provided, reset only for this user. Otherwise reset all.
        """
        if user_id:
            self._action_counts.pop(user_id, None)
            self._consecutive_high_risk_count.pop(user_id, None)
        else:
            self._action_counts.clear()
            self._consecutive_high_risk_count.clear()

