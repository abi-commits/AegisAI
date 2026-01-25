"""Explanation Agent Output Schema.

Pydantic model for structured explanation agent output.
Translator, not thinker - uses deterministic templates.
No ML dependencies. Pure data validation.
"""

from pydantic import BaseModel, Field


class ExplanationOutput(BaseModel):
    """Output from Explanation Agent.
    
    Translates agent outputs into human-readable explanations.
    Uses deterministic templates - no probabilistic language, no hallucinations.
    Boring is correct.
    """
    
    recommended_action: str = Field(
        ...,
        description="Recommended action based on agent outputs (allow, challenge, escalate, block)"
    )
    explanation_text: str = Field(
        ...,
        description="Human-readable explanation of the recommendation"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "recommended_action": "challenge",
                "explanation_text": "This login deviates from the user's typical device and location. Due to uncertainty, additional verification is recommended."
            }
        }
    }
