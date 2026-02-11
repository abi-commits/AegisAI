"""Integration tests for AegisAI.

End-to-end tests that verify the full decision flow.
"""

import pytest
from datetime import datetime, timezone

from aegis_ai.data.schemas import User, Device, Session, LoginEvent, GeoLocation
from aegis_ai.orchestration.decision_context import InputContext
from aegis_ai.orchestration.decision_flow import DecisionFlow


class TestDecisionFlowIntegration:
    """Integration tests for the decision flow."""
    
    @pytest.fixture
    def decision_flow(self):
        """Create a decision flow instance."""
        return DecisionFlow()
    
    @pytest.fixture
    def normal_user(self):
        """Create a normal user."""
        return User(
            user_id="user_test_001",
            account_age_days=365,
            home_country="US",
            home_city="New York",
            typical_login_hour_start=8,
            typical_login_hour_end=18,
        )
    
    @pytest.fixture
    def known_device(self):
        """Create a known device."""
        return Device(
            device_id="device_test_001",
            device_type="desktop",
            os="Windows 11",
            browser="Chrome 120",
            is_known=True,
            first_seen_at=datetime.now(timezone.utc),
        )
    
    @pytest.fixture
    def normal_session(self, known_device):
        """Create a normal session."""
        return Session(
            session_id="session_test_001",
            user_id="user_test_001",
            start_time=datetime.now(timezone.utc),
            device_id=known_device.device_id,
            ip_address="192.168.1.1",
            geo_location=GeoLocation(
                city="New York",
                country="US",
                latitude=40.7128,
                longitude=-74.0060,
            ),
            is_vpn=False,
            is_tor=False,
        )
    
    @pytest.fixture
    def normal_login_event(self, normal_session, normal_user):
        """Create a normal login event."""
        return LoginEvent(
            event_id="event_test_001",
            session_id=normal_session.session_id,
            user_id=normal_user.user_id,
            timestamp=datetime.now(timezone.utc),
            success=True,
            auth_method="password",
            failed_attempts_before=0,
            time_since_last_login_hours=24.0,
        )
    
    @pytest.fixture
    def normal_input_context(self, normal_login_event, normal_session, known_device, normal_user):
        """Create a normal input context."""
        return InputContext(
            login_event=normal_login_event,
            session=normal_session,
            device=known_device,
            user=normal_user,
        )
    
    def test_normal_login_produces_decision(self, decision_flow, normal_input_context):
        """Test that a normal login produces a valid decision."""
        context = decision_flow.process(normal_input_context)
        
        # Should produce a decision context
        assert context is not None
        assert context.input_context == normal_input_context
        
        # Should have a decision
        assert context.decision is not None
        assert context.decision.action in ["ALLOW", "CHALLENGE", "BLOCK", "ESCALATE"]
    
    def test_decision_has_confidence_score(self, decision_flow, normal_input_context):
        """Test that decisions have confidence scores."""
        context = decision_flow.process(normal_input_context)
        
        assert context.decision is not None
        assert 0.0 <= context.decision.confidence_score <= 1.0
    
    def test_decision_has_explanation(self, decision_flow, normal_input_context):
        """Test that decisions have explanations."""
        context = decision_flow.process(normal_input_context)
        
        assert context.decision is not None
        assert context.decision.explanation is not None
        assert len(context.decision.explanation) > 0
    
    def test_agent_outputs_captured(self, decision_flow, normal_input_context):
        """Test that agent outputs are captured in the context."""
        context = decision_flow.process(normal_input_context)
        
        # Agent outputs should be captured
        assert context.agent_outputs is not None


class TestAPIIntegration:
    """Integration tests for the API layer."""
    
    @pytest.fixture
    def client(self):
        """Create a test client."""
        try:
            from fastapi.testclient import TestClient
            from aegis_ai.api.gateway import app
            return TestClient(app)
        except ImportError:
            pytest.skip("FastAPI test client not available")
    
    def test_health_endpoint(self, client):
        """Test the health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
    
    def test_evaluate_login_endpoint_exists(self, client):
        """Test that the evaluate-login endpoint exists."""
        # Just verify endpoint exists - may return 422 without body
        response = client.post("/evaluate-login", json={})
        # Should not return 404
        assert response.status_code != 404
