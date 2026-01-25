"""Confidence Agent Output Schema.

Pydantic model for structured confidence agent output.
The Gatekeeper - decides whether AI may proceed or human review is required.
No ML dependencies. Pure data validation.
"""

from typing import Literal
from pydantic import BaseModel, Field


class ConfidenceOutput(BaseModel):
    """Output from Confidence Agent.
    
    Determines whether AI is allowed to make a decision.
    This is the most important agent - it gates automated decisions.
    """
    
    final_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Final confidence score from 0 (no confidence) to 1 (full confidence)"
    )
    decision_permission: Literal["AI_ALLOWED", "HUMAN_REQUIRED"] = Field(
        ...,
        description="Whether AI may proceed with decision or human review is required"
    )
    disagreement_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Measure of disagreement between agent scores (0=agreement, 1=conflict)"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "final_confidence": 0.85,
                "decision_permission": "AI_ALLOWED",
                "disagreement_score": 0.15
            }
        }
    }
