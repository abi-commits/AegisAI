"""Configuration management - Centralized configuration for AegisAI.

Provides environment-aware configuration with sensible defaults.
All configuration is loaded from environment variables with fallbacks.
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


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


def _get_project_root() -> Path:
    """Get the project root directory."""
    # Navigate up from src/aegis_ai/common/config/settings.py to project root
    current = Path(__file__).resolve()
    # Go up 5 levels: settings.py -> config -> common -> aegis_ai -> src -> project_root
    return current.parent.parent.parent.parent.parent


@dataclass
class Config:
    """Central configuration object for AegisAI.
    
    All settings can be overridden via environment variables prefixed with AEGIS_.
    
    Example:
        AEGIS_ENVIRONMENT=production
        AEGIS_LOG_LEVEL=INFO
        AEGIS_DEBUG=false
    """
    
    # Core settings
    environment: Environment = field(
        default_factory=lambda: Environment(
            os.getenv("AEGIS_ENVIRONMENT", "development")
        )
    )
    debug: bool = field(
        default_factory=lambda: os.getenv("AEGIS_DEBUG", "false").lower() == "true"
    )
    log_level: LogLevel = field(
        default_factory=lambda: LogLevel(os.getenv("AEGIS_LOG_LEVEL", "INFO"))
    )
    
    # Paths
    project_root: Path = field(default_factory=_get_project_root)
    
    # API settings
    api_host: str = field(
        default_factory=lambda: os.getenv("AEGIS_API_HOST", "0.0.0.0")
    )
    api_port: int = field(
        default_factory=lambda: int(os.getenv("AEGIS_API_PORT", "8000"))
    )
    
    # Audit settings
    audit_storage_type: AuditStorageType = field(
        default_factory=lambda: AuditStorageType(
            os.getenv("AEGIS_AUDIT_STORAGE_TYPE", "local")
        )
    )
    audit_log_dir: Path = field(
        default_factory=lambda: Path(
            os.getenv("AEGIS_AUDIT_LOG_DIR", "./logs/audit")
        )
    )
    audit_s3_bucket: Optional[str] = field(
        default_factory=lambda: os.getenv("AEGIS_AUDIT_S3_BUCKET")
    )
    audit_dynamodb_table: Optional[str] = field(
        default_factory=lambda: os.getenv("AEGIS_AUDIT_DYNAMODB_TABLE")
    )
    
    # AWS settings (for S3/DynamoDB)
    aws_region: str = field(
        default_factory=lambda: os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    )
    
    # Policy settings
    policy_file: Path = field(
        default_factory=lambda: Path(
            os.getenv("AEGIS_POLICY_FILE", "./config/policy_rules.yaml")
        )
    )
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        # Create audit log directory if using local storage
        if self.audit_storage_type == AuditStorageType.LOCAL:
            self.audit_log_dir.mkdir(parents=True, exist_ok=True)
        
        # Validate S3 config
        if self.audit_storage_type == AuditStorageType.S3:
            if not self.audit_s3_bucket:
                raise ValueError(
                    "AEGIS_AUDIT_S3_BUCKET must be set when using S3 audit storage"
                )
        
        # Warn about debug in production
        if self.environment == Environment.PRODUCTION and self.debug:
            import warnings
            warnings.warn(
                "Debug mode is enabled in production environment",
                RuntimeWarning,
                stacklevel=2
            )
    
    @property
    def log_dir(self) -> Path:
        """Get the log directory path."""
        log_dir = self.project_root / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir
    
    @property
    def config_dir(self) -> Path:
        """Get the config directory path."""
        return self.project_root / "config"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == Environment.PRODUCTION
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == Environment.DEVELOPMENT


# Singleton instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance.
    
    Returns:
        Config: The global configuration singleton.
    """
    global _config
    if _config is None:
        _config = Config()
    return _config


def reset_config() -> None:
    """Reset the global configuration (for testing)."""
    global _config
    _config = None
