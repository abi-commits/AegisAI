"""Configuration module - Centralized config management system."""

# Core configuration classes
from aegis_ai.common.config.schema import (
    Config,
    Environment,
    LogLevel,
    AuditStorageType,
    PathConfig,
    APIConfig,
    LoggingConfig,
    AuditConfig,
    AWSConfig,
    ModelConfig,
    PolicyConfig,
    DatabaseConfig,
    MLflowConfig,
    MonitoringConfig,
    SecurityConfig,
)

# Configuration manager and access functions
from aegis_ai.common.config.manager import (
    ConfigManager,
    get_config,
    get_config_manager,
    get_config_section,
    # Convenience functions
    is_production,
    is_development,
    is_debug_enabled,
    get_api_config,
    get_audit_config,
    get_logging_config,
    get_aws_config,
    get_model_config,
    get_policy_config,
    get_project_root,
    get_log_dir,
    get_audit_dir,
    get_models_dir,
    get_data_dir,
    get_config_dir,
)

__all__ = [
    # Schema/Config classes
    "Config",
    "Environment",
    "LogLevel",
    "AuditStorageType",
    "PathConfig",
    "APIConfig",
    "LoggingConfig",
    "AuditConfig",
    "AWSConfig",
    "ModelConfig",
    "PolicyConfig",
    "DatabaseConfig",
    "MLflowConfig",
    "MonitoringConfig",
    "SecurityConfig",
    # Manager and functions
    "ConfigManager",
    "get_config",
    "get_config_manager",
    "get_config_section",
    # Convenience functions
    "is_production",
    "is_development",
    "is_debug_enabled",
    "get_api_config",
    "get_audit_config",
    "get_logging_config",
    "get_aws_config",
    "get_model_config",
    "get_policy_config",
    "get_project_root",
    "get_log_dir",
    "get_audit_dir",
    "get_models_dir",
    "get_data_dir",
    "get_config_dir",
]
