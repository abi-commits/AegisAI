"""Session schema - canonical definition."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class GeoLocation(BaseModel):
    """Geographic location."""
    city: str = Field(..., description="City name")
    country: str = Field(..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2 country code")
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class Session(BaseModel):
    """Session entity schema.
    
    Represents a user session with device and network context.
    """
    session_id: str = Field(..., description="Unique session identifier")
    user_id: str = Field(..., description="Associated user identifier")
    device_id: str = Field(..., description="Associated device identifier")
    ip_address: str = Field(..., description="Client IP address")
    geo_location: GeoLocation = Field(..., description="Resolved geographic location")
    start_time: datetime = Field(..., description="Session start timestamp")
    is_vpn: bool = Field(default=False, description="Whether VPN/proxy detected")
    is_tor: bool = Field(default=False, description="Whether Tor exit node detected")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "session_id": "sess_abc123",
                "user_id": "user_abc123",
                "device_id": "dev_hash_xyz789",
                "ip_address": "192.168.1.100",
                "geo_location": {
                    "city": "New York",
                    "country": "US",
                    "latitude": 40.7128,
                    "longitude": -74.0060,
                },
                "start_time": "2026-01-25T14:30:00Z",
                "is_vpn": False,
                "is_tor": False,
            }
        }
    }
