"""Audit Integration - End-to-End Audit Trail with S3 + DynamoDB.

Provides unified interface for:
1. S3 audit logs (immutable, versioned, append-only)
2. DynamoDB operational metadata (fast lookups, no joins)

This module handles:
- Decision logging to both S3 (audit trail) and DynamoDB (index)
- Escalation tracking
- Human override recording
- Audit trail retrieval and correlation
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from aegis_ai.governance.audit.config import (
    create_audit_logger,
    create_dynamodb_metadata_store,
)
from aegis_ai.governance.audit.logger import AuditLogger
from aegis_ai.governance.schemas import (
    AuditEntry,
    AuditEventType,
    PolicyCheckResult,
    HumanOverride,
)


logger = logging.getLogger(__name__)


class UnifiedAuditTrail:
    """Unified audit trail with S3 logs + DynamoDB metadata.
    
    Features:
    - Immutable S3 logs (regulator-friendly)
    - Fast DynamoDB lookups
    - Escalation tracking
    - Override recording
    - Audit trail correlation
    """
    
    def __init__(
        self,
        audit_logger: Optional[AuditLogger] = None,
        use_dynamodb: bool = True,
    ):
        """Initialize unified audit trail.
        
        Args:
            audit_logger: Audit logger instance (S3-backed by default)
            use_dynamodb: Whether to enable DynamoDB metadata store
        """
        self.audit_logger = audit_logger or create_audit_logger()
        self.use_dynamodb = use_dynamodb
        self.dynamodb_metadata = None
        
        if use_dynamodb:
            try:
                self.dynamodb_metadata = create_dynamodb_metadata_store()
                logger.info("DynamoDB metadata store initialized")
            except (ImportError, ValueError) as e:
                logger.warning(f"Could not initialize DynamoDB: {e}")
                self.use_dynamodb = False
    
    def log_decision(
        self,
        decision_id: str,
        session_id: str,
        user_id: str,
        action: str,
        confidence_score: float,
        decided_by: str,
        policy_version: str,
        policy_check_result: Optional[PolicyCheckResult] = None,
        agent_outputs: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """Log a decision immutably to S3 + DynamoDB.
        
        Args:
            decision_id: Unique decision identifier
            session_id: Associated session ID
            user_id: Associated user ID
            action: Action taken (ALLOW/BLOCK/CHALLENGE/ESCALATE)
            confidence_score: Confidence score (0.0 to 1.0)
            decided_by: Who made the decision (AI/HUMAN/POLICY)
            policy_version: Version of policy rules used
            policy_check_result: Policy check result if applicable
            agent_outputs: Summary of agent outputs for traceability
            metadata: Additional context
            
        Returns:
            The created audit entry
        """
        # Log to S3 (immutable audit trail)
        entry = self.audit_logger.log_decision(
            decision_id=decision_id,
            session_id=session_id,
            user_id=user_id,
            action=action,
            confidence_score=confidence_score,
            decided_by=decided_by,
            policy_version=policy_version,
            policy_check_result=policy_check_result,
            agent_outputs=agent_outputs,
            metadata=metadata,
        )
        
        # Also index in DynamoDB for fast lookups
        if self.use_dynamodb and self.dynamodb_metadata:
            try:
                self.dynamodb_metadata.put_decision(
                    decision_id=decision_id,
                    session_id=session_id,
                    user_id=user_id,
                    action=action,
                    confidence_score=confidence_score,
                    decided_by=decided_by,
                    policy_version=policy_version,
                    timestamp=entry.timestamp,
                    metadata=metadata,
                )
                logger.debug(f"Indexed decision in DynamoDB: {decision_id}")
            except Exception as e:
                logger.warning(f"Failed to index decision in DynamoDB: {e}")
        
        return entry
    
    def log_policy_violation(
        self,
        violation_id: str,
        decision_id: str,
        session_id: str,
        user_id: str,
        violation_type: str,
        policy_rule: str,
        actual_value: Any,
        threshold_value: Any,
        severity: str = "hard_stop",
        message: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """Log a policy violation immutably.
        
        Args:
            violation_id: Unique violation identifier
            decision_id: Associated decision ID
            session_id: Associated session ID
            user_id: Associated user ID
            violation_type: Type of violation
            policy_rule: Policy rule that was violated
            actual_value: Actual value that violated policy
            threshold_value: Policy threshold
            severity: "warning" or "hard_stop"
            message: Human-readable message
            metadata: Additional context
            
        Returns:
            The created audit entry
        """
        entry = self.audit_logger.log_policy_violation(
            violation_id=violation_id,
            decision_id=decision_id,
            session_id=session_id,
            user_id=user_id,
            violation_type=violation_type,
            policy_rule=policy_rule,
            actual_value=actual_value,
            threshold_value=threshold_value,
            severity=severity,
            message=message,
            metadata=metadata,
        )
        
        return entry
    
    def log_human_override(
        self,
        override_id: str,
        original_decision_id: str,
        original_action: str,
        original_confidence: float,
        new_action: str,
        override_type: str,
        reason: str,
        reviewer_id: str,
        reviewer_role: str,
        session_id: str,
        user_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """Log a human override immutably to S3 + DynamoDB.
        
        Args:
            override_id: Unique override identifier
            original_decision_id: Decision that was overridden
            original_action: Original action
            original_confidence: Original confidence score
            new_action: New action after override
            override_type: Type of override (APPROVE/REJECT/MODIFY)
            reason: Reason for override
            reviewer_id: Reviewer ID
            reviewer_role: Reviewer role
            session_id: Session ID
            user_id: User ID
            metadata: Additional context
            
        Returns:
            The created audit entry
        """
        # Log to S3
        entry = self.audit_logger.log_human_override(
            override_id=override_id,
            original_decision_id=original_decision_id,
            original_action=original_action,
            original_confidence=original_confidence,
            new_action=new_action,
            override_type=override_type,
            reason=reason,
            reviewer_id=reviewer_id,
            reviewer_role=reviewer_role,
            session_id=session_id,
            user_id=user_id,
            metadata=metadata,
        )
        
        # Also index in DynamoDB
        if self.use_dynamodb and self.dynamodb_metadata:
            try:
                self.dynamodb_metadata.create_override_reference(
                    override_id=override_id,
                    original_decision_id=original_decision_id,
                    reviewer_id=reviewer_id,
                    override_type=override_type,
                    reason=reason,
                    timestamp=entry.timestamp,
                    metadata={
                        "original_action": original_action,
                        "new_action": new_action,
                        "original_confidence": original_confidence,
                        "reviewer_role": reviewer_role,
                        **(metadata or {})
                    }
                )
                logger.debug(f"Indexed override in DynamoDB: {override_id}")
            except Exception as e:
                logger.warning(f"Failed to index override in DynamoDB: {e}")
        
        return entry
    
    def log_escalation(
        self,
        decision_id: str,
        escalation_type: str,
        reason: str,
        escalated_to: str,
        session_id: str,
        user_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> tuple[str, AuditEntry]:
        """Log an escalation immutably to S3 + DynamoDB.
        
        Args:
            decision_id: Decision that triggered escalation
            escalation_type: Type of escalation (POLICY/THRESHOLD/MANUAL)
            reason: Reason for escalation
            escalated_to: Who escalation goes to
            session_id: Session ID
            user_id: User ID
            metadata: Additional context
            
        Returns:
            Tuple of (escalation_id, audit_entry)
        """
        # Log to S3
        entry = self.audit_logger.log_escalation(
            decision_id=decision_id,
            escalation_type=escalation_type,
            reason=reason,
            escalated_to=escalated_to,
            session_id=session_id,
            user_id=user_id,
            metadata=metadata,
        )
        
        escalation_id = entry.escalation_id or f"esc_{decision_id}"
        
        # Also track in DynamoDB
        if self.use_dynamodb and self.dynamodb_metadata:
            try:
                self.dynamodb_metadata.create_escalation(
                    decision_id=decision_id,
                    escalation_type=escalation_type,
                    reason=reason,
                    escalated_to=escalated_to,
                    timestamp=entry.timestamp,
                    metadata=metadata,
                )
                logger.debug(f"Indexed escalation in DynamoDB: {escalation_id}")
            except Exception as e:
                logger.warning(f"Failed to index escalation in DynamoDB: {e}")
        
        return escalation_id, entry
    
    # ========================================================================
    # Fast lookups via DynamoDB
    # ========================================================================
    
    def get_decision_by_id(self, decision_id: str) -> Optional[Dict[str, Any]]:
        """Get decision metadata from DynamoDB (fast).
        
        Args:
            decision_id: Decision ID to look up
            
        Returns:
            Decision metadata or None
        """
        if not self.use_dynamodb or not self.dynamodb_metadata:
            return None
        
        return self.dynamodb_metadata.get_decision(decision_id)
    
    def get_user_decisions(
        self,
        user_id: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get recent decisions for a user (fast via GSI).
        
        Args:
            user_id: User ID to query
            limit: Maximum results
            
        Returns:
            List of decision metadata
        """
        if not self.use_dynamodb or not self.dynamodb_metadata:
            return []
        
        return self.dynamodb_metadata.query_decisions_by_user(user_id, limit=limit)
    
    def get_session_decisions(
        self,
        session_id: str,
    ) -> List[Dict[str, Any]]:
        """Get all decisions in a session (fast via GSI).
        
        Args:
            session_id: Session ID to query
            
        Returns:
            List of decision metadata
        """
        if not self.use_dynamodb or not self.dynamodb_metadata:
            return []
        
        return self.dynamodb_metadata.query_decisions_by_session(session_id)
    
    def get_override_for_decision(
        self,
        decision_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get override record for a decision (fast).
        
        Args:
            decision_id: Decision ID
            
        Returns:
            Override record or None
        """
        if not self.use_dynamodb or not self.dynamodb_metadata:
            return None
        
        return self.dynamodb_metadata.get_override_for_decision(decision_id)
    
    def get_escalations_for_decision(
        self,
        decision_id: str,
    ) -> List[Dict[str, Any]]:
        """Get all escalations for a decision (fast).
        
        Args:
            decision_id: Decision ID
            
        Returns:
            List of escalation records
        """
        if not self.use_dynamodb or not self.dynamodb_metadata:
            return []
        
        return self.dynamodb_metadata.get_escalations_by_decision(decision_id)
    
    def update_escalation_status(
        self,
        escalation_id: str,
        status: str,
        resolution: Optional[str] = None,
        resolved_by: Optional[str] = None,
    ) -> bool:
        """Update escalation status in DynamoDB.
        
        Args:
            escalation_id: Escalation ID
            status: New status
            resolution: Resolution details
            resolved_by: Who resolved it
            
        Returns:
            True if successful
        """
        if not self.use_dynamodb or not self.dynamodb_metadata:
            return False
        
        return self.dynamodb_metadata.update_escalation_status(
            escalation_id=escalation_id,
            status=status,
            resolution=resolution,
            resolved_by=resolved_by,
        )
    
    def get_reviewer_overrides(
        self,
        reviewer_id: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get all overrides by a reviewer (fast via GSI).
        
        Args:
            reviewer_id: Reviewer ID
            limit: Maximum results
            
        Returns:
            List of override records
        """
        if not self.use_dynamodb or not self.dynamodb_metadata:
            return []
        
        return self.dynamodb_metadata.get_overrides_by_reviewer(
            reviewer_id,
            limit=limit
        )
    
    def health_check(self) -> Dict[str, bool]:
        """Check health of all audit components.
        
        Returns:
            Health status dictionary
        """
        health = {
            "audit_logger": True,  # File/S3 is usually available
        }
        
        if self.use_dynamodb and self.dynamodb_metadata:
            health["dynamodb"] = self.dynamodb_metadata.health_check()
        
        return health


# Re-export
__all__ = ["UnifiedAuditTrail"]
