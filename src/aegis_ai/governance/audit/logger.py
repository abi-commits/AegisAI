"""Audit logger facade with pluggable backends."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Union

from aegis_ai.governance.schemas import (
    AuditEntry, AuditEventType, HumanOverride, PolicyCheckResult)
from aegis_ai.governance.audit.store import (
    AuditStore, FileAuditStore, AuditLogIntegrityError)

__all__ = ["AuditLogger", "AuditLogIntegrityError"]
logger = logging.getLogger(__name__)


class AuditLogger:
    """High-level audit logger with pluggable backends."""
    
    def __init__(self, store: Optional[AuditStore] = None, log_dir: Optional[str] = None,
                 log_filename_pattern: str = "aegis_audit_{date}.jsonl",
                 enable_hash_chain: bool = True, hash_algorithm: str = "sha256",
                 use_background_writer: bool = False):
        if store is not None:
            self._store = store
        else:
            self._store = FileAuditStore(
                log_dir=log_dir, log_filename_pattern=log_filename_pattern,
                enable_hash_chain=enable_hash_chain, hash_algorithm=hash_algorithm)
        
        self._background_writer: Optional["BackgroundAuditWriter"] = None
        if use_background_writer:
            from aegis_ai.governance.audit.background_writer import BackgroundAuditWriter
            self._background_writer = BackgroundAuditWriter(store=self._store)
        
        self.enable_hash_chain = enable_hash_chain
        if isinstance(self._store, FileAuditStore):
            self.log_dir = self._store.log_dir
            self.log_filename_pattern = self._store.log_filename_pattern
        else:
            self.log_dir = Path(log_dir) if log_dir else FileAuditStore.DEFAULT_LOG_DIR
            self.log_filename_pattern = log_filename_pattern
    
    def _append_entry(self, entry: AuditEntry) -> AuditEntry:
        """Append entry using store or background writer."""
        if self._background_writer is not None:
            return self._background_writer.append_entry(entry)
        return self._store.append_entry(entry)
    
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
        """Log a decision immutably.
        
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
        # Validate confidence score range
        if not 0.0 <= confidence_score <= 1.0:
            logger.warning(
                f"Confidence score {confidence_score} out of range [0, 1], clamping"
            )
            confidence_score = max(0.0, min(1.0, confidence_score))
        
        entry = AuditEntry(
            event_type=AuditEventType.DECISION,
            decision_id=decision_id,
            session_id=session_id,
            user_id=user_id,
            action=action,
            confidence_score=confidence_score,
            decided_by=decided_by,  # type: ignore  # Union type requires runtime validation
            policy_version=policy_version,
            policy_check_result=policy_check_result,
            agent_outputs=agent_outputs,
            metadata=metadata or {},
        )
        
        return self._append_entry(entry)
    
    def log_policy_check(
        self,
        session_id: str,
        user_id: str,
        policy_version: str,
        policy_check_result: PolicyCheckResult,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """Log a policy check result."""
        entry = AuditEntry(
            event_type=AuditEventType.POLICY_CHECK,
            session_id=session_id,
            user_id=user_id,
            action=policy_check_result.approved_action,
            policy_version=policy_version,
            policy_check_result=policy_check_result,
            decided_by="POLICY",
            metadata=metadata or {},
        )
        
        return self._append_entry(entry)
    
    def log_policy_violation(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        policy_version: Optional[str] = None,
        policy_check_result: Optional[PolicyCheckResult] = None,
        proposed_action: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        # New parameters for UnifiedAuditTrail
        violation_id: Optional[str] = None,
        decision_id: Optional[str] = None,
        violation_type: Optional[str] = None,
        policy_rule: Optional[str] = None,
        actual_value: Optional[Any] = None,
        threshold_value: Optional[Any] = None,
        severity: str = "hard_stop",
        message: str = "",
    ) -> AuditEntry:
        """Log a policy violation.
        
        Supports both legacy interface and new UnifiedAuditTrail interface.
        """
        # Handle new parameters if provided
        if violation_id is not None and decision_id is not None:
            entry = AuditEntry(
                event_type=AuditEventType.POLICY_VIOLATION,
                decision_id=decision_id,
                session_id=session_id or "",
                user_id=user_id or "",
                action=proposed_action or "BLOCK",
                policy_version=policy_version or "",
                decided_by="POLICY",
                metadata={
                    "violation_id": violation_id,
                    "violation_type": violation_type,
                    "policy_rule": policy_rule,
                    "actual_value": actual_value,
                    "threshold_value": threshold_value,
                    "severity": severity,
                    "message": message,
                    **(metadata or {}),
                },
            )
        else:
            # Legacy interface
            entry = AuditEntry(
                event_type=AuditEventType.POLICY_VIOLATION,
                session_id=session_id or "",
                user_id=user_id or "",
                action=proposed_action or "BLOCK",
                policy_version=policy_version or "",
                policy_check_result=policy_check_result,
                decided_by="POLICY",
                metadata={
                    "violation_count": len(policy_check_result.violations) if policy_check_result else 0,
                    "violation_types": [v.violation_type.value for v in policy_check_result.violations] if policy_check_result else [],
                    **(metadata or {}),
                },
            )
        
        return self._append_entry(entry)
    
    def log_human_override(
        self,
        human_override: Optional[HumanOverride] = None,
        policy_version: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        # New parameters for UnifiedAuditTrail
        override_id: Optional[str] = None,
        original_decision_id: Optional[str] = None,
        original_action: Optional[str] = None,
        original_confidence: Optional[float] = None,
        new_action: Optional[str] = None,
        override_type: Optional[str] = None,
        reason: Optional[str] = None,
        reviewer_id: Optional[str] = None,
        reviewer_role: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> AuditEntry:
        """Log a human override.
        
        Supports both legacy interface and new UnifiedAuditTrail interface.
        """
        if override_id is not None and original_decision_id is not None:
            # New unified interface
            entry = AuditEntry(
                event_type=AuditEventType.HUMAN_OVERRIDE,
                decision_id=original_decision_id,
                session_id=session_id or "",
                user_id=user_id or "",
                action=new_action or original_action or "MODIFIED",
                decided_by="HUMAN",
                policy_version=policy_version or "",
                metadata={
                    "override_id": override_id,
                    "original_action": original_action,
                    "new_action": new_action,
                    "original_confidence": original_confidence,
                    "override_type": override_type,
                    "reason": reason,
                    "reviewer_id": reviewer_id,
                    "reviewer_role": reviewer_role,
                    **(metadata or {}),
                },
            )
        else:
            # Legacy interface with HumanOverride object
            entry = AuditEntry(
                event_type=AuditEventType.HUMAN_OVERRIDE,
                decision_id=human_override.original_decision_id if human_override else "",
                session_id=human_override.session_id if human_override else "",
                user_id=human_override.user_id if human_override else "",
                action=human_override.new_action if human_override else "",
                decided_by="HUMAN",
                policy_version=policy_version or "",
                human_override=human_override,
                metadata={
                    "original_action": human_override.original_action if human_override else "",
                    "original_confidence": human_override.original_confidence if human_override else 0.0,
                    "override_type": human_override.override_type.value if human_override else "",
                    "reviewer_id": human_override.reviewer_id if human_override else "",
                    "reviewer_role": human_override.reviewer_role if human_override else "",
                    **(metadata or {}),
                },
            )
        
        return self._append_entry(entry)
    
    def log_escalation(
        self,
        decision_id: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        escalation_reason: Optional[str] = None,
        confidence_score: Optional[float] = None,
        policy_version: Optional[str] = None,
        agent_outputs: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        # New parameters for UnifiedAuditTrail
        escalation_type: Optional[str] = None,
        reason: Optional[str] = None,
        escalated_to: Optional[str] = None,
    ) -> AuditEntry:
        """Log an escalation to human review.
        
        Supports both legacy and new UnifiedAuditTrail interfaces.
        """
        # Normalize parameters
        esc_reason = escalation_reason or reason or "Manual escalation"
        esc_type = escalation_type or "MANUAL"
        
        entry = AuditEntry(
            event_type=AuditEventType.ESCALATION,
            decision_id=decision_id or "",
            session_id=session_id or "",
            user_id=user_id or "",
            action="ESCALATE",
            confidence_score=confidence_score or 0.5,
            decided_by="AI",
            policy_version=policy_version or "",
            agent_outputs=agent_outputs,
            metadata={
                "escalation_reason": esc_reason,
                "escalation_type": esc_type,
                "escalated_to": escalated_to,
                **(metadata or {}),
            },
        )
        
        return self._append_entry(entry)
    
    def log_system_event(
        self,
        event_description: str,
        policy_version: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """Log a system event (startup, shutdown, config change, etc.)"""
        entry = AuditEntry(
            event_type=AuditEventType.SYSTEM_EVENT,
            policy_version=policy_version,
            metadata={
                "event_description": event_description,
                **(metadata or {}),
            },
        )
        
        return self._append_entry(entry)
    
    def get_entries(
        self,
        date: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        decision_id: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Generator[AuditEntry, None, None]:
        """Retrieve audit entries with optional filtering."""
        return self._store.get_entries(
            date=date,
            event_type=event_type,
            decision_id=decision_id,
            session_id=session_id,
            user_id=user_id,
        )
    
    def get_decision_history(self, decision_id: str) -> List[AuditEntry]:
        """Get all entries related to a decision."""
        entries = []
        
        # Search all log files if using FileAuditStore
        if isinstance(self._store, FileAuditStore):
            for log_file in sorted(self._store.get_log_files()):
                # Extract date from filename
                date_str = log_file.stem.replace("aegis_audit_", "")
                for entry in self._store.get_entries(
                    date=date_str, decision_id=decision_id
                ):
                    entries.append(entry)
        else:
            # For other stores, search current date only
            for entry in self._store.get_entries(decision_id=decision_id):
                entries.append(entry)
        
        return sorted(entries, key=lambda e: e.timestamp)
    
    def verify_integrity(self, date: Optional[str] = None) -> bool:
        """Verify hash chain integrity of log file."""
        return self._store.verify_integrity(date=date)
    def get_log_files(self) -> List[Path]:
        """Get list of all audit log files."""
        if isinstance(self._store, FileAuditStore):
            return self._store.get_log_files()
        return []
    
    def get_entry_count(self, date: Optional[str] = None) -> int:
        """Get count of entries in log file."""
        if isinstance(self._store, FileAuditStore):
            return self._store.get_entry_count(date=date)
        # For other stores, count by iterating
        return sum(1 for _ in self.get_entries(date=date))
    
    def shutdown(self) -> None:
        """Shutdown the logger and flush any pending writes."""
        if self._background_writer is not None:
            self._background_writer.shutdown()
    
    @property
    def store(self) -> AuditStore:
        """Get the underlying audit store."""
        return self._store

