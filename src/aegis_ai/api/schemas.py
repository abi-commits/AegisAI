"""API Schemas - Request/Response models for the API Gateway.
"""

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


# =============================================================================
# REQUEST SCHEMAS
# =============================================================================

class GeoLocationRequest(BaseModel):
    """Geographic location in request."""
    city: str = Field(..., description="City name")
    country: str = Field(
        ..., min_length=2, max_length=2,
        description="ISO 3166-1 alpha-2 country code"
    )
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class LoginEventRequest(BaseModel):
    """Login event data in request."""
    event_id: str = Field(..., description="Unique event identifier")
    timestamp: datetime = Field(..., description="Event timestamp")
    success: bool = Field(..., description="Whether login succeeded")
    auth_method: Literal["password", "mfa", "sso", "biometric"] = Field(
        default="password", description="Authentication method used"
    )
    failed_attempts_before: int = Field(
        default=0, ge=0, description="Failed attempts before this event"
    )
    time_since_last_login_hours: Optional[float] = Field(
        default=None, ge=0, description="Hours since last successful login"
    )
    is_new_device: bool = Field(default=False)
    is_new_ip: bool = Field(default=False)
    is_new_location: bool = Field(default=False)


class SessionRequest(BaseModel):
    """Session context in request."""
    session_id: str = Field(..., description="Unique session identifier")
    device_id: str = Field(..., description="Hashed device identifier")
    ip_address: str = Field(..., description="Client IP address")
    geo_location: GeoLocationRequest = Field(..., description="Geographic location")
    start_time: datetime = Field(..., description="Session start timestamp")
    is_vpn: bool = Field(default=False, description="VPN/proxy detected")
    is_tor: bool = Field(default=False, description="Tor exit node detected")


class DeviceRequest(BaseModel):
    """Device information in request."""
    device_id: str = Field(..., description="Hashed device fingerprint")
    device_type: Literal["desktop", "mobile", "tablet"] = Field(...)
    os: str = Field(..., description="Operating system")
    browser: str = Field(..., description="Browser name and version")
    is_known: bool = Field(default=False, description="Device seen before")
    first_seen_at: Optional[datetime] = Field(default=None)


class UserRequest(BaseModel):
    """User account information in request."""
    user_id: str = Field(..., description="Unique user identifier")
    account_age_days: int = Field(..., ge=0)
    home_country: str = Field(..., min_length=2, max_length=2)
    home_city: str = Field(...)
    typical_login_hour_start: int = Field(..., ge=0, le=23)
    typical_login_hour_end: int = Field(..., ge=0, le=23)


class EvaluateLoginRequest(BaseModel):
    """Request body for POST /evaluate-login.
    
    Contains all context needed to evaluate a login attempt.
    """
    login_event: LoginEventRequest = Field(
        ..., description="The login event to evaluate"
    )
    session: SessionRequest = Field(
        ..., description="Session context"
    )
    device: DeviceRequest = Field(
        ..., description="Device information"
    )
    user: UserRequest = Field(
        ..., description="User account information"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "login_event": {
                    "event_id": "evt_abc123",
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
                    "session_id": "sess_abc123",
                    "device_id": "dev_xyz789",
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
                    "device_id": "dev_xyz789",
                    "device_type": "desktop",
                    "os": "Windows 11",
                    "browser": "Chrome 120",
                    "is_known": True,
                    "first_seen_at": "2025-06-15T10:30:00Z",
                },
                "user": {
                    "user_id": "user_abc123",
                    "account_age_days": 365,
                    "home_country": "US",
                    "home_city": "New York",
                    "typical_login_hour_start": 8,
                    "typical_login_hour_end": 18,
                },
            }
        }
    }


# =============================================================================
# RESPONSE SCHEMAS
# =============================================================================

class EvaluateLoginResponse(BaseModel):
    """Response for POST /evaluate-login.
    """
    decision: Literal["ALLOW", "BLOCK", "CHALLENGE", "ESCALATE"] = Field(
        ..., description="The final action decision"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0,
        description="Confidence score for the decision (0.0 to 1.0)"
    )
    explanation: str = Field(
        ..., description="Human-readable explanation for the decision"
    )
    escalation_flag: bool = Field(
        ..., description="True if decision requires human review"
    )
    audit_id: str = Field(
        ..., description="Audit trail identifier for this evaluation"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "decision": "ALLOW",
                "confidence": 0.92,
                "explanation": "Login from known device and location during typical hours. All signals indicate legitimate access.",
                "escalation_flag": False,
                "audit_id": "aud_a1b2c3d4e5f6",
            }
        }
    }


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Human-readable error message")
    request_id: Optional[str] = Field(
        default=None, description="Request ID for debugging"
    )
