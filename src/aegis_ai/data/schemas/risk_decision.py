"""RiskDecision schema - canonical definition."""

from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field


class RiskDecision(BaseModel):
    """Risk decision entity schema.
    
    Represents the final decision for a login event.
    This is populated after agents process the event.
    """
    decision_id: str = Field(..., description="Unique decision identifier")
    event_id: str = Field(..., description="Associated login event")
    session_id: str = Field(..., description="Associated session")
    user_id: str = Field(..., description="Target user account")
    
    # Decision outcome
    final_action: Literal["allow", "challenge", "block_temporary", "escalate"] = Field(
        ..., description="Final action taken"
    )
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Model confidence (0-1)")
    risk_score: float = Field(..., ge=0.0, le=1.0, description="Aggregated risk score (0-1)")
    
    # Explainability
    risk_factors: List[str] = Field(default_factory=list, description="Detected risk factors")
    explanation_text: str = Field(..., description="Human-readable explanation")
    
    # Governance
    human_review_required: bool = Field(default=False, description="Whether human must review")
    human_override: Optional[str] = Field(default=None, description="Human override action if any")
    policy_version: str = Field(..., description="Policy version used for decision")
    model_version: str = Field(..., description="Model version used for scoring")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    reviewed_at: Optional[datetime] = Field(default=None, description="Human review timestamp")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "decision_id": "dec_abc123",
                "event_id": "evt_abc123",
                "session_id": "sess_abc123",
                "user_id": "user_abc123",
                "final_action": "challenge",
                "confidence_score": 0.72,
                "risk_score": 0.68,
                "risk_factors": ["new_device", "unusual_location"],
                "explanation_text": "Login flagged: New device from unusual location.",
                "human_review_required": False,
                "human_override": None,
                "policy_version": "1.0.0",
                "model_version": "xgboost_v2.1.0",
            }
        }
    }
