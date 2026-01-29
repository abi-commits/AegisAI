"""Tests for the API Gateway.

These tests verify that:
1. The /evaluate-login endpoint works correctly
2. No internal agent outputs are exposed
3. Error handling works as expected
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from aegis_ai.api.gateway import app, get_service
from aegis_ai.api.schemas import EvaluateLoginRequest, EvaluateLoginResponse


@pytest.fixture
def client():
    """Create a test client for the API."""
    return TestClient(app)


@pytest.fixture
def valid_login_request() -> dict:
    """Create a valid login evaluation request."""
    return {
        "login_event": {
            "event_id": "evt_test_001",
            "timestamp": "2026-01-28T14:30:05Z",
            "success": True,
            "auth_method": "password",
            "failed_attempts_before": 0,
            "time_since_last_login_hours": 24.5,
            "is_new_device": False,
            "is_new_ip": False,
            "is_new_location": False,
        },
        "session": {
            "session_id": "sess_test_001",
            "device_id": "dev_test_001",
            "ip_address": "192.168.1.100",
            "geo_location": {
                "city": "New York",
                "country": "US",
                "latitude": 40.7128,
                "longitude": -74.0060,
            },
            "start_time": "2026-01-28T14:30:00Z",
            "is_vpn": False,
            "is_tor": False,
        },
        "device": {
            "device_id": "dev_test_001",
            "device_type": "desktop",
            "os": "Windows 11",
            "browser": "Chrome 120",
            "is_known": True,
            "first_seen_at": "2025-06-15T10:30:00Z",
        },
        "user": {
            "user_id": "user_test_001",
            "account_age_days": 365,
            "home_country": "US",
            "home_city": "New York",
            "typical_login_hour_start": 8,
            "typical_login_hour_end": 18,
        },
    }


class TestHealthEndpoint:
    """Tests for the /health endpoint."""
    
    def test_health_check_returns_healthy(self, client):
        """Health check should return healthy status."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "aegis-ai-gateway"


class TestEvaluateLoginEndpoint:
    """Tests for POST /evaluate-login."""
    
    def test_evaluate_login_returns_expected_fields(
        self, client, valid_login_request
    ):
        """Response should contain only the allowed fields."""
        response = client.post("/evaluate-login", json=valid_login_request)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields are present
        assert "decision" in data
        assert "confidence" in data
        assert "explanation" in data
        assert "escalation_flag" in data
        assert "audit_id" in data
        
        # Verify no internal agent outputs are exposed
        assert "detection" not in data
        assert "behavioral" not in data
        assert "network" not in data
        assert "agent_outputs" not in data
        assert "detection_score" not in data
        assert "behavioral_score" not in data
        assert "network_score" not in data
        assert "disagreement_score" not in data
    
    def test_evaluate_login_decision_is_valid(
        self, client, valid_login_request
    ):
        """Decision should be one of the valid actions."""
        response = client.post("/evaluate-login", json=valid_login_request)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["decision"] in ["ALLOW", "BLOCK", "CHALLENGE", "ESCALATE"]
    
    def test_evaluate_login_confidence_is_normalized(
        self, client, valid_login_request
    ):
        """Confidence should be between 0 and 1."""
        response = client.post("/evaluate-login", json=valid_login_request)
        
        assert response.status_code == 200
        data = response.json()
        
        assert 0.0 <= data["confidence"] <= 1.0
    
    def test_evaluate_login_has_explanation(
        self, client, valid_login_request
    ):
        """Response should have a non-empty explanation."""
        response = client.post("/evaluate-login", json=valid_login_request)
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data["explanation"], str)
        assert len(data["explanation"]) > 0
    
    def test_evaluate_login_escalation_flag_is_boolean(
        self, client, valid_login_request
    ):
        """Escalation flag should be a boolean."""
        response = client.post("/evaluate-login", json=valid_login_request)
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data["escalation_flag"], bool)
    
    def test_evaluate_login_audit_id_is_present(
        self, client, valid_login_request
    ):
        """Audit ID should be a non-empty string."""
        response = client.post("/evaluate-login", json=valid_login_request)
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data["audit_id"], str)
        assert data["audit_id"].startswith("aud_")
    
    def test_request_id_header_is_present(
        self, client, valid_login_request
    ):
        """Response should include X-Request-ID header."""
        response = client.post("/evaluate-login", json=valid_login_request)
        
        assert "X-Request-ID" in response.headers
        assert response.headers["X-Request-ID"].startswith("req_")


class TestInputValidation:
    """Tests for input validation."""
    
    def test_missing_login_event_returns_422(self, client, valid_login_request):
        """Missing login_event should return 422."""
        del valid_login_request["login_event"]
        
        response = client.post("/evaluate-login", json=valid_login_request)
        
        assert response.status_code == 422
    
    def test_missing_session_returns_422(self, client, valid_login_request):
        """Missing session should return 422."""
        del valid_login_request["session"]
        
        response = client.post("/evaluate-login", json=valid_login_request)
        
        assert response.status_code == 422
    
    def test_missing_device_returns_422(self, client, valid_login_request):
        """Missing device should return 422."""
        del valid_login_request["device"]
        
        response = client.post("/evaluate-login", json=valid_login_request)
        
        assert response.status_code == 422
    
    def test_missing_user_returns_422(self, client, valid_login_request):
        """Missing user should return 422."""
        del valid_login_request["user"]
        
        response = client.post("/evaluate-login", json=valid_login_request)
        
        assert response.status_code == 422
    
    def test_invalid_country_code_returns_422(self, client, valid_login_request):
        """Invalid country code should return 422."""
        valid_login_request["user"]["home_country"] = "INVALID"
        
        response = client.post("/evaluate-login", json=valid_login_request)
        
        assert response.status_code == 422
    
    def test_invalid_auth_method_returns_422(self, client, valid_login_request):
        """Invalid auth method should return 422."""
        valid_login_request["login_event"]["auth_method"] = "invalid"
        
        response = client.post("/evaluate-login", json=valid_login_request)
        
        assert response.status_code == 422


class TestNoAgentOutputsExposed:
    """Tests to ensure internal agent outputs are never exposed."""
    
    def test_response_schema_only_has_allowed_fields(self):
        """Verify EvaluateLoginResponse only has allowed fields."""
        allowed_fields = {"decision", "confidence", "explanation", 
                         "escalation_flag", "audit_id"}
        
        response_fields = set(EvaluateLoginResponse.model_fields.keys())
        
        assert response_fields == allowed_fields
    
    def test_no_agent_scores_in_response(self, client, valid_login_request):
        """Response should not contain individual agent scores."""
        response = client.post("/evaluate-login", json=valid_login_request)
        
        assert response.status_code == 200
        response_text = response.text.lower()
        
        # Ensure no internal agent identifiers are in the response
        assert "detection_score" not in response_text
        assert "behavioral_score" not in response_text
        assert "network_score" not in response_text
        assert "risk_signal_score" not in response_text
        assert "behavioral_match_score" not in response_text
        assert "network_risk_score" not in response_text
