"""Kill Switches - Runtime Feature Control.

Provides dynamic configuration for emergency controls and feature flags.
Designed for production safety - when something feels wrong, slow down.

Philosophy:
"If something feels wrong, you slow the system down instead of letting it run wild."

Features:
- Feature flags (enable/disable agents)
- Emergency modes (force human review)
- Policy overrides (policy-only mode)
- Graceful degradation
"""

import os
import logging
from enum import Enum
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


class ConfigSource(str, Enum):
    """Sources for configuration."""
    ENVIRONMENT = "environment"
    PARAMETER_STORE = "parameter_store"  # AWS Parameter Store
    APPCONFIG = "appconfig"              # AWS AppConfig


class KillSwitch(str, Enum):
    """Kill switch names for emergency control."""
    # Agent controls
    DISABLE_DETECTION_AGENT = "disable_detection_agent"
    DISABLE_BEHAVIOR_AGENT = "disable_behavior_agent"
    DISABLE_NETWORK_AGENT = "disable_network_agent"
    DISABLE_CONFIDENCE_AGENT = "disable_confidence_agent"
    DISABLE_EXPLANATION_AGENT = "disable_explanation_agent"
    
    # System modes
    FORCE_HUMAN_REVIEW = "force_human_review"
    POLICY_ONLY_MODE = "policy_only_mode"
    SHADOW_MODE = "shadow_mode"
    SLOW_MODE = "slow_mode"
    
    # Feature flags
    ENABLE_MODEL_DRIFT_DETECTION = "enable_model_drift_detection"
    ENABLE_CONFIDENCE_CALIBRATION = "enable_confidence_calibration"
    ENABLE_EXPLANATION_GENERATION = "enable_explanation_generation"
    
    # Escalation controls
    ESCALATE_HIGH_RISK = "escalate_high_risk"
    ESCALATE_DISAGREEMENT = "escalate_disagreement"
    ESCALATE_UNUSUAL_PATTERN = "escalate_unusual_pattern"


class DynamicConfig:
    """Dynamic configuration with environment variable support.
    
    Load order:
    1. Environment variables (highest priority)
    2. Defaults (lowest priority)
    
    All environment variables are prefixed with AEGIS_.
    """
    
    # Default configuration (safe defaults)
    DEFAULTS: Dict[str, Any] = {
        # Agent controls - all enabled by default
        "disable_detection_agent": False,
        "disable_behavior_agent": False,
        "disable_network_agent": False,
        "disable_confidence_agent": False,
        "disable_explanation_agent": False,
        # System modes - normal operation by default
        "force_human_review": False,
        "policy_only_mode": False,
        "shadow_mode": False,
        "slow_mode": False,
        # Feature flags - all enabled by default
        "enable_model_drift_detection": True,
        "enable_confidence_calibration": True,
        "enable_explanation_generation": True,
        # Escalation controls - conservative defaults
        "escalate_high_risk": True,
        "escalate_disagreement": True,
        "escalate_unusual_pattern": True,
        # Thresholds
        "slow_mode_delay_ms": 0,
        "high_risk_threshold": 0.8,
        "disagreement_threshold": 0.3,
    }
    
    def __init__(
        self,
        source: ConfigSource = ConfigSource.ENVIRONMENT,
        region: Optional[str] = None,
        aws_profile: Optional[str] = None,
        cache_ttl_seconds: int = 60,
    ):
        """Initialize dynamic configuration.
        
        Args:
            source: Configuration source (only ENVIRONMENT supported currently)
            region: AWS region (for future AWS integration)
            aws_profile: AWS profile (for future AWS integration)
            cache_ttl_seconds: Cache TTL for fetched configs
        """
        self.source = source
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")
        self.cache_ttl_seconds = cache_ttl_seconds
        self.config_cache: Dict[str, Any] = {}
        
        # Store AWS params for future use
        self._aws_profile = aws_profile
        
        logger.debug(
            f"Initialized DynamicConfig: source={source.value}, "
            f"cache_ttl={cache_ttl_seconds}s"
        )
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value.
        
        Load order:
        1. Environment variable (AEGIS_{KEY})
        2. Cache
        3. Default value
        
        Args:
            key: Configuration key
            default: Default value if not found
            
        Returns:
            Configuration value
        """
        # Check environment variable first
        env_key = f"AEGIS_{key.upper()}"
        env_value = os.environ.get(env_key)
        if env_value is not None:
            return self._parse_value(env_value)
        
        # Check cache
        if key in self.config_cache:
            return self.config_cache[key]
        
        # Use default
        value = self.DEFAULTS.get(key, default)
        self.config_cache[key] = value
        return value
    
    def is_enabled(self, kill_switch: KillSwitch) -> bool:
        """Check if a kill switch is enabled.
        
        Args:
            kill_switch: Kill switch to check
            
        Returns:
            True if enabled
        """
        return bool(self.get(kill_switch.value, False))
    
    def set(self, key: str, value: Any) -> bool:
        """Set configuration value in cache.
        
        Note: This only sets the value in the local cache.
        Environment variables take precedence on next read.
        
        Args:
            key: Configuration key
            value: Configuration value
            
        Returns:
            True (always succeeds for local cache)
        """
        self.config_cache[key] = value
        logger.info(f"Set config in cache: {key} = {value}")
        return True
    
    def _parse_value(self, value: str) -> Any:
        """Parse string value to appropriate type."""
        # Try boolean
        if value.lower() in ("true", "yes", "1", "on"):
            return True
        if value.lower() in ("false", "no", "0", "off"):
            return False
        
        # Try integer
        try:
            return int(value)
        except ValueError:
            pass
        
        # Try float
        try:
            return float(value)
        except ValueError:
            pass
        
        # Return as string
        return value
    
    def clear_cache(self) -> None:
        """Clear the configuration cache."""
        self.config_cache.clear()


class EmergencyControl:
    """Emergency control system for rapid response.
    
    Provides methods to quickly change system behavior in emergencies.
    """
    
    def __init__(self, config: Optional[DynamicConfig] = None):
        """Initialize emergency control.
        
        Args:
            config: DynamicConfig instance (creates default if None)
        """
        self.config = config or DynamicConfig()
    
    def activate_human_review_only(self) -> bool:
        """Activate human-review-only mode.
        
        No AI decisions are made, all decisions require human review.
        """
        return self.config.set(KillSwitch.FORCE_HUMAN_REVIEW.value, True)
    
    def activate_policy_only_mode(self) -> bool:
        """Activate policy-only mode.
        
        AI agents are disabled, only policy engine runs.
        """
        return self.config.set(KillSwitch.POLICY_ONLY_MODE.value, True)
    
    def activate_shadow_mode(self) -> bool:
        """Activate shadow mode.
        
        AI runs but doesn't affect decisions (for testing).
        """
        return self.config.set(KillSwitch.SHADOW_MODE.value, True)
    
    def disable_agent(self, agent_name: str) -> bool:
        """Disable a specific agent.
        
        Args:
            agent_name: Name of agent (detection, behavior, etc.)
            
        Returns:
            True if successful
        """
        kill_switch = f"disable_{agent_name}_agent"
        return self.config.set(kill_switch, True)
    
    def enable_agent(self, agent_name: str) -> bool:
        """Enable a specific agent.
        
        Args:
            agent_name: Name of agent (detection, behavior, etc.)
            
        Returns:
            True if successful
        """
        kill_switch = f"disable_{agent_name}_agent"
        return self.config.set(kill_switch, False)
    
    def activate_slow_mode(self, delay_ms: int = 500) -> bool:
        """Activate slow mode to add safety delays.
        
        Args:
            delay_ms: Delay in milliseconds
            
        Returns:
            True if successful
        """
        self.config.set("slow_mode_delay_ms", delay_ms)
        return self.config.set(KillSwitch.SLOW_MODE.value, True)
    
    def get_status(self) -> Dict[str, bool]:
        """Get current status of all kill switches.
        
        Returns:
            Dictionary of kill switch states
        """
        status = {}
        for switch in KillSwitch:
            status[switch.value] = self.config.is_enabled(switch)
        return status
    
    def deactivate_all(self) -> bool:
        """Deactivate all emergency controls (restore normal operation).
        
        Returns:
            True if successful
        """
        # Disable emergency modes
        self.config.set(KillSwitch.FORCE_HUMAN_REVIEW.value, False)
        self.config.set(KillSwitch.POLICY_ONLY_MODE.value, False)
        self.config.set(KillSwitch.SHADOW_MODE.value, False)
        self.config.set(KillSwitch.SLOW_MODE.value, False)
        
        # Re-enable agents
        self.config.set(KillSwitch.DISABLE_DETECTION_AGENT.value, False)
        self.config.set(KillSwitch.DISABLE_BEHAVIOR_AGENT.value, False)
        self.config.set(KillSwitch.DISABLE_NETWORK_AGENT.value, False)
        self.config.set(KillSwitch.DISABLE_CONFIDENCE_AGENT.value, False)
        self.config.set(KillSwitch.DISABLE_EXPLANATION_AGENT.value, False)
        
        return True


# Singleton instances
_dynamic_config: Optional[DynamicConfig] = None
_emergency_control: Optional[EmergencyControl] = None


def get_dynamic_config() -> DynamicConfig:
    """Get the global dynamic configuration instance."""
    global _dynamic_config
    if _dynamic_config is None:
        _dynamic_config = DynamicConfig()
    return _dynamic_config


def get_emergency_control() -> EmergencyControl:
    """Get the global emergency control instance."""
    global _emergency_control
    if _emergency_control is None:
        _emergency_control = EmergencyControl(get_dynamic_config())
    return _emergency_control
