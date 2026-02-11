"""Model artifacts & versioning - frozen in time."""

import json, logging, hashlib, os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class ModelType(str, Enum):
    DETECTION = "detection"
    BEHAVIOR = "behavior"
    NETWORK = "network"
    CONFIDENCE = "confidence"
    EXPLANATION = "explanation"
    RISK = "risk"
    CALIBRATION = "calibration"


@dataclass
class FeatureSchema:
    model_type: str
    features: Dict[str, str]
    version: str
    timestamp: str
    
    def compute_hash(self) -> str:
        schema_str = json.dumps(
            {"model_type": self.model_type, "features": self.features, "version": self.version},
            sort_keys=True)
        return hashlib.sha256(schema_str.encode()).hexdigest()


@dataclass
class ModelArtifact:
    """Immutable model artifact metadata."""
    model_id: str
    model_type: ModelType
    version: str
    artifact_uri: str
    feature_schema: FeatureSchema
    hyperparameters: Dict[str, Any]
    performance_metrics: Dict[str, float]
    training_data_hash: str
    framework: str
    python_version: str
    framework_version: str
    created_at: str
    created_by: str
    policy_version: str
    description: str = ""
    tags: Dict[str, str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if self.tags is None:
            data["tags"] = {}
        return data
    
    def compute_hash(self) -> str:
        content = json.dumps({
            "model_id": self.model_id, "version": self.version,
            "feature_schema_hash": self.feature_schema.compute_hash(),
            "hyperparameters": self.hyperparameters,
            "framework_version": self.framework_version,
            "training_data_hash": self.training_data_hash}, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()


class ModelRegistry:
    """Registry for model versions with immutability guarantees."""
    
    DEFAULT_REGION = "us-east-1"
    DEFAULT_PREFIX = "model-registry/"
    
    def __init__(self, bucket_name: Optional[str] = None, prefix: str = DEFAULT_PREFIX,
                 region: Optional[str] = None, aws_profile: Optional[str] = None,
                 mlflow_uri: Optional[str] = None):
        self.bucket_name = bucket_name or os.environ.get("S3_MODEL_REGISTRY_BUCKET")
        if not self.bucket_name:
            raise ValueError("S3 bucket required. Set S3_MODEL_REGISTRY_BUCKET or pass bucket_name.")
        
        self.prefix = prefix
        self.region = region or os.environ.get("AWS_REGION", self.DEFAULT_REGION)
        self.mlflow_uri = mlflow_uri or os.environ.get("MLFLOW_TRACKING_URI")
        
        if aws_profile:
            session = boto3.Session(profile_name=aws_profile)
            self.s3_client = session.client("s3", region_name=self.region)
        else:
            self.s3_client = boto3.client("s3", region_name=self.region)
        
        self.mlflow = None
        if self.mlflow_uri:
            try:
                import mlflow
                mlflow.set_tracking_uri(self.mlflow_uri)
                self.mlflow = mlflow
                logger.info(f"MLflow integration enabled: {self.mlflow_uri}")
            except ImportError:
                logger.warning("MLflow not installed, skipping MLflow integration")
        
        logger.info(f"Initialized ModelRegistry: bucket={self.bucket_name}, prefix={self.prefix}")
    
    def _get_registry_key(self, model_type: str, model_id: str, version: str) -> str:
        """Get S3 key for model metadata: {prefix}/{model_type}/{model_id}/{version}/metadata.json"""
        return f"{self.prefix}{model_type}/{model_id}/{version}/metadata.json"
    
    def _get_artifact_key(self, model_type: str, model_id: str, version: str) -> str:
        """Get S3 prefix for model artifacts.
        
        Format: {prefix}/{model_type}/{model_id}/{version}/
        """
        return f"{self.prefix}{model_type}/{model_id}/{version}/"
    
    def register_model(
        self,
        artifact: ModelArtifact,
        verify_artifact_exists: bool = True,
    ) -> str:
        """Register a new model version immutably.
        
        Args:
            artifact: ModelArtifact with complete metadata
            verify_artifact_exists: Whether to verify artifact already in S3
            
        Returns:
            Model artifact URI
            
        Raises:
            ValueError: If artifact already exists or validation fails
            IOError: If S3 write fails
        """
        # Check if version already exists (immutable)
        registry_key = self._get_registry_key(
            artifact.model_type.value,
            artifact.model_id,
            artifact.version,
        )
        
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=registry_key)
            raise ValueError(
                f"Model version already exists: {artifact.model_id}/{artifact.version}"
            )
        except self.s3_client.exceptions.NoSuchKey:
            pass  # Expected - this is a new version
        
        # Verify artifact URI is valid
        if verify_artifact_exists:
            try:
                self.s3_client.head_object(
                    Bucket=self.bucket_name,
                    Key=artifact.artifact_uri.replace(f"s3://{self.bucket_name}/", ""),
                )
            except ClientError:
                raise ValueError(
                    f"Artifact not found at: {artifact.artifact_uri}"
                )
        
        # Store metadata immutably
        metadata = artifact.to_dict()
        metadata["model_hash"] = artifact.compute_hash()
        metadata["registered_at"] = datetime.now(timezone.utc).isoformat()
        metadata["registry_version"] = "1.0"
        
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=registry_key,
                Body=json.dumps(metadata, indent=2, default=str).encode(),
                ContentType="application/json",
                ServerSideEncryption="AES256",
                Metadata={
                    "model-id": artifact.model_id,
                    "model-version": artifact.version,
                    "model-type": artifact.model_type.value,
                },
            )
            
            logger.info(
                f"Registered model: {artifact.model_id}/{artifact.version} "
                f"({artifact.model_type.value})"
            )
            
            # Optional: sync with MLflow
            if self.mlflow:
                self._sync_with_mlflow(artifact)
            
            return artifact.artifact_uri
        
        except ClientError as e:
            logger.error(f"Failed to register model: {e}")
            raise IOError(f"S3 write failed: {e}") from e
    
    def get_model(
        self,
        model_type: str,
        model_id: str,
        version: str,
    ) -> Optional[ModelArtifact]:
        """Retrieve model metadata (immutable).
        
        Args:
            model_type: Type of model
            model_id: Model identifier
            version: Model version
            
        Returns:
            ModelArtifact or None if not found
        """
        registry_key = self._get_registry_key(model_type, model_id, version)
        
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=registry_key,
            )
            metadata = json.loads(response["Body"].read().decode())
            
            # Reconstruct ModelArtifact
            feature_schema = FeatureSchema(**metadata.pop("feature_schema"))
            model_type_enum = ModelType(metadata.pop("model_type"))
            
            artifact = ModelArtifact(
                **metadata,
                model_type=model_type_enum,
                feature_schema=feature_schema,
            )
            
            return artifact
        
        except self.s3_client.exceptions.NoSuchKey:
            logger.warning(f"Model not found: {model_id}/{version}")
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve model: {e}")
            return None
    
    def get_latest_model(
        self,
        model_type: str,
        model_id: str,
    ) -> Optional[ModelArtifact]:
        """Get latest version of a model by listing versions.
        
        Args:
            model_type: Type of model
            model_id: Model identifier
            
        Returns:
            Latest ModelArtifact or None
        """
        prefix = self._get_registry_key(model_type, model_id, "")
        
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
            )
            
            if "Contents" not in response or not response["Contents"]:
                return None
            
            # Get the most recent (last one in listing)
            latest_key = sorted(response["Contents"], key=lambda x: x["LastModified"])[-1]["Key"]
            
            # Extract version from key: .../model_id/version/metadata.json
            version = latest_key.split("/")[-2]
            
            return self.get_model(model_type, model_id, version)
        
        except Exception as e:
            logger.error(f"Failed to get latest model: {e}")
            return None
    
    def list_versions(
        self,
        model_type: str,
        model_id: str,
    ) -> List[Dict[str, Any]]:
        """List all versions of a model.
        
        Args:
            model_type: Type of model
            model_id: Model identifier
            
        Returns:
            List of version metadata
        """
        prefix = self._get_registry_key(model_type, model_id, "")
        versions = []
        
        try:
            paginator = self.s3_client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)
            
            for page in pages:
                if "Contents" not in page:
                    continue
                
                for obj in page["Contents"]:
                    if obj["Key"].endswith("metadata.json"):
                        version = obj["Key"].split("/")[-2]
                        versions.append({
                            "version": version,
                            "last_modified": obj["LastModified"].isoformat(),
                            "size": obj["Size"],
                        })
            
            return sorted(versions, key=lambda v: v["last_modified"], reverse=True)
        
        except Exception as e:
            logger.error(f"Failed to list versions: {e}")
            return []
    
    def _sync_with_mlflow(self, artifact: ModelArtifact) -> None:
        """Optional: sync model to MLflow tracking.
        
        Args:
            artifact: Model artifact to sync
        """
        if not self.mlflow:
            return
        
        try:
            # Log as MLflow experiment
            self.mlflow.set_experiment(artifact.model_id)
            with self.mlflow.start_run(run_name=artifact.version):
                # Log params
                for key, value in artifact.hyperparameters.items():
                    self.mlflow.log_param(key, value)
                
                # Log metrics
                for key, value in artifact.performance_metrics.items():
                    self.mlflow.log_metric(key, value)
                
                # Log tags
                tags = artifact.tags or {}
                tags["model_version"] = artifact.version
                tags["policy_version"] = artifact.policy_version
                for key, value in tags.items():
                    self.mlflow.set_tag(key, value)
                
                # Log artifact metadata
                self.mlflow.log_dict(artifact.to_dict(), "model_metadata.json")
            
            logger.debug(f"Synced model to MLflow: {artifact.model_id}/{artifact.version}")
        
        except Exception as e:
            logger.warning(f"Failed to sync with MLflow: {e}")


class DecisionModelTrace:
    """Links decisions to exact model versions and feature schemas.
    
    This enables post-hoc analysis: "Why did we make that decision?"
    Answer: "Because model v1.2 with schema hash X123 used feature Y."
    """
    
    @staticmethod
    def create_trace(
        decision_id: str,
        model_type: ModelType,
        model_version: str,
        feature_schema_hash: str,
        policy_version: str,
        features_used: Dict[str, Any],
        model_output: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create complete trace for a decision.
        
        Args:
            decision_id: Decision identifier
            model_type: Type of model used
            model_version: Model version used
            feature_schema_hash: Hash of feature schema
            policy_version: Policy version used
            features_used: Actual features fed to model
            model_output: Model output for decision
            
        Returns:
            Complete decision trace for audit logging
        """
        trace = {
            "decision_id": decision_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": {
                "type": model_type.value,
                "version": model_version,
            },
            "schema": {
                "feature_schema_hash": feature_schema_hash,
            },
            "policy_version": policy_version,
            "features": {
                "count": len(features_used),
                "names": list(features_used.keys()),
            },
            "output": model_output,
        }
        
        return trace
