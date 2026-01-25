"""Behavioral Consistency Agent Output Schema.

Pydantic model for structured behavioral agent output.
No ML dependencies. Pure data validation.
"""

from pydantic import BaseModel, Field


class BehavioralOutput(BaseModel):
    """Output from Behavioral Consistency Agent.
    
    Measures how well the current session matches historical baseline.
    Low score means different, not necessarily fraudulent.
    """
    
    behavioral_match_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Match score from 0 (very different) to 1 (identical to baseline)"
    )
    deviation_summary: list[str] = Field(
        default_factory=list,
        description="List of behavioral deviations from baseline"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "behavioral_match_score": 0.72,
                "deviation_summary": [
                    "login_time_outside_typical_window",
                    "different_browser_than_usual"
                ]
            }
        }
    }
