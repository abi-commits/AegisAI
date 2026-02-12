"""Unit tests for DynamoDB operational metadata store."""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch

from aegis_ai.governance.audit.dynamodb_metadata import DynamoDBOperationalMetadata


class TestDynamoDBOperationalMetadata:
    """Test DynamoDB operational metadata store."""
    
    @pytest.fixture
    def mock_dynamodb_table(self):
        """Create mock DynamoDB table."""
        return MagicMock()
    
    @pytest.fixture
    def metadata_store(self, mock_dynamodb_table):
        """Create metadata store with mocked table."""
        with patch("boto3.resource") as mock_resource:
            mock_resource.return_value.Table.return_value = mock_dynamodb_table
            store = DynamoDBOperationalMetadata(
                table_name="test-metadata",
            )
            store.table = mock_dynamodb_table
            return store
    
    def test_put_decision(self, metadata_store, mock_dynamodb_table):
        """Test storing decision metadata."""
        metadata_store.put_decision(
            decision_id="dec_123",
            session_id="ses_456",
            user_id="usr_789",
            action="ALLOW",
            confidence_score=0.95,
            decided_by="AI",
            policy_version="1.0",
        )
        
        assert mock_dynamodb_table.put_item.called
        call_args = mock_dynamodb_table.put_item.call_args
        item = call_args[1]["Item"]
        
        assert item["decision_id"] == "dec_123"
        assert item["entity_type"] == "DECISION"
        assert item["action"] == "ALLOW"
        assert float(item["confidence_score"]) == 0.95
    
    def test_get_decision(self, metadata_store, mock_dynamodb_table):
        """Test retrieving decision metadata."""
        # Mock response
        mock_dynamodb_table.get_item.return_value = {
            "Item": {
                "pk": "PK#DECISION#dec_123",
                "sk": "SK#DECISION#",
                "decision_id": "dec_123",
                "action": "ALLOW",
                "confidence_score": Decimal("0.95"),
                "timestamp": "2026-01-29T10:00:00",
            }
        }
        
        result = metadata_store.get_decision("dec_123")
        
        assert result is not None
        assert result["decision_id"] == "dec_123"
        assert result["confidence_score"] == 0.95  # Should be converted from Decimal
    
    def test_query_decisions_by_user(self, metadata_store, mock_dynamodb_table):
        """Test querying decisions by user (via GSI)."""
        mock_dynamodb_table.query.return_value = {
            "Items": [
                {
                    "decision_id": "dec_1",
                    "user_id": "usr_789",
                    "action": "ALLOW",
                    "confidence_score": Decimal("0.95"),
                },
                {
                    "decision_id": "dec_2",
                    "user_id": "usr_789",
                    "action": "BLOCK",
                    "confidence_score": Decimal("0.85"),
                }
            ]
        }
        
        results = metadata_store.query_decisions_by_user("usr_789")
        
        assert len(results) == 2
        assert all(float(r["confidence_score"]) <= 1.0 for r in results)
    
    def test_create_escalation(self, metadata_store, mock_dynamodb_table):
        """Test creating escalation record."""
        escalation_id = metadata_store.create_escalation(
            decision_id="dec_123",
            escalation_type="POLICY",
            reason="Policy violation threshold exceeded",
            escalated_to="risk_team",
        )
        
        assert escalation_id.startswith("esc_")
        assert mock_dynamodb_table.put_item.called
        
        call_args = mock_dynamodb_table.put_item.call_args
        item = call_args[1]["Item"]
        
        assert item["entity_type"] == "ESCALATION"
        assert item["status"] == "PENDING"
        assert item["decision_id"] == "dec_123"
    
    def test_update_escalation_status(self, metadata_store, mock_dynamodb_table):
        """Test updating escalation status."""
        result = metadata_store.update_escalation_status(
            escalation_id="esc_123",
            status="RESOLVED",
            resolution="Approved by analyst",
            resolved_by="analyst_001",
        )
        
        assert result is True
        assert mock_dynamodb_table.update_item.called
        
        call_args = mock_dynamodb_table.update_item.call_args
        expr_values = call_args[1]["ExpressionAttributeValues"]
        
        assert expr_values[":status"] == "RESOLVED"
        assert expr_values[":resolution"] == "Approved by analyst"
    
    def test_create_override_reference(self, metadata_store, mock_dynamodb_table):
        """Test creating override reference."""
        metadata_store.create_override_reference(
            override_id="ovr_123",
            original_decision_id="dec_456",
            reviewer_id="rev_789",
            override_type="APPROVE",
            reason="False positive",
        )
        
        assert mock_dynamodb_table.put_item.called
        call_args = mock_dynamodb_table.put_item.call_args
        item = call_args[1]["Item"]
        
        assert item["entity_type"] == "OVERRIDE"
        assert item["override_type"] == "APPROVE"
        assert item["original_decision_id"] == "dec_456"
    
    def test_get_override_for_decision(self, metadata_store, mock_dynamodb_table):
        """Test retrieving override for a decision."""
        mock_dynamodb_table.query.return_value = {
            "Items": [
                {
                    "override_id": "ovr_123",
                    "original_decision_id": "dec_456",
                    "override_type": "APPROVE",
                }
            ]
        }
        
        result = metadata_store.get_override_for_decision("dec_456")
        
        assert result is not None
        assert result["override_id"] == "ovr_123"
    
    def test_get_overrides_by_reviewer(self, metadata_store, mock_dynamodb_table):
        """Test querying overrides by reviewer (via GSI)."""
        mock_dynamodb_table.query.return_value = {
            "Items": [
                {
                    "override_id": "ovr_1",
                    "reviewer_id": "rev_789",
                    "override_type": "APPROVE",
                },
                {
                    "override_id": "ovr_2",
                    "reviewer_id": "rev_789",
                    "override_type": "REJECT",
                }
            ]
        }
        
        results = metadata_store.get_overrides_by_reviewer("rev_789")
        
        assert len(results) == 2
        assert all(r["reviewer_id"] == "rev_789" for r in results)


class TestDynamoDBMetadataSchema:
    """Test DynamoDB schema and indexing."""
    
    def test_partition_key_format(self):
        """Test partition key generation."""
        store = DynamoDBOperationalMetadata(table_name="test")
        
        # Decision key
        dec_key = "PK#DECISION#dec_123"
        assert dec_key.startswith("PK#DECISION#")
        
        # Escalation key
        esc_key = "PK#ESCALATION#esc_456"
        assert esc_key.startswith("PK#ESCALATION#")
        
        # Override key
        ovr_key = "PK#OVERRIDE#ovr_789"
        assert ovr_key.startswith("PK#OVERRIDE#")
    
    def test_gsi_keys_enable_fast_queries(self):
        """Test GSI keys support fast lookups."""
        store = DynamoDBOperationalMetadata(table_name="test")
        
        # GSI1 for user queries (DECISION#user_id)
        gsi1_pk = "DECISION#usr_789"
        assert gsi1_pk.startswith("DECISION#")
        
        # GSI2 for session queries (SESSION#ses_456)
        gsi2_pk = "SESSION#ses_456"
        assert gsi2_pk.startswith("SESSION#")
        
        # These should be queryable independently
        assert gsi1_pk != gsi2_pk
    
    def test_ttl_timestamp_generation(self):
        """Test TTL timestamp is in future."""
        store = DynamoDBOperationalMetadata(
            table_name="test",
            enable_ttl=True,
            ttl_days=90,
        )
        
        ttl_ts = store._get_ttl_timestamp()
        now_ts = int(datetime.now(timezone.utc).timestamp())
        
        # TTL should be in future
        assert ttl_ts > now_ts
        
        # Should be approximately 90 days from now
        days_diff = (ttl_ts - now_ts) / (24 * 3600)
        assert 89 < days_diff < 91
