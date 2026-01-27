"""Human Override Handler - Authority Preservation."""

from datetime import datetime
from typing import Any, Dict, Optional

from src.aegis_ai.governance.schemas import (
    HumanOverride,
    OverrideType,
    PolicyRules,
)
from src.aegis_ai.governance.audit.logger import AuditLogger


class HumanOverrideError(Exception):
    """Raised when human override validation fails."""
    pass


class HumanOverrideHandler:
    """Handles creation and logging of human overrides."""
    def __init__(
        self,
        audit_logger: AuditLogger,
        policy_rules: PolicyRules,
    ):
        self.audit_logger = audit_logger
        self.policy_rules = policy_rules
    
    def create_override(
        self,
        original_decision_id: str,
        original_action: str,
        original_confidence: float,
        new_action: str,
        override_type: OverrideType,
        reason: str,
        reviewer_id: str,
        reviewer_role: str,
        session_id: str,
        user_id: str,
        policy_impact: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> HumanOverride:
        """Create and log a human override.
        This is the main entry point for human intervention.
        """
        # Validate override type
        self._validate_override_type(override_type)
        
        # Validate reason
        self._validate_reason(reason)
        
        # Create override record
        override = HumanOverride(
            original_decision_id=original_decision_id,
            original_action=original_action,
            original_confidence=original_confidence,
            override_type=override_type,
            new_action=new_action,
            reason=reason,
            reviewer_id=reviewer_id,
            reviewer_role=reviewer_role,
            session_id=session_id,
            user_id=user_id,
            policy_version=self.policy_rules.metadata.version,
            policy_impact=policy_impact,
            allow_training_feedback=self.policy_rules.human_override.allow_training_feedback,
        )
        
        # Log immutably - this cannot be undone
        self.audit_logger.log_human_override(
            human_override=override,
            policy_version=self.policy_rules.metadata.version,
            metadata=metadata,
        )
        
        return override
    
    def _validate_override_type(self, override_type: OverrideType) -> None:
        """Validate override type against allowed types.
        
        Args:
            override_type: Type to validate
            
        Raises:
            HumanOverrideError: If type not allowed
        """
        allowed_types = self.policy_rules.human_override.allowed_override_types
        
        if override_type.value not in allowed_types:
            raise HumanOverrideError(
                f"Override type '{override_type.value}' is not allowed. "
                f"Allowed types: {allowed_types}"
            )
    
    def _validate_reason(self, reason: str) -> None:
        """Validate override reason.
        
        Args:
            reason: Reason string
            
        Raises:
            HumanOverrideError: If reason is invalid
        """
        if not self.policy_rules.human_override.require_reason:
            return
        
        min_length = self.policy_rules.human_override.min_reason_length
        
        if not reason or len(reason.strip()) < min_length:
            raise HumanOverrideError(
                f"Override reason is mandatory and must be at least {min_length} characters. "
                f"Got {len(reason.strip()) if reason else 0} characters."
            )
    
    def approve_ai_decision(
        self,
        original_decision_id: str,
        original_action: str,
        original_confidence: float,
        reason: str,
        reviewer_id: str,
        reviewer_role: str,
        session_id: str,
        user_id: str,
    ) -> HumanOverride:
        """Approve an AI decision that required human review.
        """
        return self.create_override(
            original_decision_id=original_decision_id,
            original_action=original_action,
            original_confidence=original_confidence,
            new_action=original_action,  # Same action - approval
            override_type=OverrideType.APPROVE,
            reason=reason,
            reviewer_id=reviewer_id,
            reviewer_role=reviewer_role,
            session_id=session_id,
            user_id=user_id,
            policy_impact="Human approved AI recommendation. No policy change.",
        )
    
    def reject_ai_decision(
        self,
        original_decision_id: str,
        original_action: str,
        original_confidence: float,
        new_action: str,
        reason: str,
        reviewer_id: str,
        reviewer_role: str,
        session_id: str,
        user_id: str,
    ) -> HumanOverride:
        """Reject an AI decision and substitute a different action.
        """
        return self.create_override(
            original_decision_id=original_decision_id,
            original_action=original_action,
            original_confidence=original_confidence,
            new_action=new_action,
            override_type=OverrideType.REJECT,
            reason=reason,
            reviewer_id=reviewer_id,
            reviewer_role=reviewer_role,
            session_id=session_id,
            user_id=user_id,
            policy_impact=f"Human rejected AI recommendation '{original_action}', selected '{new_action}' instead.",
        )
    
    def modify_ai_decision(
        self,
        original_decision_id: str,
        original_action: str,
        original_confidence: float,
        new_action: str,
        reason: str,
        reviewer_id: str,
        reviewer_role: str,
        session_id: str,
        user_id: str,
        modifications: Optional[Dict[str, Any]] = None,
    ) -> HumanOverride:
        """Modify an AI decision (partial override).
        """
        return self.create_override(
            original_decision_id=original_decision_id,
            original_action=original_action,
            original_confidence=original_confidence,
            new_action=new_action,
            override_type=OverrideType.MODIFY,
            reason=reason,
            reviewer_id=reviewer_id,
            reviewer_role=reviewer_role,
            session_id=session_id,
            user_id=user_id,
            policy_impact=f"Human modified AI recommendation from '{original_action}' to '{new_action}'.",
            metadata={"modifications": modifications} if modifications else None,
        )
    
    def defer_decision(
        self,
        original_decision_id: str,
        original_action: str,
        original_confidence: float,
        reason: str,
        reviewer_id: str,
        reviewer_role: str,
        session_id: str,
        user_id: str,
        defer_until: Optional[datetime] = None,
    ) -> HumanOverride:
        """Defer a decision for later review."""
        return self.create_override(
            original_decision_id=original_decision_id,
            original_action=original_action,
            original_confidence=original_confidence,
            new_action="DEFERRED",
            override_type=OverrideType.DEFER,
            reason=reason,
            reviewer_id=reviewer_id,
            reviewer_role=reviewer_role,
            session_id=session_id,
            user_id=user_id,
            policy_impact="Decision deferred for later review. No immediate action taken.",
            metadata={"defer_until": defer_until.isoformat() if defer_until else None},
        )
    
    def get_override_history(self, decision_id: str) -> list[HumanOverride]:
        """Get all overrides for a decision.
        
        Args:
            decision_id: Decision ID to look up
            
        Returns:
            List of HumanOverride records
        """
        from src.aegis_ai.governance.schemas import AuditEventType
        
        overrides = []
        for entry in self.audit_logger.get_entries(event_type=AuditEventType.HUMAN_OVERRIDE):
            if entry.decision_id == decision_id and entry.human_override:
                overrides.append(entry.human_override)
        
        return overrides
