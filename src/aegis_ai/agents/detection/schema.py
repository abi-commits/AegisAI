"""Detection Agent Output Schema.

Pydantic model for structured detection agent output.
No ML dependencies. Pure data validation.
"""

from pydantic import BaseModel, Field


class DetectionOutput(BaseModel):
    """Output from Detection Agent.
    
    Contains risk signal score and identified risk factors.
    This agent identifies anomalies but does not make decisions.
    """
    
    risk_signal_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Risk signal score from 0 (no risk) to 1 (maximum risk)"
    )
    risk_factors: list[str] = Field(
        default_factory=list,
        description="List of identified risk factors contributing to the score"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "risk_signal_score": 0.65,
                "risk_factors": [
                    "new_device_detected",
                    "login_from_new_country",
                    "high_login_velocity"
                ]
            }
        }
    }
