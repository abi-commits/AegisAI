"""LoginEvent schema - canonical definition."""

from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field


class LoginEvent(BaseModel):
    """Login event entity schema.
    
    Represents a single login attempt with outcome.
    """
    event_id: str = Field(..., description="Unique event identifier")
    session_id: str = Field(..., description="Associated session identifier")
    user_id: str = Field(..., description="Target user account")
    timestamp: datetime = Field(..., description="Event timestamp")
    success: bool = Field(..., description="Whether login succeeded")
    auth_method: Literal["password", "mfa", "sso", "biometric"] = Field(
        default="password", description="Authentication method used"
    )
    failed_attempts_before: int = Field(
        default=0, ge=0, description="Failed attempts in this session before this event"
    )
    time_since_last_login_hours: Optional[float] = Field(
        default=None, ge=0, description="Hours since user's last successful login"
    )
    is_new_device: bool = Field(default=False, description="First login from this device")
    is_new_ip: bool = Field(default=False, description="First login from this IP")
    is_new_location: bool = Field(default=False, description="First login from this geo location")
    
    # Ground truth label (for training/evaluation only)
    is_ato: bool = Field(default=False, description="Ground truth: is this an ATO attempt?")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "event_id": "evt_abc123",
                "session_id": "sess_abc123",
                "user_id": "user_abc123",
                "timestamp": "2026-01-25T14:30:05Z",
                "success": True,
                "auth_method": "password",
                "failed_attempts_before": 0,
                "time_since_last_login_hours": 24.5,
                "is_new_device": False,
                "is_new_ip": False,
                "is_new_location": False,
                "is_ato": False,
            }
        }
    }
