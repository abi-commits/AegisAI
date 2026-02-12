"""Tests for Kill Switches Layer.

Tests the emergency control and feature flag system.
"""

import os
import pytest
from unittest.mock import patch

from aegis_ai.common.config.emergency import (
    ConfigSource,
    KillSwitch,
    DynamicConfig,
    EmergencyControl,
    get_dynamic_config,
    get_emergency_control,
)


class TestKillSwitch:
    """Tests for KillSwitch enum."""
    
    def test_agent_kill_switches(self):
        """Test agent control kill switches."""
        assert KillSwitch.DISABLE_DETECTION_AGENT.value == "disable_detection_agent"
        assert KillSwitch.DISABLE_BEHAVIOR_AGENT.value == "disable_behavior_agent"
        assert KillSwitch.DISABLE_NETWORK_AGENT.value == "disable_network_agent"
        assert KillSwitch.DISABLE_CONFIDENCE_AGENT.value == "disable_confidence_agent"
        assert KillSwitch.DISABLE_EXPLANATION_AGENT.value == "disable_explanation_agent"
    
    def test_system_mode_kill_switches(self):
        """Test system mode kill switches."""
        assert KillSwitch.FORCE_HUMAN_REVIEW.value == "force_human_review"
        assert KillSwitch.POLICY_ONLY_MODE.value == "policy_only_mode"
        assert KillSwitch.SHADOW_MODE.value == "shadow_mode"
        assert KillSwitch.SLOW_MODE.value == "slow_mode"
    
    def test_feature_flag_kill_switches(self):
        """Test feature flag kill switches."""
        assert KillSwitch.ENABLE_MODEL_DRIFT_DETECTION.value == "enable_model_drift_detection"
        assert KillSwitch.ENABLE_CONFIDENCE_CALIBRATION.value == "enable_confidence_calibration"
        assert KillSwitch.ENABLE_EXPLANATION_GENERATION.value == "enable_explanation_generation"
    
    def test_escalation_kill_switches(self):
        """Test escalation control kill switches."""
        assert KillSwitch.ESCALATE_HIGH_RISK.value == "escalate_high_risk"
        assert KillSwitch.ESCALATE_DISAGREEMENT.value == "escalate_disagreement"
        assert KillSwitch.ESCALATE_UNUSUAL_PATTERN.value == "escalate_unusual_pattern"


class TestDynamicConfig:
    """Tests for DynamicConfig."""
    
    def test_environment_source_initialization(self):
        """Test initializing with environment source."""
        config = DynamicConfig(source=ConfigSource.ENVIRONMENT)
        
        assert config.source == ConfigSource.ENVIRONMENT
        assert config.cache_ttl_seconds == 60
    
    def test_get_default_value(self):
        """Test getting default value."""
        config = DynamicConfig(source=ConfigSource.ENVIRONMENT)
        
        # These should use defaults
        assert config.get("disable_detection_agent") is False
        assert config.get("enable_model_drift_detection") is True
        assert config.get("high_risk_threshold") == 0.8
    
    def test_get_nonexistent_key_returns_default(self):
        """Test getting nonexistent key returns provided default."""
        config = DynamicConfig(source=ConfigSource.ENVIRONMENT)
        
        # Key exists in DEFAULTS, so it returns default value
        assert config.get("nonexistent_key", "fallback") == "fallback"
        # Key not in DEFAULTS, so it returns None
        assert config.get("truly_nonexistent_key_xyz_123") is None
    
    def test_get_environment_variable(self):
        """Test getting value from environment variable."""
        with patch.dict(os.environ, {"AEGIS_DISABLE_DETECTION_AGENT": "true"}):
            config = DynamicConfig(source=ConfigSource.ENVIRONMENT)
            
            value = config.get("disable_detection_agent")
            assert value is True
    
    def test_environment_variable_takes_precedence(self):
        """Test that environment variable takes precedence over defaults."""
        with patch.dict(os.environ, {"AEGIS_HIGH_RISK_THRESHOLD": "0.95"}):
            config = DynamicConfig(source=ConfigSource.ENVIRONMENT)
            
            value = config.get("high_risk_threshold")
            assert value == 0.95
    
    def test_is_enabled_kill_switch(self):
        """Test checking if kill switch is enabled."""
        config = DynamicConfig(source=ConfigSource.ENVIRONMENT)
        
        # Default should be False
        assert config.is_enabled(KillSwitch.POLICY_ONLY_MODE) is False
        assert config.is_enabled(KillSwitch.DISABLE_DETECTION_AGENT) is False
    
    def test_is_enabled_kill_switch_from_env(self):
        """Test checking kill switch from environment."""
        with patch.dict(os.environ, {"AEGIS_POLICY_ONLY_MODE": "true"}):
            config = DynamicConfig(source=ConfigSource.ENVIRONMENT)
            
            assert config.is_enabled(KillSwitch.POLICY_ONLY_MODE) is True
    
    def test_set_updates_cache(self):
        """Test that set updates the local cache."""
        config = DynamicConfig(source=ConfigSource.ENVIRONMENT)
        
        result = config.set("disable_detection_agent", True)
        
        assert result is True
        assert config.config_cache["disable_detection_agent"] is True
    
    def test_parse_boolean_values(self):
        """Test parsing boolean string values."""
        config = DynamicConfig(source=ConfigSource.ENVIRONMENT)
        
        # True values
        assert config._parse_value("true") is True
        assert config._parse_value("TRUE") is True
        assert config._parse_value("yes") is True
        assert config._parse_value("YES") is True
        assert config._parse_value("1") is True
        assert config._parse_value("on") is True
        
        # False values
        assert config._parse_value("false") is False
        assert config._parse_value("FALSE") is False
        assert config._parse_value("no") is False
        assert config._parse_value("NO") is False
        assert config._parse_value("0") is False
        assert config._parse_value("off") is False
    
    def test_parse_numeric_values(self):
        """Test parsing numeric string values."""
        config = DynamicConfig(source=ConfigSource.ENVIRONMENT)
        
        assert config._parse_value("42") == 42
        assert config._parse_value("-10") == -10
        assert config._parse_value("3.14") == 3.14
        assert config._parse_value("-2.5") == -2.5
    
    def test_parse_string_values(self):
        """Test parsing string values that aren't booleans or numbers."""
        config = DynamicConfig(source=ConfigSource.ENVIRONMENT)
        
        assert config._parse_value("hello") == "hello"
        assert config._parse_value("policy-v2") == "policy-v2"
        assert config._parse_value("") == ""
    
    def test_clear_cache(self):
        """Test clearing the configuration cache."""
        config = DynamicConfig(source=ConfigSource.ENVIRONMENT)
        
        config.set("test_key", "test_value")
        assert "test_key" in config.config_cache
        
        config.clear_cache()
        assert len(config.config_cache) == 0


class TestEmergencyControl:
    """Tests for EmergencyControl."""
    
    def test_initialization(self):
        """Test EmergencyControl initialization."""
        control = EmergencyControl()
        assert control.config is not None
    
    def test_initialization_with_config(self):
        """Test EmergencyControl initialization with provided config."""
        config = DynamicConfig(source=ConfigSource.ENVIRONMENT)
        control = EmergencyControl(config)
        assert control.config is config
    
    def test_activate_human_review_only(self):
        """Test activating human-review-only mode."""
        config = DynamicConfig(source=ConfigSource.ENVIRONMENT)
        control = EmergencyControl(config)
        
        result = control.activate_human_review_only()
        
        assert result is True
        assert config.is_enabled(KillSwitch.FORCE_HUMAN_REVIEW) is True
    
    def test_activate_policy_only_mode(self):
        """Test activating policy-only mode."""
        config = DynamicConfig(source=ConfigSource.ENVIRONMENT)
        control = EmergencyControl(config)
        
        result = control.activate_policy_only_mode()
        
        assert result is True
        assert config.is_enabled(KillSwitch.POLICY_ONLY_MODE) is True
    
    def test_activate_shadow_mode(self):
        """Test activating shadow mode."""
        config = DynamicConfig(source=ConfigSource.ENVIRONMENT)
        control = EmergencyControl(config)
        
        result = control.activate_shadow_mode()
        
        assert result is True
        assert config.is_enabled(KillSwitch.SHADOW_MODE) is True
    
    def test_disable_agent(self):
        """Test disabling a specific agent."""
        config = DynamicConfig(source=ConfigSource.ENVIRONMENT)
        control = EmergencyControl(config)
        
        result = control.disable_agent("detection")
        
        assert result is True
        assert config.get("disable_detection_agent") is True
    
    def test_enable_agent(self):
        """Test enabling a specific agent."""
        config = DynamicConfig(source=ConfigSource.ENVIRONMENT)
        control = EmergencyControl(config)
        
        # First disable
        control.disable_agent("detection")
        assert config.get("disable_detection_agent") is True
        
        # Then enable
        result = control.enable_agent("detection")
        
        assert result is True
        assert config.get("disable_detection_agent") is False
    
    def test_activate_slow_mode(self):
        """Test activating slow mode with delay."""
        config = DynamicConfig(source=ConfigSource.ENVIRONMENT)
        control = EmergencyControl(config)
        
        result = control.activate_slow_mode(delay_ms=500)
        
        assert result is True
        assert config.is_enabled(KillSwitch.SLOW_MODE) is True
        assert config.get("slow_mode_delay_ms") == 500
    
    def test_get_status(self):
        """Test getting status of all kill switches."""
        config = DynamicConfig(source=ConfigSource.ENVIRONMENT)
        control = EmergencyControl(config)
        
        status = control.get_status()
        
        # Check that all kill switches are in the status
        for switch in KillSwitch:
            assert switch.value in status
            assert isinstance(status[switch.value], bool)
    
    def test_deactivate_all(self):
        """Test deactivating all emergency controls."""
        config = DynamicConfig(source=ConfigSource.ENVIRONMENT)
        control = EmergencyControl(config)
        
        # Activate some controls
        control.activate_human_review_only()
        control.activate_policy_only_mode()
        control.disable_agent("detection")
        
        # Verify they're activated
        assert config.is_enabled(KillSwitch.FORCE_HUMAN_REVIEW) is True
        assert config.is_enabled(KillSwitch.POLICY_ONLY_MODE) is True
        
        # Deactivate all
        result = control.deactivate_all()
        
        assert result is True
        assert config.is_enabled(KillSwitch.FORCE_HUMAN_REVIEW) is False
        assert config.is_enabled(KillSwitch.POLICY_ONLY_MODE) is False
        assert config.is_enabled(KillSwitch.SHADOW_MODE) is False
        assert config.is_enabled(KillSwitch.SLOW_MODE) is False
        assert config.is_enabled(KillSwitch.DISABLE_DETECTION_AGENT) is False


class TestSingletons:
    """Tests for singleton accessor functions."""
    
    def test_get_dynamic_config_returns_valid_instance(self):
        """Test that get_dynamic_config returns a valid instance."""
        config = get_dynamic_config()
        assert isinstance(config, DynamicConfig)
    
    def test_get_emergency_control_returns_valid_instance(self):
        """Test that get_emergency_control returns a valid instance."""
        control = get_emergency_control()
        
        assert isinstance(control, EmergencyControl)
        assert isinstance(control.config, DynamicConfig)
