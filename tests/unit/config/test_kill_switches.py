"""Tests for Kill Switches Layer (Layer 8)."""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError

from aegis_ai.common.config.emergency import (
    ConfigSource,
    KillSwitch,
    DynamicConfig,
    EmergencyControl,
)


class TestKillSwitch:
    """Tests for KillSwitch enum."""
    
    def test_agent_kill_switches(self):
        """Test agent control kill switches."""
        assert KillSwitch.DISABLE_DETECTION_AGENT
        assert KillSwitch.DISABLE_BEHAVIOR_AGENT
        assert KillSwitch.DISABLE_NETWORK_AGENT
        assert KillSwitch.DISABLE_CONFIDENCE_AGENT
        assert KillSwitch.DISABLE_EXPLANATION_AGENT
    
    def test_system_mode_kill_switches(self):
        """Test system mode kill switches."""
        assert KillSwitch.FORCE_HUMAN_REVIEW
        assert KillSwitch.POLICY_ONLY_MODE
        assert KillSwitch.SHADOW_MODE
        assert KillSwitch.SLOW_MODE
    
    def test_feature_flag_kill_switches(self):
        """Test feature flag kill switches."""
        assert KillSwitch.ENABLE_MODEL_DRIFT_DETECTION
        assert KillSwitch.ENABLE_CONFIDENCE_CALIBRATION
        assert KillSwitch.ENABLE_EXPLANATION_GENERATION
    
    def test_escalation_kill_switches(self):
        """Test escalation control kill switches."""
        assert KillSwitch.ESCALATE_HIGH_RISK
        assert KillSwitch.ESCALATE_DISAGREEMENT
        assert KillSwitch.ESCALATE_UNUSUAL_PATTERN


class TestDynamicConfig:
    """Tests for DynamicConfig."""
    
    def test_environment_source_initialization(self):
        """Test initializing with environment source."""
        config = DynamicConfig(source=ConfigSource.ENVIRONMENT)
        
        assert config.source == ConfigSource.ENVIRONMENT
        assert config.cache_ttl_seconds == DynamicConfig.DEFAULT_CACHE_TTL_SECONDS
    
    def test_get_default_value(self):
        """Test getting default value."""
        config = DynamicConfig(source=ConfigSource.ENVIRONMENT)
        
        # These should use defaults
        assert config.get("disable_detection_agent") is False
        assert config.get("enable_model_drift_detection") is True
    
    def test_get_environment_variable(self):
        """Test getting value from environment variable."""
        with patch.dict(os.environ, {"AEGIS_DISABLE_DETECTION_AGENT": "true"}):
            config = DynamicConfig(source=ConfigSource.ENVIRONMENT)
            
            value = config.get("disable_detection_agent")
            assert value is True
    
    def test_is_enabled_kill_switch(self):
        """Test checking if kill switch is enabled."""
        config = DynamicConfig(source=ConfigSource.ENVIRONMENT)
        
        # Default should be False
        assert config.is_enabled(KillSwitch.POLICY_ONLY_MODE) is False
    
    def test_is_enabled_kill_switch_from_env(self):
        """Test checking kill switch from environment."""
        with patch.dict(os.environ, {"AEGIS_POLICY_ONLY_MODE": "true"}):
            config = DynamicConfig(source=ConfigSource.ENVIRONMENT)
            
            assert config.is_enabled(KillSwitch.POLICY_ONLY_MODE) is True
    
    @patch("aegis_ai.common.config.emergency.boto3.client")
    def test_parameter_store_source(self, mock_boto3_client):
        """Test initializing with Parameter Store source."""
        mock_ssm = MagicMock()
        mock_boto3_client.return_value = mock_ssm
        
        config = DynamicConfig(source=ConfigSource.PARAMETER_STORE)
        
        assert config.source == ConfigSource.PARAMETER_STORE
    
    @patch("aegis_ai.common.config.emergency.boto3.client")
    def test_get_from_parameter_store(self, mock_boto3_client):
        """Test getting value from Parameter Store."""
        mock_ssm = MagicMock()
        mock_boto3_client.return_value = mock_ssm
        
        mock_ssm.get_parameter.return_value = {
            "Parameter": {"Value": "true"}
        }
        
        config = DynamicConfig(
            source=ConfigSource.PARAMETER_STORE,
            region="us-east-1",
        )
        
        value = config.get("disable_detection_agent")
        
        # Should call Parameter Store
        assert mock_ssm.get_parameter.called
    
    @patch("aegis_ai.common.config.emergency.boto3.client")
    def test_parameter_not_found_uses_default(self, mock_boto3_client):
        """Test that missing parameter falls back to default."""
        mock_ssm = MagicMock()
        mock_boto3_client.return_value = mock_ssm
        
        mock_ssm.get_parameter.side_effect = mock_ssm.exceptions.ParameterNotFound({}, "")
        
        config = DynamicConfig(
            source=ConfigSource.PARAMETER_STORE,
            region="us-east-1",
        )
        
        value = config.get("disable_detection_agent")
        
        # Should return default (False)
        assert value is False
    
    @patch("aegis_ai.common.config.emergency.boto3.client")
    def test_set_in_parameter_store(self, mock_boto3_client):
        """Test setting value in Parameter Store."""
        mock_ssm = MagicMock()
        mock_boto3_client.return_value = mock_ssm
        
        config = DynamicConfig(
            source=ConfigSource.PARAMETER_STORE,
            region="us-east-1",
        )
        
        result = config.set("disable_detection_agent", True)
        
        assert result is True
        assert mock_ssm.put_parameter.called
    
    @patch("aegis_ai.common.config.emergency.boto3.client")
    def test_set_fails_with_environment_source(self, mock_boto3_client):
        """Test that set fails with environment source."""
        config = DynamicConfig(source=ConfigSource.ENVIRONMENT)
        
        result = config.set("disable_detection_agent", True)
        
        assert result is False
    
    def test_parse_boolean_values(self):
        """Test parsing boolean string values."""
        config = DynamicConfig(source=ConfigSource.ENVIRONMENT)
        
        assert config._parse_value("true") is True
        assert config._parse_value("yes") is True
        assert config._parse_value("1") is True
        assert config._parse_value("false") is False
        assert config._parse_value("no") is False
        assert config._parse_value("0") is False
    
    def test_parse_numeric_values(self):
        """Test parsing numeric string values."""
        config = DynamicConfig(source=ConfigSource.ENVIRONMENT)
        
        assert config._parse_value("42") == 42
        assert config._parse_value("3.14") == 3.14
    
    def test_parse_string_values(self):
        """Test parsing string values."""
        config = DynamicConfig(source=ConfigSource.ENVIRONMENT)
        
        assert config._parse_value("hello") == "hello"
        assert config._parse_value("policy-v2") == "policy-v2"


class TestEmergencyControl:
    """Tests for EmergencyControl."""
    
    def test_activation_human_review_only(self):
        """Test activating human-review-only mode."""
        config = DynamicConfig(source=ConfigSource.ENVIRONMENT)
        control = EmergencyControl(config)
        
        # Should fail with environment source (read-only)
        result = control.activate_human_review_only()
        assert result is False
    
    @patch("aegis_ai.common.config.emergency.boto3.client")
    def test_activate_human_review_only_parameter_store(self, mock_boto3_client):
        """Test activating human review with Parameter Store."""
        mock_ssm = MagicMock()
        mock_boto3_client.return_value = mock_ssm
        
        config = DynamicConfig(
            source=ConfigSource.PARAMETER_STORE,
            region="us-east-1",
        )
        control = EmergencyControl(config)
        
        result = control.activate_human_review_only()
        
        assert result is True
        assert mock_ssm.put_parameter.called
    
    @patch("aegis_ai.common.config.emergency.boto3.client")
    def test_activate_policy_only_mode(self, mock_boto3_client):
        """Test activating policy-only mode."""
        mock_ssm = MagicMock()
        mock_boto3_client.return_value = mock_ssm
        
        config = DynamicConfig(
            source=ConfigSource.PARAMETER_STORE,
            region="us-east-1",
        )
        control = EmergencyControl(config)
        
        result = control.activate_policy_only_mode()
        
        assert result is True
    
    @patch("aegis_ai.common.config.emergency.boto3.client")
    def test_activate_shadow_mode(self, mock_boto3_client):
        """Test activating shadow mode."""
        mock_ssm = MagicMock()
        mock_boto3_client.return_value = mock_ssm
        
        config = DynamicConfig(
            source=ConfigSource.PARAMETER_STORE,
            region="us-east-1",
        )
        control = EmergencyControl(config)
        
        result = control.activate_shadow_mode()
        
        assert result is True
    
    @patch("aegis_ai.common.config.emergency.boto3.client")
    def test_disable_agent(self, mock_boto3_client):
        """Test disabling a specific agent."""
        mock_ssm = MagicMock()
        mock_boto3_client.return_value = mock_ssm
        
        config = DynamicConfig(
            source=ConfigSource.PARAMETER_STORE,
            region="us-east-1",
        )
        control = EmergencyControl(config)
        
        result = control.disable_agent("detection")
        
        assert result is True
    
    @patch("aegis_ai.common.config.emergency.boto3.client")
    def test_activate_slow_mode(self, mock_boto3_client):
        """Test activating slow mode with delay."""
        mock_ssm = MagicMock()
        mock_boto3_client.return_value = mock_ssm
        
        config = DynamicConfig(
            source=ConfigSource.PARAMETER_STORE,
            region="us-east-1",
        )
        control = EmergencyControl(config)
        
        result = control.activate_slow_mode(delay_ms=1000)
        
        assert result is True
        # Should set both slow_mode and delay
        assert mock_ssm.put_parameter.call_count >= 2
    
    @patch("aegis_ai.common.config.emergency.boto3.client")
    def test_disable_feature(self, mock_boto3_client):
        """Test disabling a feature."""
        mock_ssm = MagicMock()
        mock_boto3_client.return_value = mock_ssm
        
        config = DynamicConfig(
            source=ConfigSource.PARAMETER_STORE,
            region="us-east-1",
        )
        control = EmergencyControl(config)
        
        result = control.disable_feature("model_drift_detection")
        
        assert result is True
    
    def test_get_status_environment_source(self):
        """Test getting status of all kill switches."""
        config = DynamicConfig(source=ConfigSource.ENVIRONMENT)
        control = EmergencyControl(config)
        
        status = control.get_status()
        
        assert isinstance(status, dict)
        assert len(status) > 0
        # All should be False (defaults)
        assert all(v is False for k, v in status.items() 
                   if k.startswith("disable_"))
    
    @patch("aegis_ai.common.config.emergency.boto3.client")
    def test_deactivate_all(self, mock_boto3_client):
        """Test deactivating all emergency controls."""
        mock_ssm = MagicMock()
        mock_boto3_client.return_value = mock_ssm
        
        config = DynamicConfig(
            source=ConfigSource.PARAMETER_STORE,
            region="us-east-1",
        )
        control = EmergencyControl(config)
        
        result = control.deactivate_all()
        
        assert result is True
        # Should set multiple parameters
        assert mock_ssm.put_parameter.call_count >= 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
