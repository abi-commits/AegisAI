"""Confidence Agent Output Schema.
The Gatekeeper - decides whether AI may proceed or human review is required.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


class CalibrationInfo(BaseModel):
    """Calibration metadata from confidence calibrator.
    """
    raw_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Original confidence before calibration"
    )
    overconfidence_penalty: float = Field(
        default=0.0,
        ge=0.0,
        description="Penalty applied for overconfidence"
    )
    disagreement_penalty: float = Field(
        default=0.0,
        ge=0.0,
        description="Penalty applied for agent disagreement"
    )
    agreement_boost: float = Field(
        default=0.0,
        ge=0.0,
        description="Boost applied for strong agent agreement (increases confidence)"
    )
    evidence_penalty: float = Field(
        default=0.0,
        ge=0.0,
        description="Penalty applied for missing evidence"
    )
    escalation_boost: float = Field(
        default=0.0,
        ge=0.0,
        description="Boost applied to increase escalation likelihood"
    )


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
    calibration_info: Optional[CalibrationInfo] = Field(
        default=None,
        description="Calibration metadata showing adjustments made"
    )
    escalation_reason: Optional[str] = Field(
        default=None,
        description="Reason for requiring human review (if applicable)"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "final_confidence": 0.62,
                "decision_permission": "HUMAN_REQUIRED",
                "disagreement_score": 0.35,
                "calibration_info": {
                    "raw_confidence": 0.85,
                    "overconfidence_penalty": 0.08,
                    "disagreement_penalty": 0.12,
                    "evidence_penalty": 0.03,
                    "escalation_boost": 0.0
                },
                "escalation_reason": "HIGH_DISAGREEMENT"
            }
        }
    }
