"""Device schema - canonical definition."""

from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field


class Device(BaseModel):
    """Device entity schema.
    
    Represents a device used for login attempts.
    device_id is a hash (not raw fingerprint).
    """
    device_id: str = Field(..., description="Hashed device fingerprint")
    device_type: Literal["desktop", "mobile", "tablet"] = Field(..., description="Device category")
    os: str = Field(..., description="Operating system (e.g., 'Windows 11', 'iOS 17')")
    browser: str = Field(..., description="Browser name and version")
    is_known: bool = Field(default=False, description="Whether device was seen before for this user")
    first_seen_at: Optional[datetime] = Field(default=None, description="First time device was observed")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "device_id": "dev_hash_xyz789",
                "device_type": "desktop",
                "os": "Windows 11",
                "browser": "Chrome 120",
                "is_known": True,
                "first_seen_at": "2025-06-15T10:30:00Z",
            }
        }
    }
