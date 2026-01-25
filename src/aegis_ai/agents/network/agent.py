"""Network Agent - surfaces relational risk via shared infrastructure."""

from dataclasses import dataclass
from typing import List


@dataclass
class NetworkOutput:
    """Output from Network Agent."""
    network_risk_score: float  # 0.0 to 1.0
    evidence_links: List[str]
    

class NetworkAgent:
    """Network Agent Contract.
    
    Input: user-device-IP graph slice
    Output: network_risk_score, evidence_links
    Constraint: Evidence only, no verdicts
    """
    
    def __init__(self, graph_model=None):
        self.graph_model = graph_model
    
    def analyze(self, graph_data: dict) -> NetworkOutput:
        """Analyze network graph for risk."""
        raise NotImplementedError
