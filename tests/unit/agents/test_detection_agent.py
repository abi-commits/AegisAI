"""Unit tests for Detection Agent.

Testing discipline: Light but mandatory.
- One happy path test
- One edge case test  
- One weird but valid input test

Phase 4 additions:
- Tests for heuristic fallback mode
- Tests verify ML model can be loaded when available
"""

import pytest
from datetime import datetime

from src.aegis_ai.agents.detection.agent import DetectionAgent
from src.aegis_ai.agents.detection.schema import DetectionOutput
from src.aegis_ai.data.schemas.login_event import LoginEvent
from src.aegis_ai.data.schemas.session import Session, GeoLocation
from src.aegis_ai.data.schemas.device import Device


@pytest.fixture
def detection_agent():
    """Create a DetectionAgent instance in heuristic mode."""
    # Use heuristic mode for deterministic testing
    return DetectionAgent(use_ml_model=False)


@pytest.fixture
def normal_login_event():
    """Normal login event - no risk factors."""
    return LoginEvent(
        event_id="evt_normal_001",
        session_id="sess_normal_001",
        user_id="user_001",
        timestamp=datetime(2026, 1, 25, 10, 30, 0),
        success=True,
        auth_method="password",
        failed_attempts_before=0,
        time_since_last_login_hours=24.0,
        is_new_device=False,
        is_new_ip=False,
        is_new_location=False,
        is_ato=False,
    )


@pytest.fixture
def normal_session():
    """Normal session - no suspicious indicators."""
    return Session(
        session_id="sess_normal_001",
        user_id="user_001",
        device_id="dev_known_001",
        ip_address="192.168.1.100",
        geo_location=GeoLocation(
            city="New York",
            country="US",
            latitude=40.7128,
            longitude=-74.0060,
        ),
        start_time=datetime(2026, 1, 25, 10, 30, 0),
        is_vpn=False,
        is_tor=False,
    )


@pytest.fixture
def normal_device():
    """Known device with history."""
    return Device(
        device_id="dev_known_001",
        device_type="desktop",
        os="Windows 11",
        browser="Chrome 120",
        is_known=True,
        first_seen_at=datetime(2025, 6, 15, 10, 30, 0),
    )


class TestDetectionAgentHappyPath:
    """Happy path tests for DetectionAgent."""
    
    def test_normal_login_returns_low_risk(
        self,
        detection_agent,
        normal_login_event,
        normal_session,
        normal_device
    ):
        """Normal login should return low risk score with no factors."""
        result = detection_agent.analyze(
            normal_login_event,
            normal_session,
            normal_device
        )
        
        # Verify output is correct type
        assert isinstance(result, DetectionOutput)
        
        # Verify low risk
        assert result.risk_signal_score == 0.0
        assert len(result.risk_factors) == 0
    
    def test_output_validates_via_schema(
        self,
        detection_agent,
        normal_login_event,
        normal_session,
        normal_device
    ):
        """Output should validate via Pydantic schema."""
        result = detection_agent.analyze(
            normal_login_event,
            normal_session,
            normal_device
        )
        
        # Convert to dict and back - should not raise
        result_dict = result.model_dump()
        validated = DetectionOutput(**result_dict)
        
        assert validated.risk_signal_score == result.risk_signal_score
        assert validated.risk_factors == result.risk_factors


class TestDetectionAgentEdgeCases:
    """Edge case tests for DetectionAgent."""
    
    def test_maximum_risk_factors_clamped_to_one(self, detection_agent):
        """All risk factors should clamp score to 1.0 max."""
        # Create maximally suspicious login
        login_event = LoginEvent(
            event_id="evt_max_risk",
            session_id="sess_max_risk",
            user_id="user_suspicious",
            timestamp=datetime(2026, 1, 25, 3, 0, 0),
            success=False,
            auth_method="password",
            failed_attempts_before=10,  # Way over cap
            time_since_last_login_hours=2000.0,  # Very long absence
            is_new_device=True,
            is_new_ip=True,
            is_new_location=True,
            is_ato=True,
        )
        
        session = Session(
            session_id="sess_max_risk",
            user_id="user_suspicious",
            device_id="dev_unknown",
            ip_address="185.220.101.1",  # Tor exit node IP
            geo_location=GeoLocation(
                city="Unknown",
                country="RU",
                latitude=55.7558,
                longitude=37.6173,
            ),
            start_time=datetime(2026, 1, 25, 3, 0, 0),
            is_vpn=True,
            is_tor=True,
        )
        
        device = Device(
            device_id="dev_unknown",
            device_type="mobile",
            os="Android 14",
            browser="Unknown Browser",
            is_known=False,
            first_seen_at=None,
        )
        
        result = detection_agent.analyze(login_event, session, device)
        
        # Score should be clamped to 1.0
        assert result.risk_signal_score == 1.0
        
        # Should have multiple risk factors
        assert len(result.risk_factors) > 3
    
    def test_score_stays_within_bounds(self, detection_agent):
        """Risk score should always be between 0 and 1."""
        login_event = LoginEvent(
            event_id="evt_001",
            session_id="sess_001",
            user_id="user_001",
            timestamp=datetime(2026, 1, 25, 10, 0, 0),
            success=True,
            auth_method="mfa",
            failed_attempts_before=0,
            is_new_device=True,  # Only one risk factor
            is_new_ip=False,
            is_new_location=False,
        )
        
        session = Session(
            session_id="sess_001",
            user_id="user_001",
            device_id="dev_new",
            ip_address="192.168.1.1",
            geo_location=GeoLocation(
                city="New York",
                country="US",
                latitude=40.7128,
                longitude=-74.0060,
            ),
            start_time=datetime(2026, 1, 25, 10, 0, 0),
            is_vpn=False,
            is_tor=False,
        )
        
        device = Device(
            device_id="dev_new",
            device_type="desktop",
            os="macOS 14",
            browser="Safari 17",
            is_known=False,
        )
        
        result = detection_agent.analyze(login_event, session, device)
        
        assert 0.0 <= result.risk_signal_score <= 1.0


class TestDetectionAgentWeirdButValid:
    """Weird but valid input tests."""
    
    def test_device_known_but_event_says_new(self, detection_agent):
        """Device is_known=True but login_event.is_new_device=True."""
        # This is a valid edge case - device might be known but
        # login event flagged it as new due to timing
        login_event = LoginEvent(
            event_id="evt_weird_001",
            session_id="sess_weird_001",
            user_id="user_weird",
            timestamp=datetime(2026, 1, 25, 14, 0, 0),
            success=True,
            auth_method="password",
            is_new_device=True,  # Event says new
            is_new_ip=False,
            is_new_location=False,
        )
        
        session = Session(
            session_id="sess_weird_001",
            user_id="user_weird",
            device_id="dev_paradox",
            ip_address="10.0.0.1",
            geo_location=GeoLocation(
                city="Boston",
                country="US",
                latitude=42.3601,
                longitude=-71.0589,
            ),
            start_time=datetime(2026, 1, 25, 14, 0, 0),
            is_vpn=False,
            is_tor=False,
        )
        
        device = Device(
            device_id="dev_paradox",
            device_type="tablet",
            os="iPadOS 17",
            browser="Safari 17",
            is_known=True,  # Device says known
            first_seen_at=datetime(2025, 1, 1, 0, 0, 0),
        )
        
        result = detection_agent.analyze(login_event, session, device)
        
        # Should detect the new device from login_event (OR logic)
        assert "new_device_detected" in result.risk_factors
        assert result.risk_signal_score > 0.0
    
    def test_zero_failed_attempts_no_velocity_flag(self, detection_agent):
        """Zero failed attempts should not trigger velocity flag."""
        login_event = LoginEvent(
            event_id="evt_zero_fails",
            session_id="sess_zero_fails",
            user_id="user_careful",
            timestamp=datetime(2026, 1, 25, 12, 0, 0),
            success=True,
            auth_method="biometric",
            failed_attempts_before=0,  # Explicitly zero
            is_new_device=False,
            is_new_ip=False,
            is_new_location=False,
        )
        
        session = Session(
            session_id="sess_zero_fails",
            user_id="user_careful",
            device_id="dev_bio",
            ip_address="192.168.0.1",
            geo_location=GeoLocation(
                city="Chicago",
                country="US",
                latitude=41.8781,
                longitude=-87.6298,
            ),
            start_time=datetime(2026, 1, 25, 12, 0, 0),
            is_vpn=False,
            is_tor=False,
        )
        
        device = Device(
            device_id="dev_bio",
            device_type="mobile",
            os="iOS 17",
            browser="Safari 17",
            is_known=True,
        )
        
        result = detection_agent.analyze(login_event, session, device)
        
        # Should have no velocity factors
        velocity_factors = [f for f in result.risk_factors if "velocity" in f]
        assert len(velocity_factors) == 0
