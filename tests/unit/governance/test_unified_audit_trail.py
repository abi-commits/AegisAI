"""Unit tests for unified audit trail."""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch

from aegis_ai.governance.audit.unified_trail import UnifiedAuditTrail
from aegis_ai.governance.schemas import AuditEventType


class TestUnifiedAuditTrail:
    """Test unified audit trail with S3 + DynamoDB."""
    
    @pytest.fixture
    def mock_audit_logger(self):
        """Create mock audit logger."""
        logger = MagicMock()
        logger.log_decision.return_value = MagicMock(
            decision_id="dec_123",
            timestamp=datetime.now(timezone.utc),
        )
        logger.log_policy_violation.return_value = MagicMock(
            timestamp=datetime.now(timezone.utc),
        )
        logger.log_human_override.return_value = MagicMock(
            timestamp=datetime.now(timezone.utc),
        )
        logger.log_escalation.return_value = MagicMock(
            decision_id="dec_123",
            escalation_id="esc_456",
            timestamp=datetime.now(timezone.utc),
        )
        return logger
    
    @pytest.fixture
    def mock_dynamodb_store(self):
        """Create mock DynamoDB store."""
        store = MagicMock()
        store.health_check.return_value = True
        return store
    
    @pytest.fixture
    def unified_trail(self, mock_audit_logger, mock_dynamodb_store):
        """Create unified audit trail with mocks."""
        trail = UnifiedAuditTrail(
            audit_logger=mock_audit_logger,
            use_dynamodb=True,
        )
        trail.dynamodb_metadata = mock_dynamodb_store
        return trail
    
    def test_log_decision_writes_to_both_stores(self, unified_trail, mock_audit_logger, mock_dynamodb_store):
        """Test decision is logged to both S3 and DynamoDB."""
        unified_trail.log_decision(
            decision_id="dec_123",
            session_id="ses_456",
            user_id="usr_789",
            action="ALLOW",
            confidence_score=0.95,
            decided_by="AI",
            policy_version="1.0",
        )
        
        # Should call both stores
        assert mock_audit_logger.log_decision.called
        assert mock_dynamodb_store.put_decision.called
    
    def test_log_human_override_writes_to_both_stores(self, unified_trail, mock_audit_logger, mock_dynamodb_store):
        """Test override is logged to both stores."""
        unified_trail.log_human_override(
            override_id="ovr_123",
            original_decision_id="dec_456",
            original_action="BLOCK",
            original_confidence=0.85,
            new_action="ALLOW",
            override_type="APPROVE",
            reason="False positive",
            reviewer_id="rev_789",
            reviewer_role="analyst",
            session_id="ses_001",
            user_id="usr_002",
        )
        
        # Should call both stores
        assert mock_audit_logger.log_human_override.called
        assert mock_dynamodb_store.create_override_reference.called
    
    def test_log_escalation_writes_to_both_stores(self, unified_trail, mock_audit_logger, mock_dynamodb_store):
        """Test escalation is logged to both stores."""
        escalation_id, entry = unified_trail.log_escalation(
            decision_id="dec_123",
            escalation_type="POLICY",
            reason="High risk detected",
            escalated_to="risk_team",
            session_id="ses_456",
            user_id="usr_789",
        )
        
        # Should call both stores
        assert mock_audit_logger.log_escalation.called
        assert mock_dynamodb_store.create_escalation.called
        
        # Should return escalation_id and entry
        assert escalation_id is not None
        assert entry is not None
    
    def test_get_decision_by_id_uses_dynamodb(self, unified_trail, mock_dynamodb_store):
        """Test get_decision_by_id queries DynamoDB."""
        expected_result = {
            "decision_id": "dec_123",
            "action": "ALLOW",
            "confidence_score": 0.95,
        }
        mock_dynamodb_store.get_decision.return_value = expected_result
        
        result = unified_trail.get_decision_by_id("dec_123")
        
        assert result == expected_result
        assert mock_dynamodb_store.get_decision.called
    
    def test_get_user_decisions_uses_dynamodb(self, unified_trail, mock_dynamodb_store):
        """Test get_user_decisions queries DynamoDB GSI."""
        expected_results = [
            {"decision_id": "dec_1", "action": "ALLOW"},
            {"decision_id": "dec_2", "action": "BLOCK"},
        ]
        mock_dynamodb_store.query_decisions_by_user.return_value = expected_results
        
        results = unified_trail.get_user_decisions("usr_789")
        
        assert len(results) == 2
        assert mock_dynamodb_store.query_decisions_by_user.called
    
    def test_get_override_for_decision(self, unified_trail, mock_dynamodb_store):
        """Test get_override_for_decision queries DynamoDB."""
        expected_override = {
            "override_id": "ovr_123",
            "original_decision_id": "dec_456",
            "override_type": "APPROVE",
        }
        mock_dynamodb_store.get_override_for_decision.return_value = expected_override
        
        result = unified_trail.get_override_for_decision("dec_456")
        
        assert result == expected_override
        assert mock_dynamodb_store.get_override_for_decision.called
    
    def test_health_check(self, unified_trail, mock_audit_logger, mock_dynamodb_store):
        """Test health check returns status of all components."""
        health = unified_trail.health_check()
        
        assert "audit_logger" in health
        assert "dynamodb" in health
        assert health["dynamodb"] is True
    
    def test_graceful_degradation_without_dynamodb(self, mock_audit_logger):
        """Test unified trail works without DynamoDB."""
        trail = UnifiedAuditTrail(
            audit_logger=mock_audit_logger,
            use_dynamodb=False,
        )
        
        # Should still log to audit logger
        trail.log_decision(
            decision_id="dec_123",
            session_id="ses_456",
            user_id="usr_789",
            action="ALLOW",
            confidence_score=0.95,
            decided_by="AI",
            policy_version="1.0",
        )
        
        assert mock_audit_logger.log_decision.called
    
    def test_dynamodb_init_failure_doesnt_crash(self, mock_audit_logger):
        """Test unified trail handles DynamoDB init failure gracefully."""
        with patch("src.aegis_ai.governance.audit.unified_trail.create_dynamodb_metadata_store") as mock_create:
            mock_create.side_effect = ValueError("DynamoDB not available")
            
            # Should not raise
            trail = UnifiedAuditTrail(
                audit_logger=mock_audit_logger,
                use_dynamodb=True,
            )
            
            # Should fall back to audit logger only
            assert trail.use_dynamodb is False
    
    def test_update_escalation_status(self, unified_trail, mock_dynamodb_store):
        """Test updating escalation status."""
        mock_dynamodb_store.update_escalation_status.return_value = True
        
        result = unified_trail.update_escalation_status(
            escalation_id="esc_123",
            status="RESOLVED",
            resolution="Approved",
            resolved_by="analyst",
        )
        
        assert result is True
        assert mock_dynamodb_store.update_escalation_status.called


class TestUnifiedAuditTrailIntegration:
    """Integration tests for unified audit trail."""
    
    def test_end_to_end_decision_flow(self, mock_audit_logger=None):
        """Test complete decision flow through unified trail."""
        mock_logger = MagicMock()
        mock_logger.log_decision.return_value = MagicMock(
            decision_id="dec_123",
            timestamp=datetime.now(timezone.utc),
        )
        
        trail = UnifiedAuditTrail(
            audit_logger=mock_logger,
            use_dynamodb=False,
        )
        
        # Log initial decision
        entry = trail.log_decision(
            decision_id="dec_123",
            session_id="ses_456",
            user_id="usr_789",
            action="BLOCK",
            confidence_score=0.75,
            decided_by="AI",
            policy_version="1.0",
            metadata={"risk_score": 0.8},
        )
        
        # Then escalate it
        escalation_id, esc_entry = trail.log_escalation(
            decision_id="dec_123",
            escalation_type="MANUAL",
            reason="For manual review",
            escalated_to="risk_team",
            session_id="ses_456",
            user_id="usr_789",
        )
        
        assert entry is not None
        assert escalation_id is not None
        assert esc_entry is not None
