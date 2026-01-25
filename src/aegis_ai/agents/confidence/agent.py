"""Confidence Agent - determines whether AI is allowed to decide."""

from dataclasses import dataclass
from enum import Enum


class DecisionPermission(str, Enum):
    """Decision permission enum."""
    ALLOW = "allow"
    DENY = "deny"


@dataclass
class ConfidenceOutput:
    """Output from Confidence Agent."""
    final_confidence: float  # 0.0 to 1.0
    decision_permission: DecisionPermission
    reasoning: str
    

class ConfidenceAgent:
    """Confidence Agent Contract.
    
    Input: all agent outputs (aggregated signals)
    Output: decision_permission, final_confidence
    Constraint: Cannot label fraud, cannot generate actions
    """
    
    def __init__(self, calibration_model=None):
        self.calibration_model = calibration_model
    
    def evaluate(self, agent_outputs: dict) -> ConfidenceOutput:
        """Evaluate if AI is allowed to decide."""
        raise NotImplementedError
