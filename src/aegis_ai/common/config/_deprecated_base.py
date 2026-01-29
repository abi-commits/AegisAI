"""Configuration management - Base configuration classes."""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List
import os
from pathlib import Path
from enum import Enum
import json


class Environment(str, Enum):
    """Application environment."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    """Logging levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AuditStorageType(str, Enum):
    """Audit storage backend types."""
    LOCAL = "local"
    S3 = "s3"
    DYNAMODB = "dynamodb"


@dataclass
class PathConfig:
    """Path configuration."""
    project_root: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent.parent.parent)
    log_dir: Path = field(default_factory=lambda: Path("./logs"))
    data_dir: Path = field(default_factory=lambda: Path("./data"))
    models_dir: Path = field(default_factory=lambda: Path("./models"))
    config_dir: Path = field(default_factory=lambda: Path("./config"))
    cache_dir: Path = field(default_factory=lambda: Path("./cache"))
    
    def __post_init__(self):
        """Create necessary directories."""
        for directory in [self.log_dir, self.data_dir, self.models_dir, self.config_dir, self.cache_dir]:
            directory.mkdir(parents=True, exist_ok=True)


@dataclass
class APIConfig:
    """API server configuration."""
    host: str = field(default_factory=lambda: os.getenv("AEGIS_API_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("AEGIS_API_PORT", "8000")))
    workers: int = field(default_factory=lambda: int(os.getenv("AEGIS_API_WORKERS", "1")))
    reload: bool = field(default_factory=lambda: os.getenv("AEGIS_API_RELOAD", "false").lower() == "true")
    log_level: str = field(default_factory=lambda: os.getenv("AEGIS_API_LOG_LEVEL", "info"))


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: LogLevel = field(default_factory=lambda: LogLevel(os.getenv("AEGIS_LOG_LEVEL", "INFO")))
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
    max_bytes: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    use_structured: bool = field(default_factory=lambda: os.getenv("AEGIS_STRUCTURED_LOGGING", "true").lower() == "true")


@dataclass
class AuditConfig:
    """Audit logging configuration."""
    storage_type: AuditStorageType = field(
        default_factory=lambda: AuditStorageType(os.getenv("AEGIS_AUDIT_STORAGE_TYPE", "local"))
    )
    local_path: str = field(default_factory=lambda: os.getenv("AEGIS_AUDIT_LOCAL_PATH", "./logs/audit"))
    s3_bucket: str = field(default_factory=lambda: os.getenv("AEGIS_AUDIT_S3_BUCKET", ""))
    s3_prefix: str = field(default_factory=lambda: os.getenv("AEGIS_AUDIT_S3_PREFIX", "audit-logs"))
    dynamodb_table: str = field(default_factory=lambda: os.getenv("AEGIS_AUDIT_DYNAMODB_TABLE", ""))
    background_writer: bool = field(default_factory=lambda: os.getenv("AEGIS_AUDIT_BACKGROUND_WRITER", "true").lower() == "true")
    buffer_size: int = 100
    flush_interval_seconds: int = 5


@dataclass
class AWSConfig:
    """AWS configuration."""
    access_key_id: str = field(default_factory=lambda: os.getenv("AWS_ACCESS_KEY_ID", ""))
    secret_access_key: str = field(default_factory=lambda: os.getenv("AWS_SECRET_ACCESS_KEY", ""))
    region: str = field(default_factory=lambda: os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
    endpoint_url: Optional[str] = field(default_factory=lambda: os.getenv("AWS_ENDPOINT_URL"))


@dataclass
class ModelConfig:
    """Model configuration."""
    xgboost: Dict[str, Any] = field(default_factory=lambda: {
        "max_depth": 6,
        "learning_rate": 0.1,
        "n_estimators": 100,
        "verbosity": 0,
    })
    lightgbm: Dict[str, Any] = field(default_factory=lambda: {
        "max_depth": 6,
        "learning_rate": 0.1,
        "num_leaves": 31,
        "verbose": -1,
    })
    graph_embedding: Dict[str, Any] = field(default_factory=lambda: {
        "embedding_dim": 32,
        "num_layers": 2,
        "dropout": 0.1,
    })
    calibration_method: str = "isotonic"  # or "platt", "confidence"


@dataclass
class PolicyConfig:
    """Policy engine configuration."""
    rules_file: str = field(default_factory=lambda: os.getenv("AEGIS_POLICY_FILE", "./config/policy_rules.yaml"))
    strict_mode: bool = field(default_factory=lambda: os.getenv("AEGIS_POLICY_STRICT", "false").lower() == "true")
    allow_overrides: bool = field(default_factory=lambda: os.getenv("AEGIS_POLICY_ALLOW_OVERRIDES", "true").lower() == "true")
    override_ttl_hours: int = 24


@dataclass
class MLflowConfig:
    """MLflow tracking configuration."""
    enabled: bool = field(default_factory=lambda: os.getenv("AEGIS_MLFLOW_ENABLED", "false").lower() == "true")
    tracking_uri: str = field(default_factory=lambda: os.getenv("AEGIS_MLFLOW_TRACKING_URI", "http://localhost:5000"))
    experiment_name: str = field(default_factory=lambda: os.getenv("AEGIS_MLFLOW_EXPERIMENT", "aegis-ai"))
    run_name_prefix: str = "aegis"


@dataclass
class FeatureFlags:
    """Feature flags for gradual rollout."""
    new_risk_model: bool = field(default_factory=lambda: os.getenv("FEATURE_NEW_RISK_MODEL", "false").lower() == "true")
    enhanced_graph: bool = field(default_factory=lambda: os.getenv("FEATURE_ENHANCED_GRAPH", "true").lower() == "true")
    async_audit: bool = field(default_factory=lambda: os.getenv("FEATURE_ASYNC_AUDIT", "true").lower() == "true")


@dataclass
class Config:
    """Central configuration object."""
    
    # Core settings
    environment: Environment = field(default_factory=lambda: Environment(os.getenv("AEGIS_ENVIRONMENT", "development")))
    debug: bool = field(default_factory=lambda: os.getenv("AEGIS_DEBUG", "false").lower() == "true")
    version: str = "0.1.0"
    
    # Sub-configurations
    paths: PathConfig = field(default_factory=PathConfig)
    api: APIConfig = field(default_factory=APIConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    audit: AuditConfig = field(default_factory=AuditConfig)
    aws: AWSConfig = field(default_factory=AWSConfig)
    models: ModelConfig = field(default_factory=ModelConfig)
    policy: PolicyConfig = field(default_factory=PolicyConfig)
    mlflow: MLflowConfig = field(default_factory=MLflowConfig)
    features: FeatureFlags = field(default_factory=FeatureFlags)
    
    def __post_init__(self):
        """Initialize directories and validate configuration."""
        self.paths.__post_init__()
        self._validate()
    
    def _validate(self):
        """Validate configuration for consistency."""
        if self.environment == Environment.PRODUCTION and self.debug:
            raise ValueError("Debug mode cannot be enabled in production")
        
        if self.audit.storage_type == AuditStorageType.S3 and not self.audit.s3_bucket:
            raise ValueError("S3 bucket must be configured when using S3 audit storage")
        
        if self.audit.storage_type == AuditStorageType.DYNAMODB and not self.audit.dynamodb_table:
            raise ValueError("DynamoDB table must be configured when using DynamoDB audit storage")
    
    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """Convert config to dictionary.
        
        Args:
            include_sensitive: Whether to include sensitive values (passwords, keys, etc.)
            
        Returns:
            Configuration as dictionary
        """
        config_dict = asdict(self)
        
        if not include_sensitive:
            # Remove sensitive fields
            if "aws" in config_dict:
                config_dict["aws"]["access_key_id"] = "***"
                config_dict["aws"]["secret_access_key"] = "***"
        
        return config_dict
    
    def to_json(self, include_sensitive: bool = False, pretty: bool = True) -> str:
        """Convert config to JSON.
        
        Args:
            include_sensitive: Whether to include sensitive values
            pretty: Whether to pretty-print JSON
            
        Returns:
            Configuration as JSON string
        """
        config_dict = self.to_dict(include_sensitive=include_sensitive)
        indent = 2 if pretty else None
        return json.dumps(config_dict, indent=indent, default=str)
    
    def save_to_file(self, filepath: Path, include_sensitive: bool = False):
        """Save configuration to JSON file.
        
        Args:
            filepath: Path to save configuration
            include_sensitive: Whether to include sensitive values
        """
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            f.write(self.to_json(include_sensitive=include_sensitive, pretty=True))
    
    @classmethod
    def load_from_file(cls, filepath: Path) -> "Config":
        """Load configuration from JSON file.
        
        Args:
            filepath: Path to configuration file
            
        Returns:
            Config instance
        """
        with open(filepath, 'r') as f:
            config_dict = json.load(f)
        
        # This is a simplified loader - a full implementation would recursively
        # reconstruct nested dataclass instances
        return cls(**config_dict)
