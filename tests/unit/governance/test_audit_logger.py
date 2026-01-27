"""Unit tests for Audit Logger.

Tests that audit logs are immutable, append-only, and maintain integrity.
"""

import json
import pytest
import tempfile
import os
from datetime import datetime
from pathlib import Path

from src.aegis_ai.governance.audit.logger import (
    AuditLogger,
    AuditLogIntegrityError,
)
from src.aegis_ai.governance.schemas import (
    AuditEntry,
    AuditEventType,
    HumanOverride,
    OverrideType,
    PolicyCheckResult,
    PolicyDecision,
)


@pytest.fixture
def temp_log_dir():
    """Create a temporary directory for logs."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def audit_logger(temp_log_dir):
    """Create an AuditLogger with temp directory."""
    return AuditLogger(
        log_dir=temp_log_dir,
        enable_hash_chain=True,
        hash_algorithm="sha256",
    )


@pytest.fixture
def audit_logger_no_hash(temp_log_dir):
    """Create an AuditLogger without hash chain."""
    return AuditLogger(
        log_dir=temp_log_dir,
        enable_hash_chain=False,
    )


class TestAuditLoggerInit:
    """Test AuditLogger initialization."""
    
    def test_creates_log_directory(self, temp_log_dir):
        """Test that log directory is created."""
        new_dir = os.path.join(temp_log_dir, "subdir", "logs")
        logger = AuditLogger(log_dir=new_dir)
        assert os.path.exists(new_dir)
    
    def test_log_file_created_on_first_write(self, audit_logger, temp_log_dir):
        """Test that log file is created on first entry."""
        audit_logger.log_decision(
            decision_id="dec_123",
            session_id="sess_123",
            user_id="user_123",
            action="ALLOW",
            confidence_score=0.90,
            decided_by="AI",
            policy_version="1.0.0",
        )
        
        log_files = list(Path(temp_log_dir).glob("*.jsonl"))
        assert len(log_files) == 1


class TestDecisionLogging:
    """Test decision logging functionality."""
    
    def test_log_decision_creates_entry(self, audit_logger):
        """Test that decision logging creates an entry."""
        entry = audit_logger.log_decision(
            decision_id="dec_123",
            session_id="sess_123",
            user_id="user_123",
            action="ALLOW",
            confidence_score=0.90,
            decided_by="AI",
            policy_version="1.0.0",
        )
        
        assert entry.entry_id.startswith("aud_")
        assert entry.event_type == AuditEventType.DECISION
        assert entry.decision_id == "dec_123"
        assert entry.action == "ALLOW"
    
    def test_log_decision_with_policy_check(self, audit_logger):
        """Test logging decision with policy check result."""
        policy_result = PolicyCheckResult(
            decision=PolicyDecision.APPROVE,
            policy_version="1.0.0",
            approved_action="ALLOW",
        )
        
        entry = audit_logger.log_decision(
            decision_id="dec_456",
            session_id="sess_456",
            user_id="user_456",
            action="ALLOW",
            confidence_score=0.85,
            decided_by="AI",
            policy_version="1.0.0",
            policy_check_result=policy_result,
        )
        
        assert entry.policy_check_result is not None
        assert entry.policy_check_result.is_approved
    
    def test_log_decision_with_agent_outputs(self, audit_logger):
        """Test logging decision with agent output summary."""
        agent_outputs = {
            "detection": {"risk_score": 0.20},
            "behavior": {"deviation_score": 0.15},
            "network": {"risk_score": 0.10},
        }
        
        entry = audit_logger.log_decision(
            decision_id="dec_789",
            session_id="sess_789",
            user_id="user_789",
            action="ALLOW",
            confidence_score=0.92,
            decided_by="AI",
            policy_version="1.0.0",
            agent_outputs=agent_outputs,
        )
        
        assert entry.agent_outputs is not None
        assert "detection" in entry.agent_outputs


class TestPolicyLogging:
    """Test policy-related logging."""
    
    def test_log_policy_check(self, audit_logger):
        """Test logging a policy check."""
        policy_result = PolicyCheckResult(
            decision=PolicyDecision.APPROVE,
            policy_version="1.0.0",
            approved_action="CHALLENGE",
        )
        
        entry = audit_logger.log_policy_check(
            session_id="sess_123",
            user_id="user_123",
            policy_version="1.0.0",
            policy_check_result=policy_result,
        )
        
        assert entry.event_type == AuditEventType.POLICY_CHECK
        assert entry.decided_by == "POLICY"
    
    def test_log_policy_violation(self, audit_logger):
        """Test logging a policy violation."""
        from src.aegis_ai.governance.schemas import PolicyViolation, PolicyViolationType
        
        violation = PolicyViolation(
            violation_type=PolicyViolationType.CONFIDENCE_TOO_LOW,
            policy_rule="confidence.min_to_allow",
            actual_value=0.60,
            threshold_value=0.80,
            severity="hard_stop",
            message="Confidence too low",
        )
        
        policy_result = PolicyCheckResult(
            decision=PolicyDecision.ESCALATE,
            policy_version="1.0.0",
            violations=[violation],
            escalation_reason="Confidence below threshold",
        )
        
        entry = audit_logger.log_policy_violation(
            session_id="sess_123",
            user_id="user_123",
            policy_version="1.0.0",
            policy_check_result=policy_result,
            proposed_action="BLOCK_TEMPORARY",
        )
        
        assert entry.event_type == AuditEventType.POLICY_VIOLATION
        assert entry.metadata["violation_count"] == 1


class TestHumanOverrideLogging:
    """Test human override logging."""
    
    def test_log_human_override(self, audit_logger):
        """Test logging a human override."""
        override = HumanOverride(
            original_decision_id="dec_123",
            original_action="BLOCK_TEMPORARY",
            original_confidence=0.75,
            override_type=OverrideType.REJECT,
            new_action="ALLOW",
            reason="Customer verified via phone call, legitimate access attempt",
            reviewer_id="analyst_001",
            reviewer_role="Senior Fraud Analyst",
            session_id="sess_123",
            user_id="user_123",
            policy_version="1.0.0",
        )
        
        entry = audit_logger.log_human_override(
            human_override=override,
            policy_version="1.0.0",
        )
        
        assert entry.event_type == AuditEventType.HUMAN_OVERRIDE
        assert entry.decided_by == "HUMAN"
        assert entry.human_override is not None
        assert entry.human_override.reason == override.reason


class TestEscalationLogging:
    """Test escalation logging."""
    
    def test_log_escalation(self, audit_logger):
        """Test logging an escalation."""
        entry = audit_logger.log_escalation(
            decision_id="dec_123",
            session_id="sess_123",
            user_id="user_123",
            escalation_reason="High agent disagreement detected",
            confidence_score=0.65,
            policy_version="1.0.0",
        )
        
        assert entry.event_type == AuditEventType.ESCALATION
        assert entry.action == "ESCALATE"
        assert entry.metadata["escalation_reason"] == "High agent disagreement detected"


class TestSystemEventLogging:
    """Test system event logging."""
    
    def test_log_system_event(self, audit_logger):
        """Test logging a system event."""
        entry = audit_logger.log_system_event(
            event_description="Policy engine reloaded",
            policy_version="1.0.0",
            metadata={"previous_version": "0.9.0"},
        )
        
        assert entry.event_type == AuditEventType.SYSTEM_EVENT
        assert entry.metadata["event_description"] == "Policy engine reloaded"


class TestAppendOnly:
    """Test append-only behavior."""
    
    def test_entries_are_appended(self, audit_logger, temp_log_dir):
        """Test that multiple entries are appended."""
        for i in range(5):
            audit_logger.log_decision(
                decision_id=f"dec_{i}",
                session_id=f"sess_{i}",
                user_id=f"user_{i}",
                action="ALLOW",
                confidence_score=0.90,
                decided_by="AI",
                policy_version="1.0.0",
            )
        
        # Count entries in file
        count = audit_logger.get_entry_count()
        assert count == 5
    
    def test_entries_are_not_overwritten(self, audit_logger, temp_log_dir):
        """Test that entries cannot be overwritten."""
        # Write first entry
        entry1 = audit_logger.log_decision(
            decision_id="dec_first",
            session_id="sess_first",
            user_id="user_first",
            action="ALLOW",
            confidence_score=0.90,
            decided_by="AI",
            policy_version="1.0.0",
        )
        
        # Write second entry
        entry2 = audit_logger.log_decision(
            decision_id="dec_second",
            session_id="sess_second",
            user_id="user_second",
            action="BLOCK_TEMPORARY",
            confidence_score=0.85,
            decided_by="AI",
            policy_version="1.0.0",
        )
        
        # Read entries and verify both exist
        entries = list(audit_logger.get_entries())
        assert len(entries) == 2
        assert entries[0].decision_id == "dec_first"
        assert entries[1].decision_id == "dec_second"


class TestHashChainIntegrity:
    """Test hash chain integrity verification."""
    
    def test_hash_chain_created(self, audit_logger):
        """Test that hash chain is created."""
        entry1 = audit_logger.log_decision(
            decision_id="dec_1",
            session_id="sess_1",
            user_id="user_1",
            action="ALLOW",
            confidence_score=0.90,
            decided_by="AI",
            policy_version="1.0.0",
        )
        
        assert entry1.entry_hash is not None
        assert entry1.previous_hash is None  # First entry
        
        entry2 = audit_logger.log_decision(
            decision_id="dec_2",
            session_id="sess_2",
            user_id="user_2",
            action="CHALLENGE",
            confidence_score=0.85,
            decided_by="AI",
            policy_version="1.0.0",
        )
        
        assert entry2.entry_hash is not None
        assert entry2.previous_hash == entry1.entry_hash
    
    def test_verify_integrity_passes(self, audit_logger):
        """Test that integrity verification passes for valid log."""
        for i in range(5):
            audit_logger.log_decision(
                decision_id=f"dec_{i}",
                session_id=f"sess_{i}",
                user_id=f"user_{i}",
                action="ALLOW",
                confidence_score=0.90,
                decided_by="AI",
                policy_version="1.0.0",
            )
        
        assert audit_logger.verify_integrity() is True
    
    def test_verify_integrity_detects_tampering(self, audit_logger, temp_log_dir):
        """Test that integrity verification detects tampering."""
        # Create some entries
        for i in range(3):
            audit_logger.log_decision(
                decision_id=f"dec_{i}",
                session_id=f"sess_{i}",
                user_id=f"user_{i}",
                action="ALLOW",
                confidence_score=0.90,
                decided_by="AI",
                policy_version="1.0.0",
            )
        
        # Tamper with the log file
        log_files = list(Path(temp_log_dir).glob("*.jsonl"))
        assert len(log_files) == 1
        
        with open(log_files[0], 'r') as f:
            lines = f.readlines()
        
        # Modify an entry
        entry_dict = json.loads(lines[1])
        entry_dict["action"] = "BLOCK_PERMANENT"  # Tampered!
        lines[1] = json.dumps(entry_dict) + "\n"
        
        with open(log_files[0], 'w') as f:
            f.writelines(lines)
        
        # Verification should fail
        with pytest.raises(AuditLogIntegrityError):
            audit_logger.verify_integrity()
    
    def test_no_hash_chain_when_disabled(self, audit_logger_no_hash):
        """Test that no hash chain is created when disabled."""
        entry = audit_logger_no_hash.log_decision(
            decision_id="dec_1",
            session_id="sess_1",
            user_id="user_1",
            action="ALLOW",
            confidence_score=0.90,
            decided_by="AI",
            policy_version="1.0.0",
        )
        
        assert entry.entry_hash is None
        assert entry.previous_hash is None


class TestEntryRetrieval:
    """Test entry retrieval functionality."""
    
    def test_get_entries_all(self, audit_logger):
        """Test retrieving all entries."""
        for i in range(3):
            audit_logger.log_decision(
                decision_id=f"dec_{i}",
                session_id=f"sess_{i}",
                user_id=f"user_{i}",
                action="ALLOW",
                confidence_score=0.90,
                decided_by="AI",
                policy_version="1.0.0",
            )
        
        entries = list(audit_logger.get_entries())
        assert len(entries) == 3
    
    def test_get_entries_by_event_type(self, audit_logger):
        """Test filtering entries by event type."""
        audit_logger.log_decision(
            decision_id="dec_1",
            session_id="sess_1",
            user_id="user_1",
            action="ALLOW",
            confidence_score=0.90,
            decided_by="AI",
            policy_version="1.0.0",
        )
        
        audit_logger.log_escalation(
            decision_id="dec_2",
            session_id="sess_2",
            user_id="user_2",
            escalation_reason="Test",
            confidence_score=0.60,
            policy_version="1.0.0",
        )
        
        decisions = list(audit_logger.get_entries(event_type=AuditEventType.DECISION))
        escalations = list(audit_logger.get_entries(event_type=AuditEventType.ESCALATION))
        
        assert len(decisions) == 1
        assert len(escalations) == 1
    
    def test_get_entries_by_user(self, audit_logger):
        """Test filtering entries by user ID."""
        audit_logger.log_decision(
            decision_id="dec_1",
            session_id="sess_1",
            user_id="user_target",
            action="ALLOW",
            confidence_score=0.90,
            decided_by="AI",
            policy_version="1.0.0",
        )
        
        audit_logger.log_decision(
            decision_id="dec_2",
            session_id="sess_2",
            user_id="user_other",
            action="ALLOW",
            confidence_score=0.90,
            decided_by="AI",
            policy_version="1.0.0",
        )
        
        entries = list(audit_logger.get_entries(user_id="user_target"))
        assert len(entries) == 1
        assert entries[0].user_id == "user_target"
    
    def test_get_decision_history(self, audit_logger):
        """Test getting all entries for a decision."""
        # Initial decision
        audit_logger.log_decision(
            decision_id="dec_history",
            session_id="sess_1",
            user_id="user_1",
            action="BLOCK_TEMPORARY",
            confidence_score=0.75,
            decided_by="AI",
            policy_version="1.0.0",
        )
        
        # Human override
        override = HumanOverride(
            original_decision_id="dec_history",
            original_action="BLOCK_TEMPORARY",
            original_confidence=0.75,
            override_type=OverrideType.REJECT,
            new_action="ALLOW",
            reason="Verified customer via phone",
            reviewer_id="analyst_001",
            reviewer_role="Analyst",
            session_id="sess_1",
            user_id="user_1",
            policy_version="1.0.0",
        )
        audit_logger.log_human_override(
            human_override=override,
            policy_version="1.0.0",
        )
        
        history = audit_logger.get_decision_history("dec_history")
        assert len(history) == 2


class TestJSONLFormat:
    """Test JSONL format compliance."""
    
    def test_entries_are_valid_json(self, audit_logger, temp_log_dir):
        """Test that each line is valid JSON."""
        for i in range(3):
            audit_logger.log_decision(
                decision_id=f"dec_{i}",
                session_id=f"sess_{i}",
                user_id=f"user_{i}",
                action="ALLOW",
                confidence_score=0.90,
                decided_by="AI",
                policy_version="1.0.0",
            )
        
        log_files = list(Path(temp_log_dir).glob("*.jsonl"))
        with open(log_files[0], 'r') as f:
            for line in f:
                if line.strip():
                    # Should not raise
                    entry = json.loads(line)
                    assert "entry_id" in entry
                    assert "timestamp" in entry
    
    def test_to_jsonl_method(self):
        """Test AuditEntry.to_jsonl() method."""
        entry = AuditEntry(
            event_type=AuditEventType.DECISION,
            decision_id="dec_123",
            session_id="sess_123",
            user_id="user_123",
            action="ALLOW",
            confidence_score=0.90,
            decided_by="AI",
            policy_version="1.0.0",
        )
        
        jsonl = entry.to_jsonl()
        parsed = json.loads(jsonl)
        
        assert parsed["decision_id"] == "dec_123"
        assert parsed["action"] == "ALLOW"
    
    def test_from_jsonl_method(self):
        """Test AuditEntry.from_jsonl() method."""
        jsonl = '{"entry_id":"aud_123","timestamp":"2026-01-26T12:00:00","event_type":"decision","decision_id":"dec_123","session_id":"sess_123","user_id":"user_123","action":"ALLOW","confidence_score":0.9,"decided_by":"AI","policy_version":"1.0.0"}'
        
        entry = AuditEntry.from_jsonl(jsonl)
        
        assert entry.entry_id == "aud_123"
        assert entry.decision_id == "dec_123"


class TestThreadSafety:
    """Test thread safety of audit logger."""
    
    def test_concurrent_writes(self, audit_logger):
        """Test that concurrent writes don't corrupt the log."""
        import threading
        
        def write_entries(thread_id):
            for i in range(10):
                audit_logger.log_decision(
                    decision_id=f"dec_t{thread_id}_{i}",
                    session_id=f"sess_t{thread_id}_{i}",
                    user_id=f"user_t{thread_id}_{i}",
                    action="ALLOW",
                    confidence_score=0.90,
                    decided_by="AI",
                    policy_version="1.0.0",
                )
        
        threads = [
            threading.Thread(target=write_entries, args=(i,))
            for i in range(5)
        ]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        # Verify all entries were written
        count = audit_logger.get_entry_count()
        assert count == 50  # 5 threads * 10 entries
        
        # Verify integrity
        assert audit_logger.verify_integrity() is True
