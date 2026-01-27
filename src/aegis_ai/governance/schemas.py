"""Governance schemas - type definitions for policy enforcement and audit.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field
from uuid import uuid4


class PolicyViolationType(str, Enum):
    """Types of policy violations."""
    CONFIDENCE_TOO_LOW = "confidence_too_low"
    ACTION_NOT_ALLOWED = "action_not_allowed"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    HUMAN_ONLY_ACTION = "human_only_action"
    DISAGREEMENT_TOO_HIGH = "disagreement_too_high"
    CONSECUTIVE_HIGH_RISK = "consecutive_high_risk"
    CRITICAL_RISK = "critical_risk"


class PolicyDecision(str, Enum):
    """Policy engine decision types."""
    APPROVE = "approve"
    VETO = "veto"
    ESCALATE = "escalate"


class OverrideType(str, Enum):
    """Human override types."""
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    MODIFY = "MODIFY"
    DEFER = "DEFER"


class AuditEventType(str, Enum):
    """Types of audit events."""
    DECISION = "decision"
    POLICY_CHECK = "policy_check"
    POLICY_VIOLATION = "policy_violation"
    HUMAN_OVERRIDE = "human_override"
    ESCALATION = "escalation"
    SYSTEM_EVENT = "system_event"


class PolicyViolation(BaseModel):
    """A single policy violation record.
    
    Immutable. Used for audit trail.
    """
    violation_id: str = Field(
        default_factory=lambda: f"vio_{uuid4().hex[:12]}",
        description="Unique violation identifier"
    )
    violation_type: PolicyViolationType = Field(
        ...,
        description="Type of policy violation"
    )
    policy_rule: str = Field(
        ...,
        description="The policy rule that was violated"
    )
    actual_value: Any = Field(
        ...,
        description="The actual value that violated the policy"
    )
    threshold_value: Any = Field(
        ...,
        description="The policy threshold that was exceeded"
    )
    severity: Literal["warning", "hard_stop"] = Field(
        default="hard_stop",
        description="Violation severity"
    )
    message: str = Field(
        ...,
        description="Human-readable violation message"
    )


class PolicyCheckResult(BaseModel):
    """Result of a policy evaluation.
    
    This is what the policy engine returns after checking an action.
    """
    check_id: str = Field(
        default_factory=lambda: f"chk_{uuid4().hex[:12]}",
        description="Unique check identifier"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the check was performed"
    )
    decision: PolicyDecision = Field(
        ...,
        description="Policy decision: approve, veto, or escalate"
    )
    policy_version: str = Field(
        ...,
        description="Version of policy rules used"
    )
    violations: List[PolicyViolation] = Field(
        default_factory=list,
        description="List of policy violations (if any)"
    )
    approved_action: Optional[str] = Field(
        default=None,
        description="The action that was approved (if decision is approve)"
    )
    veto_reason: Optional[str] = Field(
        default=None,
        description="Reason for veto (if decision is veto)"
    )
    escalation_reason: Optional[str] = Field(
        default=None,
        description="Reason for escalation (if decision is escalate)"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context for the check"
    )
    
    @property
    def is_approved(self) -> bool:
        """Check if the action was approved."""
        return self.decision == PolicyDecision.APPROVE
    
    @property
    def is_vetoed(self) -> bool:
        """Check if the action was vetoed."""
        return self.decision == PolicyDecision.VETO
    
    @property
    def requires_escalation(self) -> bool:
        """Check if escalation is required."""
        return self.decision == PolicyDecision.ESCALATE


class HumanOverride(BaseModel):
    """Record of a human override.
    
    When a human intervenes in an AI decision, this is the record.
    The AI decision is RETAINED. Override reason is MANDATORY.
    No retroactive deletion allowed.
    """
    override_id: str = Field(
        default_factory=lambda: f"ovr_{uuid4().hex[:12]}",
        description="Unique override identifier"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the override occurred"
    )
    
    # Reference to original decision
    original_decision_id: str = Field(
        ...,
        description="ID of the AI decision being overridden"
    )
    original_action: str = Field(
        ...,
        description="The action AI recommended"
    )
    original_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="AI's confidence in original decision"
    )
    
    # Override details
    override_type: OverrideType = Field(
        ...,
        description="Type of override"
    )
    new_action: str = Field(
        ...,
        description="The action human decided to take"
    )
    reason: str = Field(
        ...,
        min_length=10,
        description="Mandatory explanation for override (min 10 chars)"
    )
    
    # Human identity (for accountability)
    reviewer_id: str = Field(
        ...,
        description="ID of the human reviewer"
    )
    reviewer_role: str = Field(
        ...,
        description="Role of the human reviewer"
    )
    
    # Context preservation
    session_id: str = Field(
        ...,
        description="Associated session ID"
    )
    user_id: str = Field(
        ...,
        description="Associated user ID"
    )
    
    # Policy impact tracking
    policy_version: str = Field(
        ...,
        description="Policy version at time of override"
    )
    policy_impact: Optional[str] = Field(
        default=None,
        description="Description of policy impact (if any)"
    )
    
    # Training feedback control
    allow_training_feedback: bool = Field(
        default=False,
        description="Whether this override can be used for model training"
    )


class AuditEntry(BaseModel):
    """A single immutable audit log entry.
    """
    entry_id: str = Field(
        default_factory=lambda: f"aud_{uuid4().hex[:12]}",
        description="Unique entry identifier"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the entry was created"
    )
    event_type: AuditEventType = Field(
        ...,
        description="Type of event being logged"
    )
    
    # Core identifiers
    decision_id: Optional[str] = Field(
        default=None,
        description="Associated decision ID"
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Associated session ID"
    )
    user_id: Optional[str] = Field(
        default=None,
        description="Associated user ID"
    )
    
    # Decision details
    action: Optional[str] = Field(
        default=None,
        description="Action taken or proposed"
    )
    confidence_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score (if applicable)"
    )
    decided_by: Optional[Literal["AI", "HUMAN", "POLICY"]] = Field(
        default=None,
        description="Who made the decision"
    )
    
    # Governance
    policy_version: str = Field(
        ...,
        description="Policy version in effect"
    )
    policy_check_result: Optional[PolicyCheckResult] = Field(
        default=None,
        description="Policy check result (if applicable)"
    )
    human_override: Optional[HumanOverride] = Field(
        default=None,
        description="Human override record (if applicable)"
    )
    
    # Agent outputs summary (for traceability)
    agent_outputs: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Summary of agent outputs"
    )
    
    # Integrity
    previous_hash: Optional[str] = Field(
        default=None,
        description="Hash of previous entry (for chain integrity)"
    )
    entry_hash: Optional[str] = Field(
        default=None,
        description="Hash of this entry"
    )
    
    # Metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context"
    )
    
    def to_jsonl(self) -> str:
        """Serialize entry to JSONL format."""
        import json
        return json.dumps(self.model_dump(mode="json"), default=str)
    
    @classmethod
    def from_jsonl(cls, line: str) -> "AuditEntry":
        """Deserialize entry from JSONL format."""
        import json
        return cls.model_validate(json.loads(line))


class PolicyRules(BaseModel):
    """Parsed policy rules from YAML configuration.
    
    This is the in-memory representation of policy_rules.yaml.
    Used by PolicyEngine for runtime checks.
    """
    
    class Metadata(BaseModel):
        version: str
        last_updated: str
        author: str
        description: str
    
    class ConfidenceRules(BaseModel):
        min_to_allow: float = Field(ge=0.0, le=1.0)
        min_to_escalate: float = Field(ge=0.0, le=1.0)
        calibration_method: str
        max_confidence_cap: float = Field(ge=0.0, le=1.0)
    
    class ActionRules(BaseModel):
        permanent_block_allowed: bool
        temporary_block_allowed: bool
        max_temporary_block_hours: int
        max_actions_per_user_per_day: int
        allowed_actions: List[str]
        human_only_actions: List[str]
    
    class EscalationRules(BaseModel):
        disagreement_threshold: float = Field(ge=0.0, le=1.0)
        consecutive_high_risk_limit: int
        force_human_review: List[str]
        escalation_priorities: Dict[str, int]
    
    class RiskThresholds(BaseModel):
        low_risk_max: float = Field(ge=0.0, le=1.0)
        medium_risk_max: float = Field(ge=0.0, le=1.0)
        high_risk_min: float = Field(ge=0.0, le=1.0)
        critical_risk_threshold: float = Field(ge=0.0, le=1.0)
    
    class RateLimits(BaseModel):
        max_decisions_per_ip_per_minute: int
        max_failed_attempts: int
        lockout_duration_minutes: int
        max_escalations_per_user_per_day: int
    
    class ModelVersions(BaseModel):
        detection: str
        behavior: str
        network: str
        confidence: str
        explanation: str
    
    class HumanOverrideRules(BaseModel):
        require_reason: bool
        min_reason_length: int
        allowed_override_types: List[str]
        retain_ai_decision: bool
        allow_training_feedback: bool
    
    class AuditConfig(BaseModel):
        format: str
        log_path_pattern: str
        append_only: bool
        retention_days: int
        required_fields: List[str]
        enable_hash_chain: bool
        hash_algorithm: str
    
    metadata: Metadata
    confidence: ConfidenceRules
    actions: ActionRules
    escalation: EscalationRules
    risk_thresholds: RiskThresholds
    rate_limits: RateLimits
    models: ModelVersions
    human_override: HumanOverrideRules
    audit: AuditConfig
