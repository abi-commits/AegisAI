"""Unit tests for Human Override Handler.

Tests that human overrides preserve AI decisions and maintain accountability.
"""

import pytest
import tempfile
import os

from aegis_ai.governance.override import (
    HumanOverrideHandler,
    HumanOverrideError,
)
from aegis_ai.governance.audit.logger import AuditLogger
from aegis_ai.governance.schemas import (
    OverrideType,
    PolicyRules,
    AuditEventType,
)


@pytest.fixture
def policy_yaml_content():
    """Sample policy YAML for testing."""
    return """
metadata:
  version: "1.0.0-test"
  last_updated: "2026-01-26"
  author: "Test Suite"
  description: "Test policy rules"

confidence:
  min_to_allow: 0.80
  min_to_escalate: 0.50
  calibration_method: "isotonic"
  max_confidence_cap: 0.99

actions:
  permanent_block_allowed: false
  temporary_block_allowed: true
  max_temporary_block_hours: 24
  max_actions_per_user_per_day: 5
  allowed_actions:
    - "ALLOW"
    - "CHALLENGE"
    - "BLOCK_TEMPORARY"
    - "ESCALATE"
  human_only_actions:
    - "BLOCK_PERMANENT"

escalation:
  disagreement_threshold: 0.30
  consecutive_high_risk_limit: 3
  force_human_review:
    - "low_confidence"
  escalation_priorities:
    critical: 1
    high: 2
    medium: 3
    low: 4

risk_thresholds:
  low_risk_max: 0.30
  medium_risk_max: 0.70
  high_risk_min: 0.70
  critical_risk_threshold: 0.95

rate_limits:
  max_decisions_per_ip_per_minute: 10
  max_failed_attempts: 5
  lockout_duration_minutes: 30
  max_escalations_per_user_per_day: 10

models:
  detection: "xgboost_v2.1.0"
  behavior: "isolation_forest_v1.0"
  network: "gnn_v1.2.0"
  confidence: "calibrated_ensemble_v1.0"
  explanation: "shap_v1.0.0"

human_override:
  require_reason: true
  min_reason_length: 10
  allowed_override_types:
    - "APPROVE"
    - "REJECT"
    - "MODIFY"
    - "DEFER"
  retain_ai_decision: true
  allow_training_feedback: false

audit:
  format: "jsonl"
  log_path_pattern: "logs/audit/aegis_audit_{date}.jsonl"
  append_only: true
  retention_days: 2555
  required_fields:
    - "timestamp"
    - "decision_id"
  enable_hash_chain: true
  hash_algorithm: "sha256"
"""


@pytest.fixture
def temp_log_dir():
    """Create a temporary directory for logs."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def policy_rules(policy_yaml_content):
    """Create PolicyRules from YAML content."""
    import yaml
    raw_config = yaml.safe_load(policy_yaml_content)
    return PolicyRules.model_validate(raw_config)


@pytest.fixture
def audit_logger(temp_log_dir):
    """Create an AuditLogger with temp directory."""
    return AuditLogger(
        log_dir=temp_log_dir,
        enable_hash_chain=True,
    )


@pytest.fixture
def override_handler(audit_logger, policy_rules):
    """Create a HumanOverrideHandler."""
    return HumanOverrideHandler(
        audit_logger=audit_logger,
        policy_rules=policy_rules,
    )


class TestOverrideCreation:
    """Test override creation."""
    
    def test_create_override_success(self, override_handler):
        """Test successful override creation."""
        override = override_handler.create_override(
            original_decision_id="dec_123",
            original_action="BLOCK_TEMPORARY",
            original_confidence=0.75,
            new_action="ALLOW",
            override_type=OverrideType.REJECT,
            reason="Customer verified via phone call, confirmed legitimate access",
            reviewer_id="analyst_001",
            reviewer_role="Senior Fraud Analyst",
            session_id="sess_123",
            user_id="user_123",
        )
        
        assert override.override_id.startswith("ovr_")
        assert override.original_decision_id == "dec_123"
        assert override.original_action == "BLOCK_TEMPORARY"
        assert override.new_action == "ALLOW"
        assert override.override_type == OverrideType.REJECT
    
    def test_override_reason_mandatory(self, override_handler):
        """Test that reason is mandatory."""
        with pytest.raises(HumanOverrideError) as exc_info:
            override_handler.create_override(
                original_decision_id="dec_123",
                original_action="BLOCK_TEMPORARY",
                original_confidence=0.75,
                new_action="ALLOW",
                override_type=OverrideType.REJECT,
                reason="short",  # Too short (min 10 chars)
                reviewer_id="analyst_001",
                reviewer_role="Analyst",
                session_id="sess_123",
                user_id="user_123",
            )
        
        assert "mandatory" in str(exc_info.value).lower()
    
    def test_override_reason_empty_rejected(self, override_handler):
        """Test that empty reason is rejected."""
        with pytest.raises(HumanOverrideError):
            override_handler.create_override(
                original_decision_id="dec_123",
                original_action="BLOCK_TEMPORARY",
                original_confidence=0.75,
                new_action="ALLOW",
                override_type=OverrideType.REJECT,
                reason="",  # Empty
                reviewer_id="analyst_001",
                reviewer_role="Analyst",
                session_id="sess_123",
                user_id="user_123",
            )


class TestOverrideTypes:
    """Test different override types."""
    
    def test_approve_ai_decision(self, override_handler):
        """Test approving an AI decision."""
        override = override_handler.approve_ai_decision(
            original_decision_id="dec_123",
            original_action="CHALLENGE",
            original_confidence=0.65,
            reason="Reviewed evidence, AI recommendation is correct",
            reviewer_id="analyst_001",
            reviewer_role="Analyst",
            session_id="sess_123",
            user_id="user_123",
        )
        
        assert override.override_type == OverrideType.APPROVE
        assert override.new_action == "CHALLENGE"  # Same as original
    
    def test_reject_ai_decision(self, override_handler):
        """Test rejecting an AI decision."""
        override = override_handler.reject_ai_decision(
            original_decision_id="dec_123",
            original_action="BLOCK_TEMPORARY",
            original_confidence=0.72,
            new_action="ALLOW",
            reason="Customer called support, verified identity via security questions",
            reviewer_id="analyst_002",
            reviewer_role="Senior Analyst",
            session_id="sess_123",
            user_id="user_123",
        )
        
        assert override.override_type == OverrideType.REJECT
        assert override.new_action == "ALLOW"
        assert override.original_action == "BLOCK_TEMPORARY"
    
    def test_modify_ai_decision(self, override_handler):
        """Test modifying an AI decision."""
        override = override_handler.modify_ai_decision(
            original_decision_id="dec_123",
            original_action="BLOCK_TEMPORARY",
            original_confidence=0.80,
            new_action="CHALLENGE",
            reason="Reducing severity, user has good history, requires additional verification",
            reviewer_id="analyst_003",
            reviewer_role="Team Lead",
            session_id="sess_123",
            user_id="user_123",
            modifications={"severity_reduced": True},
        )
        
        assert override.override_type == OverrideType.MODIFY
        assert override.new_action == "CHALLENGE"
    
    def test_defer_decision(self, override_handler):
        """Test deferring a decision."""
        from datetime import datetime, timedelta, timezone
        
        defer_until = datetime.now(timezone.utc) + timedelta(hours=2)
        
        override = override_handler.defer_decision(
            original_decision_id="dec_123",
            original_action="CHALLENGE",
            original_confidence=0.55,
            reason="Need more information from user, waiting for callback",
            reviewer_id="analyst_004",
            reviewer_role="Analyst",
            session_id="sess_123",
            user_id="user_123",
            defer_until=defer_until,
        )
        
        assert override.override_type == OverrideType.DEFER
        assert override.new_action == "DEFERRED"


class TestAIDecisionPreservation:
    """Test that AI decisions are preserved."""
    
    def test_original_decision_retained(self, override_handler):
        """Test that original AI decision is retained in override."""
        override = override_handler.reject_ai_decision(
            original_decision_id="dec_preserve",
            original_action="BLOCK_TEMPORARY",
            original_confidence=0.78,
            new_action="ALLOW",
            reason="Verified customer, AI was too aggressive on this one",
            reviewer_id="analyst_001",
            reviewer_role="Analyst",
            session_id="sess_123",
            user_id="user_123",
        )
        
        # Original decision fields are preserved
        assert override.original_decision_id == "dec_preserve"
        assert override.original_action == "BLOCK_TEMPORARY"
        assert override.original_confidence == 0.78
    
    def test_original_decision_in_audit_log(self, override_handler, audit_logger):
        """Test that original decision appears in audit log."""
        override_handler.reject_ai_decision(
            original_decision_id="dec_audit_test",
            original_action="CHALLENGE",
            original_confidence=0.70,
            new_action="ALLOW",
            reason="Customer verified through additional documentation",
            reviewer_id="analyst_001",
            reviewer_role="Analyst",
            session_id="sess_audit",
            user_id="user_audit",
        )
        
        # Check audit log
        entries = list(audit_logger.get_entries(event_type=AuditEventType.HUMAN_OVERRIDE))
        assert len(entries) == 1
        
        entry = entries[0]
        assert entry.metadata["original_action"] == "CHALLENGE"
        assert entry.metadata["original_confidence"] == 0.70


class TestPolicyImpactTracking:
    """Test policy impact tracking."""
    
    def test_policy_impact_logged(self, override_handler, audit_logger):
        """Test that policy impact is logged."""
        override = override_handler.reject_ai_decision(
            original_decision_id="dec_policy",
            original_action="BLOCK_TEMPORARY",
            original_confidence=0.75,
            new_action="ALLOW",
            reason="Override due to known issue with geolocation detection",
            reviewer_id="analyst_001",
            reviewer_role="Analyst",
            session_id="sess_policy",
            user_id="user_policy",
        )
        
        assert override.policy_impact is not None
        assert "rejected" in override.policy_impact.lower()
    
    def test_policy_version_recorded(self, override_handler, policy_rules):
        """Test that policy version is recorded."""
        override = override_handler.approve_ai_decision(
            original_decision_id="dec_version",
            original_action="CHALLENGE",
            original_confidence=0.65,
            reason="AI recommendation verified and approved by analyst",
            reviewer_id="analyst_001",
            reviewer_role="Analyst",
            session_id="sess_version",
            user_id="user_version",
        )
        
        assert override.policy_version == policy_rules.metadata.version


class TestTrainingFeedbackControl:
    """Test training feedback control."""
    
    def test_training_feedback_disabled_by_policy(self, override_handler, policy_rules):
        """Test that training feedback is disabled per policy."""
        # Policy has allow_training_feedback: false
        assert policy_rules.human_override.allow_training_feedback is False
        
        override = override_handler.reject_ai_decision(
            original_decision_id="dec_training",
            original_action="BLOCK_TEMPORARY",
            original_confidence=0.75,
            new_action="ALLOW",
            reason="Customer verified, false positive from model",
            reviewer_id="analyst_001",
            reviewer_role="Analyst",
            session_id="sess_training",
            user_id="user_training",
        )
        
        # Override should inherit policy setting
        assert override.allow_training_feedback is False


class TestAccountability:
    """Test reviewer accountability."""
    
    def test_reviewer_info_recorded(self, override_handler):
        """Test that reviewer information is recorded."""
        override = override_handler.approve_ai_decision(
            original_decision_id="dec_accountability",
            original_action="CHALLENGE",
            original_confidence=0.65,
            reason="Verified and approved the AI recommendation",
            reviewer_id="analyst_jane_doe",
            reviewer_role="Senior Fraud Analyst",
            session_id="sess_123",
            user_id="user_123",
        )
        
        assert override.reviewer_id == "analyst_jane_doe"
        assert override.reviewer_role == "Senior Fraud Analyst"
    
    def test_reviewer_info_in_audit_log(self, override_handler, audit_logger):
        """Test that reviewer info appears in audit log."""
        override_handler.approve_ai_decision(
            original_decision_id="dec_audit_reviewer",
            original_action="CHALLENGE",
            original_confidence=0.65,
            reason="Verified and approved after review",
            reviewer_id="analyst_john_smith",
            reviewer_role="Fraud Analyst Level 2",
            session_id="sess_audit_rev",
            user_id="user_audit_rev",
        )
        
        entries = list(audit_logger.get_entries(event_type=AuditEventType.HUMAN_OVERRIDE))
        assert len(entries) == 1
        
        entry = entries[0]
        assert entry.metadata["reviewer_id"] == "analyst_john_smith"
        assert entry.metadata["reviewer_role"] == "Fraud Analyst Level 2"


class TestOverrideHistory:
    """Test override history retrieval."""
    
    def test_get_override_history(self, override_handler):
        """Test retrieving override history for a decision."""
        decision_id = "dec_history_test"
        
        # Create multiple overrides for same decision
        override_handler.reject_ai_decision(
            original_decision_id=decision_id,
            original_action="BLOCK_TEMPORARY",
            original_confidence=0.75,
            new_action="CHALLENGE",
            reason="Reducing severity, needs more investigation",
            reviewer_id="analyst_001",
            reviewer_role="Analyst",
            session_id="sess_1",
            user_id="user_1",
        )
        
        override_handler.modify_ai_decision(
            original_decision_id=decision_id,
            original_action="CHALLENGE",
            original_confidence=0.75,
            new_action="ALLOW",
            reason="After investigation, allowing the access",
            reviewer_id="analyst_002",
            reviewer_role="Senior Analyst",
            session_id="sess_1",
            user_id="user_1",
        )
        
        # Get history
        history = override_handler.get_override_history(decision_id)
        
        assert len(history) == 2
        assert history[0].override_type == OverrideType.REJECT
        assert history[1].override_type == OverrideType.MODIFY


class TestValidation:
    """Test input validation."""
    
    def test_invalid_override_type_rejected(self, audit_logger, policy_rules, policy_yaml_content):
        """Test that invalid override types are rejected."""
        import yaml
        
        # Create policy with limited override types
        modified_yaml = policy_yaml_content.replace(
            'allowed_override_types:\n    - "APPROVE"\n    - "REJECT"\n    - "MODIFY"\n    - "DEFER"',
            'allowed_override_types:\n    - "APPROVE"\n    - "REJECT"'
        )
        raw_config = yaml.safe_load(modified_yaml)
        limited_policy = PolicyRules.model_validate(raw_config)
        
        handler = HumanOverrideHandler(
            audit_logger=audit_logger,
            policy_rules=limited_policy,
        )
        
        # MODIFY is not allowed in this policy
        with pytest.raises(HumanOverrideError) as exc_info:
            handler.create_override(
                original_decision_id="dec_123",
                original_action="BLOCK_TEMPORARY",
                original_confidence=0.75,
                new_action="CHALLENGE",
                override_type=OverrideType.MODIFY,  # Not allowed
                reason="This should fail validation",
                reviewer_id="analyst_001",
                reviewer_role="Analyst",
                session_id="sess_123",
                user_id="user_123",
            )
        
        assert "not allowed" in str(exc_info.value).lower()
