"""Tests for Model Artifacts Layer (Layer 5)."""

import pytest
import json
import hashlib
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal

from aegis_ai.models.artifacts import (
    ModelType,
    FeatureSchema,
    ModelArtifact,
    ModelRegistry,
    DecisionModelTrace,
)


class TestFeatureSchema:
    """Tests for FeatureSchema."""
    
    def test_feature_schema_creation(self):
        """Test creating a feature schema."""
        features = {
            "user_risk_score": {"type": "float", "min": 0, "max": 1},
            "transaction_amount": {"type": "float"},
            "account_age_days": {"type": "int"},
            "geographic_risk": {"type": "categorical", "values": ["low", "medium", "high"]},
        }
        
        schema = FeatureSchema(
            model_type="detection",
            features=features,
            version="1.0.0",
            timestamp="2026-01-28T00:00:00Z"
        )
        assert schema.features == features
    
    def test_feature_schema_hash(self):
        """Test feature schema hash computation."""
        features = {
            "user_risk_score": {"type": "float"},
            "transaction_amount": {"type": "float"},
        }
        
        schema1 = FeatureSchema(
            model_type="detection",
            features=features,
            version="1.0.0",
            timestamp="2026-01-28T00:00:00Z"
        )
        schema2 = FeatureSchema(
            model_type="detection",
            features=features,
            version="1.0.0",
            timestamp="2026-01-28T00:00:00Z"
        )
        
        # Same features should produce same hash
        assert schema1.compute_hash() == schema2.compute_hash()
    
    def test_feature_schema_hash_deterministic(self):
        """Test that hash is deterministic."""
        features = {
            "a": {"type": "float"},
            "b": {"type": "int"},
        }
        
        schema = FeatureSchema(
            model_type="detection",
            features=features,
            version="1.0.0",
            timestamp="2026-01-28T00:00:00Z"
        )
        hash1 = schema.compute_hash()
        hash2 = schema.compute_hash()
        
        assert hash1 == hash2
    
    def test_feature_schema_hash_changes_with_content(self):
        """Test that hash changes when features change."""
        schema1 = FeatureSchema(
            model_type="detection",
            features={"a": {"type": "float"}},
            version="1.0.0",
            timestamp="2026-01-28T00:00:00Z"
        )
        schema2 = FeatureSchema(
            model_type="detection",
            features={"b": {"type": "float"}},
            version="1.0.0",
            timestamp="2026-01-28T00:00:00Z"
        )
        
        # Different features should produce different hashes
        assert schema1.compute_hash() != schema2.compute_hash()


class TestModelArtifact:
    """Tests for ModelArtifact."""
    
    def test_model_artifact_creation(self):
        """Test creating a model artifact."""
        features = {"user_score": {"type": "float"}}
        schema = FeatureSchema(
            model_type="detection",
            features=features,
            version="1.0.0",
            timestamp="2026-01-28T00:00:00Z"
        )
        
        artifact = ModelArtifact(
            model_id="fraud-detection-v1",
            version="1.0.0",
            model_type=ModelType.DETECTION,
            artifact_uri="s3://models/fraud-v1.pkl",
            feature_schema=schema,
            hyperparameters={"threshold": 0.7, "max_depth": 10},
            performance_metrics={"precision": 0.95, "recall": 0.92},
            training_data_hash="abc123",
            framework="xgboost",
            created_by="data-team",
        )
        
        assert artifact.model_id == "fraud-detection-v1"
        assert artifact.version == "1.0.0"
        assert artifact.model_type == ModelType.DETECTION
        assert artifact.framework == "xgboost"
    
    def test_model_artifact_to_dict(self):
        """Test converting artifact to dict."""
        features = {"user_score": {"type": "float"}}
        schema = FeatureSchema(
            model_type="detection",
            features=features,
            version="1.0.0",
            timestamp="2026-01-28T00:00:00Z"
        )
        
        artifact = ModelArtifact(
            model_id="test-model",
            version="1.0.0",
            model_type=ModelType.DETECTION,
            artifact_uri="s3://models/test.pkl",
            feature_schema=schema,
            created_by="test",
        )
        
        artifact_dict = artifact.to_dict()
        
        assert artifact_dict["model_id"] == "test-model"
        assert artifact_dict["version"] == "1.0.0"
        assert "created_at" in artifact_dict


class TestModelRegistry:
    """Tests for ModelRegistry."""
    
    @patch("aegis_ai.models.artifacts.boto3.client")
    def test_register_model(self, mock_boto3_client):
        """Test registering a model."""
        # Mock S3 client
        mock_s3 = MagicMock()
        mock_boto3_client.return_value = mock_s3
        mock_s3.head_object.side_effect = Exception("Not found")  # Version doesn't exist
        
        registry = ModelRegistry(bucket_name="test-bucket")
        
        features = {"score": {"type": "float"}}
        schema = FeatureSchema(
            model_type="detection",
            features=features,
            version="1.0.0",
            timestamp="2026-01-28T00:00:00Z"
        )
        
        artifact = ModelArtifact(
            model_id="test-model",
            version="1.0.0",
            model_type=ModelType.DETECTION,
            artifact_uri="s3://models/test.pkl",
            feature_schema=schema,
            created_by="test",
        )
        
        result = registry.register_model(artifact)
        
        assert result is not None
        # Verify S3 put_object was called
        assert mock_s3.put_object.called
    
    @patch("aegis_ai.models.artifacts.boto3.client")
    def test_get_model(self, mock_boto3_client):
        """Test retrieving a model."""
        mock_s3 = MagicMock()
        mock_boto3_client.return_value = mock_s3
        
        # Mock the get_object response
        features = {"score": {"type": "float"}}
        schema = FeatureSchema(
            model_type="detection",
            features=features,
            version="1.0.0",
            timestamp="2026-01-28T00:00:00Z"
        )
        
        artifact = ModelArtifact(
            model_id="test-model",
            version="1.0.0",
            model_type=ModelType.DETECTION,
            artifact_uri="s3://models/test.pkl",
            feature_schema=schema,
            created_by="test",
        )
        
        artifact_json = json.dumps(artifact.to_dict())
        
        mock_response = {
            "Body": MagicMock(read=lambda: artifact_json.encode()),
        }
        mock_s3.get_object.return_value = mock_response
        
        registry = ModelRegistry(bucket_name="test-bucket")
        result = registry.get_model(ModelType.DETECTION, "test-model", "1.0.0")
        
        assert result is not None
        assert result.model_id == "test-model"
    
    @patch("aegis_ai.models.artifacts.boto3.client")
    def test_list_versions(self, mock_boto3_client):
        """Test listing model versions."""
        mock_s3 = MagicMock()
        mock_boto3_client.return_value = mock_s3
        
        # Mock list_objects response
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "model-registry/detection/test-model/1.0.0/metadata.json"},
                {"Key": "model-registry/detection/test-model/1.0.1/metadata.json"},
                {"Key": "model-registry/detection/test-model/1.1.0/metadata.json"},
            ],
        }
        
        registry = ModelRegistry(bucket_name="test-bucket")
        versions = registry.list_versions(ModelType.DETECTION, "test-model")
        
        assert len(versions) == 3


class TestDecisionModelTrace:
    """Tests for DecisionModelTrace."""
    
    def test_create_trace(self):
        """Test creating a decision model trace."""
        features = {"score": {"type": "float"}}
        schema = FeatureSchema(
            model_type="detection",
            features=features,
            version="1.0.0",
            timestamp="2026-01-28T00:00:00Z"
        )
        
        artifact = ModelArtifact(
            model_id="test-model",
            version="1.0.0",
            model_type=ModelType.DETECTION,
            artifact_uri="s3://models/test.pkl",
            feature_schema=schema,
            created_by="test",
        )
        
        trace = DecisionModelTrace.create_trace(
            decision_id="decision-123",
            model_artifact=artifact,
            policy_version="policy-v2",
            confidence_score=0.85,
            model_latency_ms=150,
        )
        
        assert trace.decision_id == "decision-123"
        assert trace.model_id == "test-model"
        assert trace.model_version == "1.0.0"
        assert trace.policy_version == "policy-v2"
        assert trace.confidence_score == 0.85
    
    def test_trace_to_dict(self):
        """Test converting trace to dict."""
        features = {"score": {"type": "float"}}
        schema = FeatureSchema(
            model_type="detection",
            features=features,
            version="1.0.0",
            timestamp="2026-01-28T00:00:00Z"
        )
        
        artifact = ModelArtifact(
            model_id="test-model",
            version="1.0.0",
            model_type=ModelType.DETECTION,
            artifact_uri="s3://models/test.pkl",
            feature_schema=schema,
            created_by="test",
        )
        
        trace = DecisionModelTrace.create_trace(
            decision_id="decision-123",
            model_artifact=artifact,
            policy_version="policy-v2",
        )
        
        trace_dict = trace.to_dict()
        
        assert trace_dict["decision_id"] == "decision-123"
        assert trace_dict["model_id"] == "test-model"
        assert "created_at" in trace_dict


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
