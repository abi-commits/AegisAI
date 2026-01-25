"""User schema - canonical definition."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class User(BaseModel):
    """User entity schema.
    
    Represents an account holder with baseline attributes.
    """
    user_id: str = Field(..., description="Unique user identifier")
    account_age_days: int = Field(..., ge=0, description="Days since account creation")
    home_country: str = Field(..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2 country code")
    home_city: str = Field(..., description="Primary city of residence")
    typical_login_hour_start: int = Field(..., ge=0, le=23, description="Typical login window start (0-23)")
    typical_login_hour_end: int = Field(..., ge=0, le=23, description="Typical login window end (0-23)")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "user_abc123",
                "account_age_days": 365,
                "home_country": "US",
                "home_city": "New York",
                "typical_login_hour_start": 8,
                "typical_login_hour_end": 18,
            }
        }
    }
