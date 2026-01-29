"""Kill Switches - Mandatory in Production.

Dynamic configuration system for emergency controls.

Philosophy:
"If something feels wrong, you slow the system down instead of letting it run wild."
"This is professional paranoia."

Features:
- Feature flags (enable/disable agents)
- Emergency modes (force human review)
- Policy overrides (run policy-only)
- Agent disabling (turn off specific agents)
- Graceful degradation

Backed by:
- AWS AppConfig (for staged rollouts)
- Parameter Store (for instant updates)
- Local cache with TTL
"""

import logging
import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional
from enum import Enum
import os

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class ConfigSource(str, Enum):
    """Sources for configuration."""
    APPCONFIG = "appconfig"           # AWS AppConfig (staged)
    PARAMETER_STORE = "parameter_store"  # Parameter Store (instant)
    ENVIRONMENT = "environment"        # Environment variables


class KillSwitch(str, Enum):
    """Kill switch names."""
    # Agent controls
    DISABLE_DETECTION_AGENT = "disable_detection_agent"
    DISABLE_BEHAVIOR_AGENT = "disable_behavior_agent"
    DISABLE_NETWORK_AGENT = "disable_network_agent"
    DISABLE_CONFIDENCE_AGENT = "disable_confidence_agent"
    DISABLE_EXPLANATION_AGENT = "disable_explanation_agent"
    
    # System modes
    FORCE_HUMAN_REVIEW = "force_human_review"      # Review all decisions
    POLICY_ONLY_MODE = "policy_only_mode"          # Only use policies, no AI
    SHADOW_MODE = "shadow_mode"                    # AI runs but doesn't affect decisions
    SLOW_MODE = "slow_mode"                        # Add delays for safety
    
    # Feature flags
    ENABLE_MODEL_DRIFT_DETECTION = "enable_model_drift_detection"
    ENABLE_CONFIDENCE_CALIBRATION = "enable_confidence_calibration"
    ENABLE_EXPLANATION_GENERATION = "enable_explanation_generation"
    
    # Escalation controls
    ESCALATE_HIGH_RISK = "escalate_high_risk"      # Escalate if risk > threshold
    ESCALATE_DISAGREEMENT = "escalate_disagreement" # Escalate if agents disagree
    ESCALATE_UNUSUAL_PATTERN = "escalate_unusual_pattern"


class DynamicConfig:
    """Dynamic configuration with multiple sources.
    
    Load order:
    1. Environment variables (highest priority)
    2. Parameter Store (instant updates)
    3. AppConfig (staged rollouts)
    4. Defaults (lowest priority)
    
    Environment variables:
    - CONFIG_SOURCE: appconfig, parameter_store, or environment
    - APPCONFIG_APPLICATION: AppConfig application name
    - APPCONFIG_ENVIRONMENT: AppConfig environment name
    - APPCONFIG_PROFILE: AppConfig configuration profile
    - PARAMETER_STORE_PREFIX: Parameter Store prefix
    """
    
    DEFAULT_REGION = "us-east-1"
    DEFAULT_CACHE_TTL_SECONDS = 60
    
    # Default configuration (safe defaults)
    DEFAULTS = {
        "disable_detection_agent": False,
        "disable_behavior_agent": False,
        "disable_network_agent": False,
        "disable_confidence_agent": False,
        "disable_explanation_agent": False,
        "force_human_review": False,
        "policy_only_mode": False,
        "shadow_mode": False,
        "slow_mode": False,
        "enable_model_drift_detection": True,
        "enable_confidence_calibration": True,
        "enable_explanation_generation": True,
        "escalate_high_risk": True,
        "escalate_disagreement": True,
        "escalate_unusual_pattern": True,
        "slow_mode_delay_ms": 0,
        "high_risk_threshold": 0.8,
        "disagreement_threshold": 0.3,
    }
    
    def __init__(
        self,
        source: ConfigSource = ConfigSource.ENVIRONMENT,
        region: Optional[str] = None,
        aws_profile: Optional[str] = None,
        cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
    ):
        """Initialize dynamic configuration.
        
        Args:
            source: Configuration source
            region: AWS region
            aws_profile: AWS profile
            cache_ttl_seconds: Cache TTL for fetched configs
        """
        self.source = source
        self.region = region or os.environ.get("AWS_REGION", self.DEFAULT_REGION)
        self.cache_ttl_seconds = cache_ttl_seconds
        self.config_cache: Dict[str, Any] = {}
        self.cache_time: Optional[datetime] = None
        
        # Initialize AWS clients if needed
        if source != ConfigSource.ENVIRONMENT:
            if aws_profile:
                session = boto3.Session(profile_name=aws_profile)
                self.ssm_client = session.client("ssm", region_name=self.region)
                self.appconfig_client = session.client("appconfig", region_name=self.region)
            else:
                self.ssm_client = boto3.client("ssm", region_name=self.region)
                self.appconfig_client = boto3.client("appconfig", region_name=self.region)
        
        # Load AppConfig parameters
        self.appconfig_app = os.environ.get("APPCONFIG_APPLICATION", "aegis-ai")
        self.appconfig_env = os.environ.get("APPCONFIG_ENVIRONMENT", "production")
        self.appconfig_profile = os.environ.get("APPCONFIG_PROFILE", "aegis-config")
        self.parameter_store_prefix = os.environ.get("PARAMETER_STORE_PREFIX", "/aegis/")
        
        logger.info(
            f"Initialized DynamicConfig: source={source.value}, "
            f"region={self.region}, cache_ttl={cache_ttl_seconds}s"
        )
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value.
        
        Load order:
        1. Environment variable
        2. Cache
        3. Parameter Store / AppConfig
        4. Default value
        
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
        if self._is_cache_valid() and key in self.config_cache:
            return self.config_cache[key]
        
        # Fetch from source
        if self.source == ConfigSource.ENVIRONMENT:
            value = self.DEFAULTS.get(key, default)
        elif self.source == ConfigSource.PARAMETER_STORE:
            value = self._get_from_parameter_store(key)
        elif self.source == ConfigSource.APPCONFIG:
            value = self._get_from_appconfig(key)
        else:
            value = self.DEFAULTS.get(key, default)
        
        # Cache and return
        if value is not None:
            self.config_cache[key] = value
        
        return value if value is not None else default
    
    def is_enabled(self, kill_switch: KillSwitch) -> bool:
        """Check if a kill switch is enabled.
        
        Args:
            kill_switch: Kill switch to check
            
        Returns:
            True if enabled
        """
        return bool(self.get(kill_switch.value, False))
    
    def set(self, key: str, value: Any) -> bool:
        """Set configuration value (if source supports it).
        
        Args:
            key: Configuration key
            value: Configuration value
            
        Returns:
            True if successful
        """
        if self.source == ConfigSource.ENVIRONMENT:
            # Can't set environment variables
            logger.warning("Cannot set config with ENVIRONMENT source")
            return False
        
        if self.source == ConfigSource.PARAMETER_STORE:
            return self._set_in_parameter_store(key, value)
        elif self.source == ConfigSource.APPCONFIG:
            logger.warning("AppConfig is read-only in this implementation")
            return False
        
        return False
    
    def _is_cache_valid(self) -> bool:
        """Check if cache is still valid."""
        if self.cache_time is None:
            return False
        
        age = (datetime.now(timezone.utc) - self.cache_time).total_seconds()
        return age < self.cache_ttl_seconds
    
    def _parse_value(self, value: str) -> Any:
        """Parse string value to appropriate type."""
        # Try boolean
        if value.lower() in ("true", "yes", "1"):
            return True
        if value.lower() in ("false", "no", "0"):
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
    
    def _get_from_parameter_store(self, key: str) -> Optional[Any]:
        """Get value from Parameter Store.
        
        Args:
            key: Parameter key
            
        Returns:
            Parameter value or None
        """
        try:
            param_name = f"{self.parameter_store_prefix}{key}"
            response = self.ssm_client.get_parameter(
                Name=param_name,
                WithDecryption=True,
            )
            
            value = response["Parameter"]["Value"]
            return self._parse_value(value)
        
        except self.ssm_client.exceptions.ParameterNotFound:
            # Use default
            return self.DEFAULTS.get(key)
        except ClientError as e:
            logger.warning(f"Failed to get parameter {key}: {e}")
            return self.DEFAULTS.get(key)
    
    def _set_in_parameter_store(self, key: str, value: Any) -> bool:
        """Set value in Parameter Store.
        
        Args:
            key: Parameter key
            value: Parameter value
            
        Returns:
            True if successful
        """
        try:
            param_name = f"{self.parameter_store_prefix}{key}"
            self.ssm_client.put_parameter(
                Name=param_name,
                Value=str(value),
                Type="String",
                Overwrite=True,
            )
            
            # Invalidate cache
            self.cache_time = None
            
            logger.info(f"Updated parameter: {key} = {value}")
            return True
        
        except ClientError as e:
            logger.error(f"Failed to set parameter {key}: {e}")
            return False
    
    def _get_from_appconfig(self, key: str) -> Optional[Any]:
        """Get value from AppConfig.
        
        Args:
            key: Configuration key
            
        Returns:
            Configuration value or None
        """
        try:
            response = self.appconfig_client.get_configuration(
                Application=self.appconfig_app,
                Environment=self.appconfig_env,
                Configuration=self.appconfig_profile,
                ClientId="aegis-service",
            )
            
            config_data = json.loads(response["Content"].read().decode())
            
            # Cache the full config
            self.config_cache = config_data
            self.cache_time = datetime.now(timezone.utc)
            
            return config_data.get(key)
        
        except ClientError as e:
            logger.warning(f"Failed to get AppConfig: {e}")
            return self.DEFAULTS.get(key)


class EmergencyControl:
    """Emergency control system for rapid response."""
    
    def __init__(self, config: DynamicConfig):
        """Initialize emergency control.
        
        Args:
            config: DynamicConfig instance
        """
        self.config = config
    
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
    
    def activate_slow_mode(self, delay_ms: int = 500) -> bool:
        """Activate slow mode to add safety delays.
        
        Args:
            delay_ms: Delay in milliseconds
            
        Returns:
            True if successful
        """
        return self.config.set(KillSwitch.SLOW_MODE.value, True) and \
               self.config.set("slow_mode_delay_ms", delay_ms)
    
    def disable_feature(self, feature_name: str) -> bool:
        """Disable a feature.
        
        Args:
            feature_name: Feature to disable
            
        Returns:
            True if successful
        """
        return self.config.set(f"enable_{feature_name}", False)
    
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
        all_ok = True
        
        # Disable emergency modes
        all_ok &= self.config.set(KillSwitch.FORCE_HUMAN_REVIEW.value, False)
        all_ok &= self.config.set(KillSwitch.POLICY_ONLY_MODE.value, False)
        all_ok &= self.config.set(KillSwitch.SHADOW_MODE.value, False)
        all_ok &= self.config.set(KillSwitch.SLOW_MODE.value, False)
        
        # Re-enable agents
        all_ok &= self.config.set(KillSwitch.DISABLE_DETECTION_AGENT.value, False)
        all_ok &= self.config.set(KillSwitch.DISABLE_BEHAVIOR_AGENT.value, False)
        all_ok &= self.config.set(KillSwitch.DISABLE_NETWORK_AGENT.value, False)
        
        return all_ok
