"""Audit trail integration with S3 + DynamoDB for logging, tracking, and retrieval."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from aegis_ai.common.constants import DataConstants
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
    """Unified audit trail with S3 logs + DynamoDB metadata for compliance."""
    
    def __init__(self, audit_logger: Optional[AuditLogger] = None, use_dynamodb: bool = True):
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
    
    def log_decision(self, decision_id: str, session_id: str, user_id: str, action: str,
                     confidence_score: float, decided_by: str, policy_version: str,
                     policy_check_result: Optional[PolicyCheckResult] = None,
                     agent_outputs: Optional[Dict[str, Any]] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> AuditEntry:
        """Log a decision to S3 and DynamoDB."""
        entry = self.audit_logger.log_decision(
            decision_id=decision_id, session_id=session_id, user_id=user_id,
            action=action, confidence_score=confidence_score, decided_by=decided_by,
            policy_version=policy_version, policy_check_result=policy_check_result,
            agent_outputs=agent_outputs, metadata=metadata)
        
        if self.use_dynamodb and self.dynamodb_metadata:
            try:
                self.dynamodb_metadata.put_decision(
                    decision_id=decision_id, session_id=session_id, user_id=user_id,
                    action=action, confidence_score=confidence_score, decided_by=decided_by,
                    policy_version=policy_version, timestamp=entry.timestamp, metadata=metadata)
                logger.debug(f"Indexed decision in DynamoDB: {decision_id}")
            except Exception as e:
                logger.error(f"AUDIT_CONSISTENCY_ERROR: Failed to index {decision_id}: {e}")
        
        return entry
    
    def log_policy_violation(self, violation_id: str, decision_id: str, session_id: str,
                             user_id: str, violation_type: str, policy_rule: str,
                             actual_value: Any, threshold_value: Any, severity: str = "hard_stop",
                             message: str = "", metadata: Optional[Dict[str, Any]] = None) -> AuditEntry:
        """Log a policy violation immutably to S3."""
        return self.audit_logger.log_policy_violation(
            violation_id=violation_id, decision_id=decision_id, session_id=session_id,
            user_id=user_id, violation_type=violation_type, policy_rule=policy_rule,
            actual_value=actual_value, threshold_value=threshold_value, severity=severity,
            message=message, metadata=metadata)
    
    def log_human_override(self, override_id: str, original_decision_id: str,
                          original_action: str, original_confidence: float, new_action: str,
                          override_type: str, reason: str, reviewer_id: str, reviewer_role: str,
                          session_id: str, user_id: str,
                          metadata: Optional[Dict[str, Any]] = None) -> AuditEntry:
        """Log a human override to S3 and DynamoDB."""
        entry = self.audit_logger.log_human_override(
            override_id=override_id, original_decision_id=original_decision_id,
            original_action=original_action, original_confidence=original_confidence,
            new_action=new_action, override_type=override_type, reason=reason,
            reviewer_id=reviewer_id, reviewer_role=reviewer_role, session_id=session_id,
            user_id=user_id, metadata=metadata)
        
        if self.use_dynamodb and self.dynamodb_metadata:
            try:
                self.dynamodb_metadata.create_override_reference(
                    override_id=override_id, original_decision_id=original_decision_id,
                    reviewer_id=reviewer_id, override_type=override_type, reason=reason,
                    timestamp=entry.timestamp, metadata={
                        "original_action": original_action, "new_action": new_action,
                        "original_confidence": original_confidence, "reviewer_role": reviewer_role,
                        **(metadata or {})})
                logger.debug(f"Indexed override in DynamoDB: {override_id}")
            except Exception as e:
                logger.error(f"AUDIT_CONSISTENCY_ERROR: Failed to index override {override_id}: {e}")
        
        return entry
    
    def log_escalation(self, decision_id: str, escalation_type: str, reason: str,
                      escalated_to: str, session_id: str, user_id: str,
                      metadata: Optional[Dict[str, Any]] = None) -> tuple[str, AuditEntry]:
        """Log an escalation to S3 and DynamoDB."""
        entry = self.audit_logger.log_escalation(
            decision_id=decision_id, escalation_type=escalation_type, reason=reason,
            escalated_to=escalated_to, session_id=session_id, user_id=user_id, metadata=metadata)
        
        escalation_id = entry.escalation_id or f"esc_{decision_id}"
        
        if self.use_dynamodb and self.dynamodb_metadata:
            try:
                self.dynamodb_metadata.create_escalation(
                    decision_id=decision_id, escalation_type=escalation_type, reason=reason,
                    escalated_to=escalated_to, timestamp=entry.timestamp, metadata=metadata)
                logger.debug(f"Indexed escalation in DynamoDB: {escalation_id}")
            except Exception as e:
                logger.error(f"AUDIT_CONSISTENCY_ERROR: Failed to index escalation {decision_id}: {e}")
        
        return escalation_id, entry
    
    def get_decision_by_id(self, decision_id: str) -> Optional[Dict[str, Any]]:
        """Get decision metadata from DynamoDB."""
        return self.dynamodb_metadata.get_decision(decision_id) if self.use_dynamodb and self.dynamodb_metadata else None
    
    def get_user_decisions(self, user_id: str, limit: int = DataConstants.DEFAULT_QUERY_LIMIT) -> List[Dict[str, Any]]:
        """Get recent decisions for a user via GSI."""
        return self.dynamodb_metadata.query_decisions_by_user(user_id, limit=limit) if self.use_dynamodb and self.dynamodb_metadata else []
    
    def get_session_decisions(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all decisions in a session via GSI."""
        return self.dynamodb_metadata.query_decisions_by_session(session_id) if self.use_dynamodb and self.dynamodb_metadata else []
    
    def get_override_for_decision(self, decision_id: str) -> Optional[Dict[str, Any]]:
        """Get override record for a decision."""
        return self.dynamodb_metadata.get_override_for_decision(decision_id) if self.use_dynamodb and self.dynamodb_metadata else None
    
    def get_escalations_for_decision(self, decision_id: str) -> List[Dict[str, Any]]:
        """Get all escalations for a decision."""
        return self.dynamodb_metadata.get_escalations_by_decision(decision_id) if self.use_dynamodb and self.dynamodb_metadata else []
    
    def update_escalation_status(self, escalation_id: str, status: str,
                                resolution: Optional[str] = None,
                                resolved_by: Optional[str] = None) -> bool:
        """Update escalation status in DynamoDB."""
        return self.dynamodb_metadata.update_escalation_status(
            escalation_id=escalation_id, status=status, resolution=resolution,
            resolved_by=resolved_by) if self.use_dynamodb and self.dynamodb_metadata else False
    
    def get_reviewer_overrides(self, reviewer_id: str, limit: int = DataConstants.DEFAULT_QUERY_LIMIT) -> List[Dict[str, Any]]:
        """Get all overrides by a reviewer via GSI."""
        return self.dynamodb_metadata.get_overrides_by_reviewer(reviewer_id, limit=limit) if self.use_dynamodb and self.dynamodb_metadata else []
    
    def health_check(self) -> Dict[str, bool]:
        """Check health of all audit components."""
        return {
            "audit_logger": True,
            "dynamodb": self.dynamodb_metadata.health_check() if (self.use_dynamodb and self.dynamodb_metadata) else None
        }


# Re-export
__all__ = ["UnifiedAuditTrail"]
