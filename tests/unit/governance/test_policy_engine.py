"""Unit tests for Policy Engine.

Tests that policies can veto AI actions and enforce governance rules.
"""

import pytest
import tempfile
import os
from pathlib import Path

from src.aegis_ai.governance.policies.engine import (
    PolicyEngine,
    PolicyViolationError,
)
from src.aegis_ai.governance.schemas import (
    PolicyDecision,
    PolicyViolationType,
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
    - "ACCOUNT_TERMINATION"

escalation:
  disagreement_threshold: 0.30
  consecutive_high_risk_limit: 3
  force_human_review:
    - "low_confidence"
    - "high_disagreement"
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
def temp_policy_file(policy_yaml_content):
    """Create a temporary policy file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(policy_yaml_content)
        temp_path = f.name
    yield temp_path
    os.unlink(temp_path)


@pytest.fixture
def policy_engine(temp_policy_file):
    """Create a PolicyEngine with test policies."""
    return PolicyEngine(policy_file=temp_policy_file)


class TestPolicyEngineInit:
    """Test PolicyEngine initialization."""
    
    def test_load_policies_from_file(self, policy_engine):
        """Test that policies load correctly from YAML."""
        assert policy_engine.policy_version == "1.0.0-test"
        assert policy_engine.rules.confidence.min_to_allow == 0.80
        assert policy_engine.rules.actions.permanent_block_allowed is False
    
    def test_file_not_found_raises_error(self):
        """Test that missing policy file raises error."""
        with pytest.raises(FileNotFoundError):
            PolicyEngine(policy_file="/nonexistent/path.yaml")


class TestActionValidation:
    """Test action validation rules."""
    
    def test_allowed_action_approved(self, policy_engine):
        """Test that allowed actions pass validation."""
        result = policy_engine.evaluate(
            proposed_action="ALLOW",
            confidence_score=0.90,
            risk_score=0.20,
            disagreement_score=0.10,
            user_id="user_123",
            session_id="sess_123",
        )
        assert result.is_approved
        assert result.approved_action == "ALLOW"
    
    def test_human_only_action_vetoed(self, policy_engine):
        """Test that human-only actions are vetoed."""
        result = policy_engine.evaluate(
            proposed_action="BLOCK_PERMANENT",
            confidence_score=0.99,
            risk_score=0.90,
            disagreement_score=0.0,
            user_id="user_123",
            session_id="sess_123",
        )
        assert result.is_vetoed
        assert any(v.violation_type == PolicyViolationType.HUMAN_ONLY_ACTION 
                   for v in result.violations)
    
    def test_unknown_action_vetoed(self, policy_engine):
        """Test that unknown actions are vetoed."""
        result = policy_engine.evaluate(
            proposed_action="DELETE_ACCOUNT",
            confidence_score=0.99,
            risk_score=0.50,
            disagreement_score=0.0,
            user_id="user_123",
            session_id="sess_123",
        )
        assert result.is_vetoed
        assert any(v.violation_type == PolicyViolationType.ACTION_NOT_ALLOWED 
                   for v in result.violations)


class TestConfidenceValidation:
    """Test confidence threshold validation."""
    
    def test_high_confidence_approved(self, policy_engine):
        """Test that high confidence passes."""
        result = policy_engine.evaluate(
            proposed_action="ALLOW",
            confidence_score=0.85,
            risk_score=0.20,
            disagreement_score=0.10,
            user_id="user_123",
            session_id="sess_123",
        )
        assert result.is_approved
    
    def test_low_confidence_escalates(self, policy_engine):
        """Test that low confidence triggers escalation."""
        result = policy_engine.evaluate(
            proposed_action="BLOCK_TEMPORARY",
            confidence_score=0.60,  # Below min_to_allow (0.80)
            risk_score=0.70,
            disagreement_score=0.10,
            user_id="user_123",
            session_id="sess_123",
        )
        assert result.requires_escalation
        assert any(v.violation_type == PolicyViolationType.CONFIDENCE_TOO_LOW 
                   for v in result.violations)
    
    def test_very_low_confidence_hard_stop(self, policy_engine):
        """Test that very low confidence is a hard stop."""
        result = policy_engine.evaluate(
            proposed_action="BLOCK_TEMPORARY",
            confidence_score=0.40,  # Below min_to_escalate (0.50)
            risk_score=0.70,
            disagreement_score=0.10,
            user_id="user_123",
            session_id="sess_123",
        )
        assert result.requires_escalation


class TestDisagreementValidation:
    """Test agent disagreement validation."""
    
    def test_low_disagreement_approved(self, policy_engine):
        """Test that low disagreement passes."""
        result = policy_engine.evaluate(
            proposed_action="ALLOW",
            confidence_score=0.90,
            risk_score=0.20,
            disagreement_score=0.20,  # Below threshold (0.30)
            user_id="user_123",
            session_id="sess_123",
        )
        assert result.is_approved
    
    def test_high_disagreement_escalates(self, policy_engine):
        """Test that high disagreement triggers escalation."""
        result = policy_engine.evaluate(
            proposed_action="ALLOW",
            confidence_score=0.90,
            risk_score=0.20,
            disagreement_score=0.50,  # Above threshold (0.30)
            user_id="user_123",
            session_id="sess_123",
        )
        assert result.requires_escalation
        assert any(v.violation_type == PolicyViolationType.DISAGREEMENT_TOO_HIGH 
                   for v in result.violations)


class TestRiskValidation:
    """Test risk threshold validation."""
    
    def test_critical_risk_escalates(self, policy_engine):
        """Test that critical risk forces escalation."""
        result = policy_engine.evaluate(
            proposed_action="BLOCK_TEMPORARY",
            confidence_score=0.99,
            risk_score=0.96,  # Above critical (0.95)
            disagreement_score=0.0,
            user_id="user_123",
            session_id="sess_123",
        )
        assert result.requires_escalation
        assert any(v.violation_type == PolicyViolationType.CRITICAL_RISK 
                   for v in result.violations)
    
    def test_action_recommendation_for_risk(self, policy_engine):
        """Test risk-based action recommendations."""
        assert policy_engine.get_action_for_risk(0.10) == "ALLOW"
        assert policy_engine.get_action_for_risk(0.50) == "CHALLENGE"
        assert policy_engine.get_action_for_risk(0.80) == "BLOCK_TEMPORARY"
        assert policy_engine.get_action_for_risk(0.96) == "ESCALATE"


class TestRateLimits:
    """Test rate limiting validation."""
    
    def test_within_rate_limit_approved(self, policy_engine):
        """Test that actions within rate limit pass."""
        for i in range(5):  # Max is 5 per day
            result = policy_engine.evaluate(
                proposed_action="ALLOW",
                confidence_score=0.90,
                risk_score=0.20,
                disagreement_score=0.10,
                user_id="user_rate_test",
                session_id=f"sess_{i}",
            )
            assert result.is_approved
    
    def test_exceeding_rate_limit_vetoed(self, policy_engine):
        """Test that exceeding rate limit is vetoed."""
        # First exhaust the limit
        for i in range(5):
            policy_engine.evaluate(
                proposed_action="ALLOW",
                confidence_score=0.90,
                risk_score=0.20,
                disagreement_score=0.10,
                user_id="user_rate_limit",
                session_id=f"sess_{i}",
            )
        
        # This should be vetoed
        result = policy_engine.evaluate(
            proposed_action="ALLOW",
            confidence_score=0.90,
            risk_score=0.20,
            disagreement_score=0.10,
            user_id="user_rate_limit",
            session_id="sess_6",
        )
        assert result.is_vetoed
        assert any(v.violation_type == PolicyViolationType.RATE_LIMIT_EXCEEDED 
                   for v in result.violations)


class TestConsecutiveHighRisk:
    """Test consecutive high-risk detection."""
    
    def test_consecutive_high_risk_escalates(self, policy_engine):
        """Test that consecutive high-risk decisions trigger escalation."""
        user_id = "user_high_risk"
        
        # First two high-risk decisions (limit is 3)
        for i in range(2):
            result = policy_engine.evaluate(
                proposed_action="BLOCK_TEMPORARY",
                confidence_score=0.90,
                risk_score=0.80,  # High risk
                disagreement_score=0.10,
                user_id=user_id,
                session_id=f"sess_{i}",
            )
            # These should pass but not the third
        
        # Third consecutive high-risk should escalate
        result = policy_engine.evaluate(
            proposed_action="BLOCK_TEMPORARY",
            confidence_score=0.90,
            risk_score=0.80,
            disagreement_score=0.10,
            user_id=user_id,
            session_id="sess_3",
        )
        assert result.requires_escalation
        assert any(v.violation_type == PolicyViolationType.CONSECUTIVE_HIGH_RISK 
                   for v in result.violations)


class TestEnforcement:
    """Test strict enforcement mode."""
    
    def test_enforce_raises_on_violation(self, policy_engine):
        """Test that enforce() raises exception on veto."""
        with pytest.raises(PolicyViolationError) as exc_info:
            policy_engine.enforce(
                proposed_action="BLOCK_PERMANENT",
                confidence_score=0.99,
                risk_score=0.90,
                disagreement_score=0.0,
                user_id="user_123",
                session_id="sess_123",
                raise_on_violation=True,
            )
        
        assert len(exc_info.value.violations) > 0
    
    def test_enforce_returns_result_when_no_raise(self, policy_engine):
        """Test that enforce() returns result without raising."""
        result = policy_engine.enforce(
            proposed_action="BLOCK_PERMANENT",
            confidence_score=0.99,
            risk_score=0.90,
            disagreement_score=0.0,
            user_id="user_123",
            session_id="sess_123",
            raise_on_violation=False,
        )
        assert result.is_vetoed


class TestPolicyReload:
    """Test policy reloading."""
    
    def test_reload_policies(self, policy_engine, temp_policy_file):
        """Test that policies can be reloaded."""
        initial_version = policy_engine.policy_version
        
        # Modify the policy file
        with open(temp_policy_file, 'r') as f:
            content = f.read()
        content = content.replace('version: "1.0.0-test"', 'version: "1.0.1-test"')
        with open(temp_policy_file, 'w') as f:
            f.write(content)
        
        # Reload
        policy_engine.reload_policies()
        
        assert policy_engine.policy_version == "1.0.1-test"


class TestTracking:
    """Test tracking and reset functionality."""
    
    def test_reset_tracking_for_user(self, policy_engine):
        """Test resetting tracking for a specific user."""
        user_id = "user_reset"
        
        # Create some tracking data
        for i in range(3):
            policy_engine.evaluate(
                proposed_action="ALLOW",
                confidence_score=0.90,
                risk_score=0.20,
                disagreement_score=0.10,
                user_id=user_id,
                session_id=f"sess_{i}",
            )
        
        # Reset for this user
        policy_engine.reset_tracking(user_id=user_id)
        
        # Should be able to make 5 more actions
        for i in range(5):
            result = policy_engine.evaluate(
                proposed_action="ALLOW",
                confidence_score=0.90,
                risk_score=0.20,
                disagreement_score=0.10,
                user_id=user_id,
                session_id=f"sess_new_{i}",
            )
            assert result.is_approved
    
    def test_reset_all_tracking(self, policy_engine):
        """Test resetting all tracking."""
        # Create tracking for multiple users
        for user_num in range(3):
            for i in range(3):
                policy_engine.evaluate(
                    proposed_action="ALLOW",
                    confidence_score=0.90,
                    risk_score=0.20,
                    disagreement_score=0.10,
                    user_id=f"user_{user_num}",
                    session_id=f"sess_{i}",
                )
        
        # Reset all
        policy_engine.reset_tracking()
        
        # All users should have fresh limits
        for user_num in range(3):
            result = policy_engine.evaluate(
                proposed_action="ALLOW",
                confidence_score=0.90,
                risk_score=0.20,
                disagreement_score=0.10,
                user_id=f"user_{user_num}",
                session_id="sess_fresh",
            )
            assert result.is_approved
