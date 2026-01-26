"""Explanation Agent Output Schema."""

from typing import Optional
from pydantic import BaseModel, Field


class SHAPContribution(BaseModel):
    """Single SHAP feature contribution."""
    feature_name: str = Field(
        ...,
        description="Name of the contributing feature"
    )
    contribution: float = Field(
        ...,
        description="SHAP value (positive = increases risk, negative = decreases risk)"
    )
    human_readable: str = Field(
        ...,
        description="Human-readable description of this contribution"
    )


class BehavioralDeviation(BaseModel):
    """Single behavioral deviation from baseline.
    """
    deviation_type: str = Field(
        ...,
        description="Type of deviation (e.g., 'time_anomaly', 'device_change')"
    )
    description: str = Field(
        ...,
        description="Human-readable description of the deviation"
    )
    severity: str = Field(
        default="medium",
        description="Severity level: low, medium, high"
    )


class NetworkEvidence(BaseModel):
    """Network evidence item.
    
    Represents one piece of network-based evidence.
    """
    evidence_type: str = Field(
        ...,
        description="Type of evidence (e.g., 'shared_ip', 'shared_device')"
    )
    description: str = Field(
        ...,
        description="Human-readable description of the evidence"
    )
    count: int = Field(
        default=1,
        ge=1,
        description="Count of related entities (e.g., number of shared accounts)"
    )


class ExplanationOutput(BaseModel):
    """Output from Explanation Agent."""
    
    recommended_action: str = Field(
        ...,
        description="Recommended action based on agent outputs (allow, challenge, escalate, block)"
    )
    explanation_text: str = Field(
        ...,
        description="Human-readable explanation of the recommendation"
    )
    
    # Phase 4: Model-aware explanation components
    shap_contributions: list[SHAPContribution] = Field(
        default_factory=list,
        description="Top SHAP feature contributions from Detection Agent (max 5)"
    )
    behavioral_deviations: list[BehavioralDeviation] = Field(
        default_factory=list,
        description="Behavioral deviations from Behavior Agent"
    )
    network_evidence: list[NetworkEvidence] = Field(
        default_factory=list,
        description="Network evidence from Network Agent"
    )
    
    # Explanation metadata
    total_evidence_count: int = Field(
        default=0,
        ge=0,
        description="Total count of evidence items across all agents"
    )
    explanation_traceable: bool = Field(
        default=True,
        description="Whether all explanation components can be traced to signals"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "recommended_action": "escalate",
                "explanation_text": "This login is from a new device not previously associated with this account. This login originates from a new geographic location. Due to uncertainty in the analysis, additional verification is recommended.",
                "shap_contributions": [
                    {
                        "feature_name": "is_new_location",
                        "contribution": 0.35,
                        "human_readable": "Login from new geographic location increases risk"
                    },
                    {
                        "feature_name": "is_new_device",
                        "contribution": 0.25,
                        "human_readable": "First time device increases risk"
                    }
                ],
                "behavioral_deviations": [
                    {
                        "deviation_type": "time_anomaly",
                        "description": "Login at 3:00 AM, typical hours are 9 AM - 5 PM",
                        "severity": "medium"
                    }
                ],
                "network_evidence": [
                    {
                        "evidence_type": "shared_ip",
                        "description": "IP address shared with 3 other accounts",
                        "count": 3
                    }
                ],
                "total_evidence_count": 6,
                "explanation_traceable": True
            }
        }
    }
