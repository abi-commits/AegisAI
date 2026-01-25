"""Test fixtures for AegisAI."""

import pytest
from datetime import datetime
from src.aegis_ai.core.types import LoginEvent


@pytest.fixture
def sample_login_event():
    """Fixture for a sample login event."""
    return LoginEvent(
        event_id="test_event_1",
        user_id="test_user_1",
        session_id="test_session_1",
        device_id="test_device_1",
        ip_address="192.168.1.1",
        geo_location="Test City",
        timestamp=datetime.utcnow(),
        success=True,
    )


@pytest.fixture
def sample_suspicious_event():
    """Fixture for a suspicious login event."""
    return LoginEvent(
        event_id="test_event_sus",
        user_id="test_user_2",
        session_id="test_session_2",
        device_id="unknown_device",
        ip_address="203.0.113.0",  # Example IP from different region
        geo_location="Unknown Location",
        timestamp=datetime.utcnow(),
        success=False,
        additional_context={"failed_attempts": 5},
    )
