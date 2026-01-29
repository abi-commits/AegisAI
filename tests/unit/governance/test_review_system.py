"""Tests for Human-in-the-Loop Review System (Layer 6)."""

import pytest
import json
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal
import uuid

from aegis_ai.governance.review import (
    CaseStatus,
    ReviewAction,
    CaseManager,
    ReviewUIBackend,
)


class TestCaseStatus:
    """Tests for CaseStatus enum."""
    
    def test_case_statuses_exist(self):
        """Test that all required statuses exist."""
        assert CaseStatus.PENDING
        assert CaseStatus.IN_REVIEW
        assert CaseStatus.APPROVED
        assert CaseStatus.REJECTED
        assert CaseStatus.OVERRIDDEN
        assert CaseStatus.DEFERRED
        assert CaseStatus.ESCALATED


class TestReviewAction:
    """Tests for ReviewAction enum."""
    
    def test_review_actions_exist(self):
        """Test that all required actions exist."""
        assert ReviewAction.APPROVE
        assert ReviewAction.REJECT
        assert ReviewAction.OVERRIDE
        assert ReviewAction.COMMENT
        assert ReviewAction.DEFER
        assert ReviewAction.ESCALATE


class TestCaseManager:
    """Tests for CaseManager."""
    
    @patch("aegis_ai.governance.review.boto3.client")
    def test_create_case(self, mock_boto3_client):
        """Test creating a review case."""
        mock_s3 = MagicMock()
        mock_dynamodb = MagicMock()
        
        def client_factory(service_name, **kwargs):
            if service_name == "s3":
                return mock_s3
            elif service_name == "dynamodb":
                return mock_dynamodb
        
        mock_boto3_client.side_effect = client_factory
        
        manager = CaseManager(
            dynamodb_table="cases",
            s3_bucket="evidence",
        )
        
        evidence = {
            "decision_id": "dec-123",
            "input_features": {"score": 0.8},
            "ai_decision": "approve",
            "confidence": 0.85,
        }
        
        case_id = manager.create_case(
            decision_id="dec-123",
            case_type="override_review",
            evidence=evidence,
            priority="high",
        )
        
        assert case_id is not None
        # Verify S3 put_object was called for evidence
        assert mock_s3.put_object.called
        # Verify DynamoDB put_item was called for case
        assert mock_dynamodb.put_item.called
    
    @patch("aegis_ai.governance.review.boto3.client")
    def test_add_review_action_approve(self, mock_boto3_client):
        """Test approving a case."""
        mock_dynamodb = MagicMock()
        mock_boto3_client.return_value = mock_dynamodb
        
        manager = CaseManager(
            dynamodb_table="cases",
            s3_bucket="evidence",
        )
        
        result = manager.add_review_action(
            case_id="case-123",
            action=ReviewAction.APPROVE,
            reviewer_id="user-456",
            reviewer_role="analyst",
            comment="Looks good.",
        )
        
        assert result is True
        assert mock_dynamodb.update_item.called
    
    @patch("aegis_ai.governance.review.boto3.client")
    def test_add_review_action_override_requires_comment(self, mock_boto3_client):
        """Test that override action requires comment."""
        mock_dynamodb = MagicMock()
        mock_boto3_client.return_value = mock_dynamodb
        
        manager = CaseManager(
            dynamodb_table="cases",
            s3_bucket="evidence",
        )
        
        # Override without comment should fail
        with pytest.raises(ValueError):
            manager.add_review_action(
                case_id="case-123",
                action=ReviewAction.OVERRIDE,
                reviewer_id="user-456",
                reviewer_role="supervisor",
                # No comment
            )
    
    @patch("aegis_ai.governance.review.boto3.client")
    def test_add_review_action_override_requires_new_action(self, mock_boto3_client):
        """Test that override action requires new_action."""
        mock_dynamodb = MagicMock()
        mock_boto3_client.return_value = mock_dynamodb
        
        manager = CaseManager(
            dynamodb_table="cases",
            s3_bucket="evidence",
        )
        
        # Override without new_action should fail
        with pytest.raises(ValueError):
            manager.add_review_action(
                case_id="case-123",
                action=ReviewAction.OVERRIDE,
                reviewer_id="user-456",
                reviewer_role="supervisor",
                comment="Changing this decision.",
                # No new_action
            )
    
    @patch("aegis_ai.governance.review.boto3.client")
    def test_add_review_action_override_with_required_fields(self, mock_boto3_client):
        """Test override action with required fields."""
        mock_dynamodb = MagicMock()
        mock_boto3_client.return_value = mock_dynamodb
        
        manager = CaseManager(
            dynamodb_table="cases",
            s3_bucket="evidence",
        )
        
        result = manager.add_review_action(
            case_id="case-123",
            action=ReviewAction.OVERRIDE,
            reviewer_id="user-456",
            reviewer_role="supervisor",
            comment="Changing to reject due to suspicious pattern.",
            new_action="reject",
        )
        
        assert result is True
    
    @patch("aegis_ai.governance.review.boto3.client")
    def test_get_case(self, mock_boto3_client):
        """Test retrieving a case."""
        mock_dynamodb = MagicMock()
        mock_boto3_client.return_value = mock_dynamodb
        
        case_data = {
            "pk": {"S": "PK#CASE#case-123"},
            "sk": {"S": "SK#CASE#2026-01-28T10:00:00Z"},
            "case_id": {"S": "case-123"},
            "decision_id": {"S": "dec-123"},
            "status": {"S": "PENDING"},
            "case_type": {"S": "override_review"},
            "priority": {"S": "high"},
            "created_at": {"S": "2026-01-28T10:00:00Z"},
            "history": {"L": []},
        }
        
        mock_dynamodb.get_item.return_value = {"Item": case_data}
        
        manager = CaseManager(
            dynamodb_table="cases",
            s3_bucket="evidence",
        )
        
        case = manager.get_case("case-123")
        
        assert case is not None
        assert case["case_id"] == "case-123"
        assert case["status"] == "PENDING"
    
    @patch("aegis_ai.governance.review.boto3.client")
    def test_get_pending_cases(self, mock_boto3_client):
        """Test querying pending cases."""
        mock_dynamodb = MagicMock()
        mock_boto3_client.return_value = mock_dynamodb
        
        mock_dynamodb.query.return_value = {
            "Items": [
                {
                    "case_id": {"S": "case-1"},
                    "status": {"S": "PENDING"},
                    "priority": {"S": "high"},
                },
                {
                    "case_id": {"S": "case-2"},
                    "status": {"S": "PENDING"},
                    "priority": {"S": "medium"},
                },
            ],
        }
        
        manager = CaseManager(
            dynamodb_table="cases",
            s3_bucket="evidence",
        )
        
        cases = manager.get_pending_cases(limit=10)
        
        assert len(cases) == 2
        assert mock_dynamodb.query.called
    
    @patch("aegis_ai.governance.review.boto3.client")
    def test_get_user_cases(self, mock_boto3_client):
        """Test querying cases for a specific user."""
        mock_dynamodb = MagicMock()
        mock_boto3_client.return_value = mock_dynamodb
        
        mock_dynamodb.query.return_value = {
            "Items": [
                {
                    "case_id": {"S": "case-1"},
                    "reviewer_id": {"S": "user-456"},
                },
                {
                    "case_id": {"S": "case-2"},
                    "reviewer_id": {"S": "user-456"},
                },
            ],
        }
        
        manager = CaseManager(
            dynamodb_table="cases",
            s3_bucket="evidence",
        )
        
        cases = manager.get_user_cases("user-456", limit=10)
        
        assert len(cases) == 2


class TestReviewUIBackend:
    """Tests for ReviewUIBackend."""
    
    @patch("aegis_ai.governance.review.boto3.client")
    def test_get_review_dashboard(self, mock_boto3_client):
        """Test getting review dashboard data."""
        mock_dynamodb = MagicMock()
        
        def client_factory(service_name, **kwargs):
            if service_name == "dynamodb":
                return mock_dynamodb
        
        mock_boto3_client.side_effect = client_factory
        
        # Mock query results
        mock_dynamodb.query.return_value = {
            "Count": 5,
            "Items": [
                {"case_id": {"S": "case-1"}, "priority": {"S": "high"}},
            ] * 5,
        }
        
        mock_dynamodb.scan.return_value = {
            "Items": [
                {"status": {"S": "APPROVED"}},
                {"status": {"S": "REJECTED"}},
                {"status": {"S": "OVERRIDDEN"}},
            ],
        }
        
        backend = ReviewUIBackend(
            dynamodb_table="cases",
            s3_bucket="evidence",
        )
        
        dashboard = backend.get_review_dashboard()
        
        assert "pending_count" in dashboard
        assert dashboard["pending_count"] > 0
        assert "recent_cases" in dashboard
    
    @patch("aegis_ai.governance.review.boto3.client")
    def test_submit_review(self, mock_boto3_client):
        """Test submitting a review action."""
        mock_dynamodb = MagicMock()
        mock_boto3_client.return_value = mock_dynamodb
        
        backend = ReviewUIBackend(
            dynamodb_table="cases",
            s3_bucket="evidence",
        )
        
        result = backend.submit_review(
            case_id="case-123",
            action="APPROVE",
            comment="OK to proceed.",
            reviewer_id="user-456",
            reviewer_role="analyst",
        )
        
        assert result is not None
        assert "action_id" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
