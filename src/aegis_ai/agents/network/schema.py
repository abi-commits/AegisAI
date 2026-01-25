"""Network & Evidence Agent Output Schema.

Pydantic model for structured network agent output.
No ML dependencies. Pure data validation.
"""

from pydantic import BaseModel, Field


class NetworkOutput(BaseModel):
    """Output from Network & Evidence Agent.
    
    Surfaces suspicion by association via shared infrastructure.
    This agent points to evidence but never concludes.
    """
    
    network_risk_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Network risk score from 0 (no network risk) to 1 (high network risk)"
    )
    evidence_links: list[str] = Field(
        default_factory=list,
        description="List of evidence links indicating network-based risk signals"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "network_risk_score": 0.45,
                "evidence_links": [
                    "ip_shared_with_3_other_accounts",
                    "device_seen_on_2_other_users",
                    "ip_in_known_proxy_range"
                ]
            }
        }
    }
