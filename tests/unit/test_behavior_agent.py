"""Unit tests for Behavior Agent.

Testing discipline: Light but mandatory.
- One happy path test
- One edge case test  
- One weird but valid input test
"""

import pytest
from datetime import datetime

from src.aegis_ai.agents.behavior.agent import BehaviorAgent
from src.aegis_ai.agents.behavior.schema import BehavioralOutput
from src.aegis_ai.data.schemas.login_event import LoginEvent
from src.aegis_ai.data.schemas.session import Session, GeoLocation
from src.aegis_ai.data.schemas.user import User


@pytest.fixture
def behavior_agent():
    """Create a BehaviorAgent instance."""
    return BehaviorAgent()


@pytest.fixture
def typical_user():
    """User with typical patterns in US, 9-5 login window."""
    return User(
        user_id="user_typical",
        account_age_days=365,
        home_country="US",
        home_city="New York",
        typical_login_hour_start=9,
        typical_login_hour_end=17,
    )


@pytest.fixture
def matching_login_event():
    """Login event that matches user baseline."""
    return LoginEvent(
        event_id="evt_match_001",
        session_id="sess_match_001",
        user_id="user_typical",
        timestamp=datetime(2026, 1, 25, 10, 30, 0),  # 10:30 AM - within window
        success=True,
        auth_method="password",
        is_new_device=False,
        is_new_ip=False,
        is_new_location=False,
    )


@pytest.fixture
def matching_session():
    """Session from user's home location during typical hours."""
    return Session(
        session_id="sess_match_001",
        user_id="user_typical",
        device_id="dev_001",
        ip_address="192.168.1.100",
        geo_location=GeoLocation(
            city="New York",
            country="US",
            latitude=40.7128,
            longitude=-74.0060,
        ),
        start_time=datetime(2026, 1, 25, 10, 30, 0),  # 10:30 AM
        is_vpn=False,
        is_tor=False,
    )


class TestBehaviorAgentHappyPath:
    """Happy path tests for BehaviorAgent."""
    
    def test_matching_behavior_returns_high_score(
        self,
        behavior_agent,
        matching_login_event,
        matching_session,
        typical_user
    ):
        """Login matching baseline should return high match score."""
        result = behavior_agent.analyze(
            matching_login_event,
            matching_session,
            typical_user
        )
        
        # Verify output type
        assert isinstance(result, BehavioralOutput)
        
        # High match score for matching behavior
        assert result.behavioral_match_score >= 0.9
        
        # No deviations
        assert len(result.deviation_summary) == 0
    
    def test_output_validates_via_schema(
        self,
        behavior_agent,
        matching_login_event,
        matching_session,
        typical_user
    ):
        """Output should validate via Pydantic schema."""
        result = behavior_agent.analyze(
            matching_login_event,
            matching_session,
            typical_user
        )
        
        # Convert to dict and back
        result_dict = result.model_dump()
        validated = BehavioralOutput(**result_dict)
        
        assert validated.behavioral_match_score == result.behavioral_match_score


class TestBehaviorAgentEdgeCases:
    """Edge case tests for BehaviorAgent."""
    
    def test_all_deviations_detected(self, behavior_agent, typical_user):
        """Multiple deviations should accumulate and reduce score."""
        # Login at 3 AM from different country with new device
        login_event = LoginEvent(
            event_id="evt_deviant",
            session_id="sess_deviant",
            user_id="user_typical",
            timestamp=datetime(2026, 1, 25, 3, 0, 0),  # 3 AM - outside window
            success=True,
            auth_method="sso",  # Different auth method
            is_new_device=True,  # New device
            is_new_ip=True,
            is_new_location=True,
        )
        
        session = Session(
            session_id="sess_deviant",
            user_id="user_typical",
            device_id="dev_new",
            ip_address="185.220.101.1",
            geo_location=GeoLocation(
                city="London",
                country="GB",  # Different country
                latitude=51.5074,
                longitude=-0.1278,
            ),
            start_time=datetime(2026, 1, 25, 3, 0, 0),
            is_vpn=False,
            is_tor=False,
        )
        
        historical_baseline = {
            "typical_auth_methods": ["password", "mfa"],
        }
        
        result = behavior_agent.analyze(
            login_event,
            session,
            typical_user,
            historical_baseline
        )
        
        # Low match score due to deviations
        assert result.behavioral_match_score < 0.5
        
        # Multiple deviations detected
        assert len(result.deviation_summary) >= 2
    
    def test_match_score_bounded_zero_to_one(self, behavior_agent, typical_user):
        """Match score should always be between 0 and 1."""
        # Create session with some deviations
        login_event = LoginEvent(
            event_id="evt_test",
            session_id="sess_test",
            user_id="user_typical",
            timestamp=datetime(2026, 1, 25, 22, 0, 0),
            success=True,
            auth_method="password",
            is_new_device=False,
            is_new_ip=False,
            is_new_location=False,
        )
        
        session = Session(
            session_id="sess_test",
            user_id="user_typical",
            device_id="dev_001",
            ip_address="192.168.1.1",
            geo_location=GeoLocation(
                city="Boston",  # Different city, same country
                country="US",
                latitude=42.3601,
                longitude=-71.0589,
            ),
            start_time=datetime(2026, 1, 25, 22, 0, 0),
            is_vpn=False,
            is_tor=False,
        )
        
        result = behavior_agent.analyze(login_event, session, typical_user)
        
        assert 0.0 <= result.behavioral_match_score <= 1.0


class TestBehaviorAgentWeirdButValid:
    """Weird but valid input tests."""
    
    def test_overnight_login_window(self, behavior_agent):
        """User with overnight login window (e.g., night shift worker)."""
        night_shift_user = User(
            user_id="user_night",
            account_age_days=100,
            home_country="US",
            home_city="Las Vegas",
            typical_login_hour_start=22,  # 10 PM
            typical_login_hour_end=6,  # 6 AM - overnight window
        )
        
        # Login at 2 AM should be within window
        login_event = LoginEvent(
            event_id="evt_night",
            session_id="sess_night",
            user_id="user_night",
            timestamp=datetime(2026, 1, 25, 2, 0, 0),  # 2 AM
            success=True,
            auth_method="password",
            is_new_device=False,
            is_new_ip=False,
            is_new_location=False,
        )
        
        session = Session(
            session_id="sess_night",
            user_id="user_night",
            device_id="dev_001",
            ip_address="10.0.0.1",
            geo_location=GeoLocation(
                city="Las Vegas",
                country="US",
                latitude=36.1699,
                longitude=-115.1398,
            ),
            start_time=datetime(2026, 1, 25, 2, 0, 0),
            is_vpn=False,
            is_tor=False,
        )
        
        result = behavior_agent.analyze(login_event, session, night_shift_user)
        
        # Should NOT flag time anomaly - 2 AM is within 22:00-06:00
        time_anomalies = [d for d in result.deviation_summary if "time" in d]
        assert len(time_anomalies) == 0
        
        # High match score expected
        assert result.behavioral_match_score >= 0.9
    
    def test_no_historical_baseline_provided(
        self,
        behavior_agent,
        matching_login_event,
        matching_session,
        typical_user
    ):
        """Agent should work without historical baseline."""
        # Explicitly pass None for baseline
        result = behavior_agent.analyze(
            matching_login_event,
            matching_session,
            typical_user,
            historical_baseline=None
        )
        
        # Should still return valid output
        assert isinstance(result, BehavioralOutput)
        assert 0.0 <= result.behavioral_match_score <= 1.0
