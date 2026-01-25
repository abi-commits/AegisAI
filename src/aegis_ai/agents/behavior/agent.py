"""Behavior Agent - compares current behavior with historical patterns."""

from dataclasses import dataclass


@dataclass
class BehaviorOutput:
    """Output from Behavior Agent."""
    behavioral_match_score: float  # 0.0 to 1.0
    

class BehaviorAgent:
    """Behavior Agent Contract.
    
    Input: session behavior vectors
    Output: behavioral_match_score
    Constraint: No network data, isolated
    """
    
    def __init__(self, model=None):
        self.model = model
    
    def analyze(self, session_behavior: dict) -> BehaviorOutput:
        """Analyze session behavior."""
        raise NotImplementedError
