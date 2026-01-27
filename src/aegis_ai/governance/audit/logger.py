"""Audit Logger - Immutable logging of all decisions.
"""

import hashlib
import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from src.aegis_ai.governance.schemas import (
    AuditEntry,
    AuditEventType,
    HumanOverride,
    PolicyCheckResult,
)


class AuditLogIntegrityError(Exception):
    """Raised when audit log integrity check fails."""
    pass


class AuditLogger:
    """Records all decisions immutably in JSONL format."""
    
    DEFAULT_LOG_DIR = Path(__file__).parent.parent.parent.parent.parent / "logs" / "audit"
    
    def __init__(
        self,
        log_dir: Optional[str] = None,
        log_filename_pattern: str = "aegis_audit_{date}.jsonl",
        enable_hash_chain: bool = True,
        hash_algorithm: str = "sha256",
    ):
        """Initialize audit logger.
        
        Args:
            log_dir: Directory for audit logs. Uses default if not provided.
            log_filename_pattern: Pattern for log filename. {date} is replaced.
            enable_hash_chain: Whether to enable hash chain integrity.
            hash_algorithm: Hash algorithm for integrity checks.
        """
        self.log_dir = Path(log_dir) if log_dir else self.DEFAULT_LOG_DIR
        self.log_filename_pattern = log_filename_pattern
        self.enable_hash_chain = enable_hash_chain
        self.hash_algorithm = hash_algorithm
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Cache last hash for chain continuity
        self._last_hash: Optional[str] = None
        
        # Ensure log directory exists
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize hash chain from existing logs
        if self.enable_hash_chain:
            self._last_hash = self._get_last_hash_from_log()
    
    def _get_current_log_path(self) -> Path:
        """Get path to current day's log file.
        
        Returns:
            Path to today's log file
        """
        today = datetime.utcnow().strftime("%Y-%m-%d")
        filename = self.log_filename_pattern.replace("{date}", today)
        return self.log_dir / filename
    
    def _get_last_hash_from_log(self) -> Optional[str]:
        """Read the last hash from the current log file."""
        log_path = self._get_current_log_path()
        
        if not log_path.exists():
            return None
        
        last_hash = None
        try:
            with open(log_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        entry = json.loads(line)
                        last_hash = entry.get("entry_hash")
        except (json.JSONDecodeError, IOError):
            return None
        
        return last_hash
    
    def _compute_hash(self, content: str) -> str:
        """Compute hash of content."""
        hasher = hashlib.new(self.hash_algorithm)
        hasher.update(content.encode("utf-8"))
        return hasher.hexdigest()
    
    def _create_hash_chain_entry(self, entry: AuditEntry) -> AuditEntry:
        """Add hash chain fields to entry."""
        
        if not self.enable_hash_chain:
            return entry
        
        # Create a copy with previous hash
        entry_dict = entry.model_dump(mode="json")
        entry_dict["previous_hash"] = self._last_hash
        
        # Compute hash of entry content (without entry_hash field)
        entry_dict["entry_hash"] = None
        content_to_hash = json.dumps(entry_dict, sort_keys=True, default=str)
        entry_hash = self._compute_hash(content_to_hash)
        
        entry_dict["entry_hash"] = entry_hash
        
        return AuditEntry.model_validate(entry_dict)
    
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
        """Log a decision immutably."""
        entry = AuditEntry(
            event_type=AuditEventType.DECISION,
            decision_id=decision_id,
            session_id=session_id,
            user_id=user_id,
            action=action,
            confidence_score=confidence_score,
            decided_by=decided_by,  # type: ignore
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
        session_id: str,
        user_id: str,
        policy_version: str,
        policy_check_result: PolicyCheckResult,
        proposed_action: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """Log a policy violation."""
        entry = AuditEntry(
            event_type=AuditEventType.POLICY_VIOLATION,
            session_id=session_id,
            user_id=user_id,
            action=proposed_action,
            policy_version=policy_version,
            policy_check_result=policy_check_result,
            decided_by="POLICY",
            metadata={
                "violation_count": len(policy_check_result.violations),
                "violation_types": [v.violation_type.value for v in policy_check_result.violations],
                **(metadata or {}),
            },
        )
        
        return self._append_entry(entry)
    
    def log_human_override(
        self,
        human_override: HumanOverride,
        policy_version: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """Log a human override."""
        entry = AuditEntry(
            event_type=AuditEventType.HUMAN_OVERRIDE,
            decision_id=human_override.original_decision_id,
            session_id=human_override.session_id,
            user_id=human_override.user_id,
            action=human_override.new_action,
            decided_by="HUMAN",
            policy_version=policy_version,
            human_override=human_override,
            metadata={
                "original_action": human_override.original_action,
                "original_confidence": human_override.original_confidence,
                "override_type": human_override.override_type.value,
                "reviewer_id": human_override.reviewer_id,
                "reviewer_role": human_override.reviewer_role,
                **(metadata or {}),
            },
        )
        
        return self._append_entry(entry)
    
    def log_escalation(
        self,
        decision_id: str,
        session_id: str,
        user_id: str,
        escalation_reason: str,
        confidence_score: float,
        policy_version: str,
        agent_outputs: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """Log an escalation to human review."""
        entry = AuditEntry(
            event_type=AuditEventType.ESCALATION,
            decision_id=decision_id,
            session_id=session_id,
            user_id=user_id,
            action="ESCALATE",
            confidence_score=confidence_score,
            decided_by="AI",
            policy_version=policy_version,
            agent_outputs=agent_outputs,
            metadata={
                "escalation_reason": escalation_reason,
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
    
    def _append_entry(self, entry: AuditEntry) -> AuditEntry:
        """Append entry to log file (thread-safe)."""
        with self._lock:
            # Add hash chain
            entry = self._create_hash_chain_entry(entry)
            
            # Get current log file
            log_path = self._get_current_log_path()
            
            # Append to file (never overwrite)
            with open(log_path, "a") as f:
                f.write(entry.to_jsonl() + "\n")
            
            # Update last hash for chain continuity
            if self.enable_hash_chain:
                self._last_hash = entry.entry_hash
            
            return entry
    
    def get_entries(
        self,
        date: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        decision_id: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Generator[AuditEntry, None, None]:
        """Retrieve audit entries with optional filtering."""
        if date is None:
            date = datetime.utcnow().strftime("%Y-%m-%d")
        
        filename = self.log_filename_pattern.replace("{date}", date)
        log_path = self.log_dir / filename
        
        if not log_path.exists():
            return
        
        with open(log_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    entry = AuditEntry.from_jsonl(line)
                    
                    # Apply filters
                    if event_type and entry.event_type != event_type:
                        continue
                    if decision_id and entry.decision_id != decision_id:
                        continue
                    if session_id and entry.session_id != session_id:
                        continue
                    if user_id and entry.user_id != user_id:
                        continue
                    
                    yield entry
                except (json.JSONDecodeError, ValueError):
                    # Skip malformed entries
                    continue
    
    def get_decision_history(self, decision_id: str) -> List[AuditEntry]:
        """Get all entries related to a decision."""
        entries = []
        
        # Search all log files
        for log_file in sorted(self.log_dir.glob("*.jsonl")):
            with open(log_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        entry = AuditEntry.from_jsonl(line)
                        if entry.decision_id == decision_id:
                            entries.append(entry)
                    except (json.JSONDecodeError, ValueError):
                        continue
        
        return sorted(entries, key=lambda e: e.timestamp)
    
    def verify_integrity(self, date: Optional[str] = None) -> bool:
        """Verify hash chain integrity of log file."""
        if not self.enable_hash_chain:
            return True
        
        if date is None:
            date = datetime.utcnow().strftime("%Y-%m-%d")
        
        filename = self.log_filename_pattern.replace("{date}", date)
        log_path = self.log_dir / filename
        
        if not log_path.exists():
            return True  # Empty log is valid
        
        previous_hash = None
        line_number = 0
        
        with open(log_path, "r") as f:
            for line in f:
                line_number += 1
                line = line.strip()
                if not line:
                    continue
                
                try:
                    entry_dict = json.loads(line)
                    
                    # Check previous hash matches
                    if entry_dict.get("previous_hash") != previous_hash:
                        raise AuditLogIntegrityError(
                            f"Hash chain broken at line {line_number}. "
                            f"Expected previous_hash={previous_hash}, "
                            f"got {entry_dict.get('previous_hash')}"
                        )
                    
                    # Verify entry hash
                    stored_hash = entry_dict.get("entry_hash")
                    entry_dict["entry_hash"] = None
                    content_to_hash = json.dumps(entry_dict, sort_keys=True, default=str)
                    computed_hash = self._compute_hash(content_to_hash)
                    
                    if computed_hash != stored_hash:
                        raise AuditLogIntegrityError(
                            f"Entry hash mismatch at line {line_number}. "
                            f"Entry may have been tampered with."
                        )
                    
                    previous_hash = stored_hash
                    
                except json.JSONDecodeError as e:
                    raise AuditLogIntegrityError(
                        f"Malformed JSON at line {line_number}: {e}"
                    )
        
        return True
    
    def get_log_files(self) -> List[Path]:
        """Get list of all audit log files."""
        return sorted(self.log_dir.glob("*.jsonl"))
    
    def get_entry_count(self, date: Optional[str] = None) -> int:
        """Get count of entries in log file."""
        if date is None:
            date = datetime.utcnow().strftime("%Y-%m-%d")
        
        filename = self.log_filename_pattern.replace("{date}", date)
        log_path = self.log_dir / filename
        
        if not log_path.exists():
            return 0
        
        count = 0
        with open(log_path, "r") as f:
            for line in f:
                if line.strip():
                    count += 1
        
        return count

