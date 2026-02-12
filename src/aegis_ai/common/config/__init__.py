"""Configuration subpackage for AegisAI.

Provides configuration management and emergency controls.
"""

from aegis_ai.common.config.settings import (
    Config,
    Environment,
    LogLevel,
    AuditStorageType,
    get_config,
    reset_config,
)
from aegis_ai.common.config.emergency import (
    ConfigSource,
    KillSwitch,
    DynamicConfig,
    EmergencyControl,
    get_dynamic_config,
    get_emergency_control,
)

__all__ = [
    # Settings
    "Config",
    "Environment",
    "LogLevel",
    "AuditStorageType",
    "get_config",
    "reset_config",
    # Emergency controls
    "ConfigSource",
    "KillSwitch",
    "DynamicConfig",
    "EmergencyControl",
    "get_dynamic_config",
    "get_emergency_control",
]
