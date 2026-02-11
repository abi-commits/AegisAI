"""Tests for configuration settings.

Tests the Config class and environment variable handling.
"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch

from aegis_ai.common.config.settings import (
    Config,
    Environment,
    LogLevel,
    AuditStorageType,
    get_config,
    reset_config,
)


class TestEnvironment:
    """Tests for Environment enum."""
    
    def test_environment_values(self):
        """Test Environment enum values."""
        assert Environment.DEVELOPMENT.value == "development"
        assert Environment.STAGING.value == "staging"
        assert Environment.PRODUCTION.value == "production"
    
    def test_environment_from_string(self):
        """Test creating Environment from string."""
        assert Environment("development") == Environment.DEVELOPMENT
        assert Environment("production") == Environment.PRODUCTION


class TestLogLevel:
    """Tests for LogLevel enum."""
    
    def test_log_level_values(self):
        """Test LogLevel enum values."""
        assert LogLevel.DEBUG.value == "DEBUG"
        assert LogLevel.INFO.value == "INFO"
        assert LogLevel.WARNING.value == "WARNING"
        assert LogLevel.ERROR.value == "ERROR"
        assert LogLevel.CRITICAL.value == "CRITICAL"


class TestAuditStorageType:
    """Tests for AuditStorageType enum."""
    
    def test_storage_type_values(self):
        """Test AuditStorageType enum values."""
        assert AuditStorageType.LOCAL.value == "local"
        assert AuditStorageType.S3.value == "s3"


class TestConfig:
    """Tests for Config class."""
    
    def test_default_config(self):
        """Test Config with default values."""
        # Reset any global state first
        reset_config()
        
        with patch.dict(os.environ, {}, clear=True):
            # Set minimal env vars
            os.environ["AEGIS_ENVIRONMENT"] = "development"
            os.environ["AEGIS_LOG_LEVEL"] = "INFO"
            os.environ["AEGIS_AUDIT_STORAGE_TYPE"] = "local"
            
            config = Config()
            
            assert config.environment == Environment.DEVELOPMENT
            assert config.debug is False
            assert config.log_level == LogLevel.INFO
            assert config.api_host == "0.0.0.0"
            assert config.api_port == 8000
    
    def test_environment_from_env_var(self):
        """Test environment loaded from environment variable."""
        reset_config()
        
        with patch.dict(os.environ, {"AEGIS_ENVIRONMENT": "production"}, clear=False):
            config = Config()
            assert config.environment == Environment.PRODUCTION
    
    def test_debug_mode(self):
        """Test debug mode configuration."""
        reset_config()
        
        with patch.dict(os.environ, {"AEGIS_DEBUG": "true"}, clear=False):
            config = Config()
            assert config.debug is True
        
        reset_config()
        
        with patch.dict(os.environ, {"AEGIS_DEBUG": "false"}, clear=False):
            config = Config()
            assert config.debug is False
    
    def test_api_config(self):
        """Test API configuration from environment."""
        reset_config()
        
        with patch.dict(os.environ, {
            "AEGIS_API_HOST": "127.0.0.1",
            "AEGIS_API_PORT": "9000"
        }, clear=False):
            config = Config()
            assert config.api_host == "127.0.0.1"
            assert config.api_port == 9000
    
    def test_audit_local_storage(self):
        """Test audit configuration for local storage."""
        reset_config()
        
        with patch.dict(os.environ, {
            "AEGIS_AUDIT_STORAGE_TYPE": "local",
            "AEGIS_AUDIT_LOG_DIR": "/tmp/audit"
        }, clear=False):
            config = Config()
            assert config.audit_storage_type == AuditStorageType.LOCAL
            assert config.audit_log_dir == Path("/tmp/audit")
    
    def test_audit_s3_storage_requires_bucket(self):
        """Test that S3 storage requires bucket configuration."""
        reset_config()
        
        with patch.dict(os.environ, {
            "AEGIS_AUDIT_STORAGE_TYPE": "s3",
            "AEGIS_AUDIT_S3_BUCKET": ""  # Empty bucket
        }, clear=False):
            # Remove the bucket env var entirely
            if "AEGIS_AUDIT_S3_BUCKET" in os.environ:
                del os.environ["AEGIS_AUDIT_S3_BUCKET"]
            
            with pytest.raises(ValueError, match="AEGIS_AUDIT_S3_BUCKET"):
                Config()
    
    def test_audit_s3_storage_with_bucket(self):
        """Test S3 storage with bucket configured."""
        reset_config()
        
        with patch.dict(os.environ, {
            "AEGIS_AUDIT_STORAGE_TYPE": "s3",
            "AEGIS_AUDIT_S3_BUCKET": "my-audit-bucket"
        }, clear=False):
            config = Config()
            assert config.audit_storage_type == AuditStorageType.S3
            assert config.audit_s3_bucket == "my-audit-bucket"
    
    def test_is_production(self):
        """Test is_production property."""
        reset_config()
        
        with patch.dict(os.environ, {"AEGIS_ENVIRONMENT": "production"}, clear=False):
            config = Config()
            assert config.is_production is True
            assert config.is_development is False
    
    def test_is_development(self):
        """Test is_development property."""
        reset_config()
        
        with patch.dict(os.environ, {"AEGIS_ENVIRONMENT": "development"}, clear=False):
            config = Config()
            assert config.is_development is True
            assert config.is_production is False
    
    def test_log_dir_property(self):
        """Test log_dir property creates directory."""
        reset_config()
        config = Config()
        
        log_dir = config.log_dir
        assert log_dir.exists()
        assert log_dir.is_dir()
    
    def test_config_dir_property(self):
        """Test config_dir property."""
        reset_config()
        config = Config()
        
        config_dir = config.config_dir
        assert config_dir == config.project_root / "config"


class TestGetConfig:
    """Tests for get_config singleton function."""
    
    def test_get_config_returns_config(self):
        """Test that get_config returns a Config instance."""
        reset_config()
        config = get_config()
        assert isinstance(config, Config)
    
    def test_get_config_returns_same_instance(self):
        """Test that get_config returns the same instance."""
        reset_config()
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2
    
    def test_reset_config_clears_singleton(self):
        """Test that reset_config clears the singleton."""
        reset_config()
        config1 = get_config()
        reset_config()
        config2 = get_config()
        
        # After reset, should be different instances
        # (though they may be equal in value)
        assert config1 is not config2
