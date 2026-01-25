"""Data schemas using Pydantic."""

from datetime import datetime
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional


class User(BaseModel):
    """User schema."""
    user_id: str
    account_age_days: int
    home_country: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Device(BaseModel):
    """Device schema."""
    device_id: str  # hashed
    device_type: str
    os: str
    browser: str
    

class Session(BaseModel):
    """Session schema."""
    session_id: str
    user_id: str
    device_id: str
    ip_address: str
    geo_location: str
    start_time: datetime
    

class LoginEvent(BaseModel):
    """Login event schema."""
    event_id: str
    session_id: str
    timestamp: datetime
    success: bool
    additional_data: Optional[Dict[str, Any]] = None
