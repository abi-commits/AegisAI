"""Unit tests for S3 audit store."""

import pytest
import json
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch

from aegis_ai.governance.schemas import AuditEntry, AuditEventType
from aegis_ai.governance.audit.s3_store import S3AuditStore


class TestS3AuditStore:
    """Test S3 audit store functionality."""
    
    @pytest.fixture
    def mock_s3_client(self):
        """Create mock S3 client."""
        return MagicMock()
    
    @pytest.fixture
    def s3_store(self, mock_s3_client):
        """Create S3 audit store with mocked client."""
        store = S3AuditStore(
            bucket_name="test-audit-bucket",
            prefix="audit-logs/",
            environment="test",
            enable_hash_chain=True,
        )
        store.s3_client = mock_s3_client
        return store
    
    def test_get_log_key_format(self, s3_store):
        """Test S3 key generation format."""
        key = s3_store._get_log_key(date="2026-01-29")
        assert key == "audit-logs/test/2026-01-29/audit.jsonl"
    
    def test_compute_hash_simple(self, s3_store):
        """Test hash computation."""
        data = "test data"
        hash1 = s3_store._compute_hash(data)
        hash2 = s3_store._compute_hash(data)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex length
    
    def test_compute_hash_with_chaining(self, s3_store):
        """Test hash chain computation."""
        prev_hash = "abc123"
        data1 = "first"
        data2 = "second"
        
        hash1 = s3_store._compute_hash(data1, prev_hash)
        hash2 = s3_store._compute_hash(data2, prev_hash)
        
        # Different data should produce different hashes even with same previous
        assert hash1 != hash2
    
    def test_append_entry_no_hash_chain(self, s3_store, mock_s3_client):
        """Test appending entry without hash chain."""
        s3_store.enable_hash_chain = False
        mock_s3_client.get_object.side_effect = s3_store.s3_client.exceptions.NoSuchKey()
        
        entry = AuditEntry(
            event_type=AuditEventType.DECISION,
            decision_id="dec_123",
            session_id="ses_456",
            user_id="usr_789",
            action="ALLOW",
            confidence_score=0.95,
            decided_by="AI",
            policy_version="1.0",
        )
        
        result = s3_store.append_entry(entry)
        
        assert result.decision_id == "dec_123"
        assert mock_s3_client.put_object.called
    
    def test_verify_integrity_passes(self, s3_store, mock_s3_client):
        """Test integrity verification passes for valid chain."""
        # Setup mock to return sample JSONL
        entry_dict = {
            "event_type": "decision",
            "decision_id": "dec_123",
            "entry_hash": "abc123",
            "previous_hash": None,
        }
        
        mock_s3_client.get_object.return_value = {
            "Body": MagicMock(read=lambda: json.dumps(entry_dict).encode())
        }
        
        # Should pass (we'll just verify it doesn't raise)
        result = s3_store.verify_integrity()
        assert result is True
    
    def test_get_entries_filters_by_decision_id(self, s3_store, mock_s3_client):
        """Test get_entries filters by decision_id."""
        entry1 = {
            "event_type": "decision",
            "decision_id": "dec_1",
            "session_id": "ses_1",
            "user_id": "usr_1",
            "timestamp": "2026-01-29T10:00:00",
        }
        entry2 = {
            "event_type": "decision",
            "decision_id": "dec_2",
            "session_id": "ses_1",
            "user_id": "usr_1",
            "timestamp": "2026-01-29T10:01:00",
        }
        
        jsonl_content = json.dumps(entry1) + "\n" + json.dumps(entry2) + "\n"
        mock_s3_client.get_object.return_value = {
            "Body": MagicMock(read=lambda: jsonl_content.encode())
        }
        
        # Should only return entry1
        entries = list(s3_store.get_entries(decision_id="dec_1"))
        assert len(entries) == 1
        assert entries[0].decision_id == "dec_1"
    
    def test_get_last_hash_returns_none_when_no_file(self, s3_store, mock_s3_client):
        """Test get_last_hash returns None when file doesn't exist."""
        mock_s3_client.get_object.side_effect = s3_store.s3_client.exceptions.NoSuchKey()
        
        result = s3_store.get_last_hash()
        assert result is None


class TestS3AuditStorePartitioning:
    """Test S3 audit store partitioning scheme."""
    
    def test_date_partitioning(self, mock_s3_client=None):
        """Test date-based partitioning."""
        store = S3AuditStore(
            bucket_name="test-bucket",
            environment="prod",
        )
        
        key1 = store._get_log_key(date="2026-01-28")
        key2 = store._get_log_key(date="2026-01-29")
        
        # Should have different dates
        assert "2026-01-28" in key1
        assert "2026-01-29" in key2
        assert key1 != key2
    
    def test_environment_partitioning(self):
        """Test environment-based partitioning."""
        store_prod = S3AuditStore(
            bucket_name="test-bucket",
            environment="production",
        )
        store_dev = S3AuditStore(
            bucket_name="test-bucket",
            environment="development",
        )
        
        key_prod = store_prod._get_log_key()
        key_dev = store_dev._get_log_key()
        
        # Should have different environments
        assert "production" in key_prod
        assert "development" in key_dev
        assert key_prod != key_dev
