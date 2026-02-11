"""Unit tests for S3 audit store."""

import pytest
import json
import re
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch

from aegis_ai.governance.schemas import AuditEntry, AuditEventType
from aegis_ai.governance.audit.s3_store import S3AuditStore


class TestS3AuditStore:
    """Test S3 audit store functionality."""

    @pytest.fixture
    def mock_boto3(self):
        with patch("aegis_ai.governance.audit.s3_store.boto3") as mock:
            yield mock
    
    @pytest.fixture
    def s3_store(self, mock_boto3):
        """Create S3 audit store with mocked client."""
        # Setup mock client to avoid 403 on init
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_boto3.Session.return_value.client.return_value = mock_client
        
        store = S3AuditStore(
            bucket_name="test-audit-bucket",
            prefix="audit-logs/",
            environment="test",
            enable_hash_chain=True,
        )
        return store
    
    def test_get_unique_key_format(self, s3_store):
        """Test S3 key generation format."""
        key = s3_store._get_unique_key(date="2026-01-29", decision_id="dec-123")
        # Format: audit-logs/test/2026-01-29/{ts}_{uuid}_dec-123.json
        assert key.startswith("audit-logs/test/2026-01-29/")
        assert key.endswith("_dec-123.json")
        assert len(key.split("/")) == 4  # prefix, env, date, filename
    
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
    
    def test_append_entry_no_hash_chain(self, s3_store):
        """Test appending entry without hash chain."""
        s3_store.enable_hash_chain = False
        
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
        assert s3_store.s3_client.put_object.called
        call_args = s3_store.s3_client.put_object.call_args[1]
        assert "dec_123" in call_args["Key"]
    
    def test_verify_integrity_passes(self, s3_store):
        """Test integrity verification passes for valid chain."""
        # Mock paginator for list_objects_v2
        mock_paginator = MagicMock()
        s3_store.s3_client.get_paginator.return_value = mock_paginator
        
        # Simulate one file in S3
        mock_paginator.paginate.return_value = [{
            "Contents": [{"Key": "path/to/log.json"}]
        }]

        # Setup mock to return sample content
        entry_dict = {
            "event_type": "decision",
            "decision_id": "dec_123",
            "entry_hash": "", # Will fill below
            "previous_hash": None,
        }
        # Pre-compute valid hash
        entry_copy = entry_dict.copy()
        entry_copy.pop("entry_hash")
        computed = s3_store._compute_hash(json.dumps(entry_copy, default=str), None)
        entry_dict["entry_hash"] = computed

        s3_store.s3_client.get_object.return_value = {
            "Body": MagicMock(read=lambda: json.dumps(entry_dict).encode())
        }
        
        # Should pass
        result = s3_store.verify_integrity()
        assert result is True
    
    def test_get_entries_filters_by_decision_id(self, s3_store):
        """Test get_entries filters by decision_id."""
        entry1 = {
            "event_type": "decision",
            "decision_id": "dec_1",
            "session_id": "ses_1",
            "user_id": "usr_1",
            "timestamp": "2026-01-29T10:00:00",
            "action": "ALLOW",
            "confidence_score": 0.9,
            "decided_by": "AI",
            "policy_version": "1.0",
        }
        entry2 = {
            "event_type": "decision",
            "decision_id": "dec_2",
            "session_id": "ses_1",
            "user_id": "usr_1",
            "timestamp": "2026-01-29T10:01:00",
            "action": "BLOCK",
            "confidence_score": 0.8,
            "decided_by": "POLICY",
            "policy_version": "1.0",
        }
        
        # Mock paginator
        mock_paginator = MagicMock()
        s3_store.s3_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{
            "Contents": [
                {"Key": "log1.json"},
                {"Key": "log2.json"}
            ]
        }]
        
        # Mock get_object side effect
        def get_object_side_effect(**kwargs):
            key = kwargs["Key"]
            if key == "log1.json":
                return {"Body": MagicMock(read=lambda: json.dumps(entry1).encode())}
            else:
                return {"Body": MagicMock(read=lambda: json.dumps(entry2).encode())}
        
        s3_store.s3_client.get_object.side_effect = get_object_side_effect
        
        # Should only return entry1
        entries = list(s3_store.get_entries(decision_id="dec_1"))
        assert len(entries) == 1
        assert entries[0].decision_id == "dec_1"
    
    def test_get_last_hash_returns_none_when_no_file(self, s3_store):
        """Test get_last_hash returns None."""
        result = s3_store.get_last_hash()
        assert result is None


class TestS3AuditStorePartitioning:
    """Test S3 audit store partitioning scheme."""
    
    @pytest.fixture
    def mock_boto3(self):
        with patch("aegis_ai.governance.audit.s3_store.boto3") as mock:
            yield mock

    def test_date_partitioning(self, mock_boto3):
        """Test date-based partitioning."""
        # Mock client creation
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_boto3.Session.return_value.client.return_value = mock_client

        store = S3AuditStore(
            bucket_name="test-bucket",
            environment="prod",
        )
        
        key1 = store._get_partition_prefix(date="2026-01-28")
        key2 = store._get_partition_prefix(date="2026-01-29")
        
        # Should have different dates
        assert "2026-01-28" in key1
        assert "2026-01-29" in key2
        assert key1 != key2
    
    def test_environment_partitioning(self, mock_boto3):
        """Test environment-based partitioning."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        
        store_prod = S3AuditStore(
            bucket_name="test-bucket",
            environment="production",
        )
        store_dev = S3AuditStore(
            bucket_name="test-bucket",
            environment="development",
        )
        
        key_prod = store_prod._get_partition_prefix()
        key_dev = store_dev._get_partition_prefix()
        
        # Should have different environments
        assert "production" in key_prod
        assert "development" in key_dev
        assert key_prod != key_dev
