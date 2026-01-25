"""Confidence Agent - The Gatekeeper.

Determines whether AI is allowed to proceed with a decision.
Measures variance between agent scores, penalizes weak evidence.

This is the most important agent.
This agent thinks. It does not act.
"""

from typing import Literal
from src.aegis_ai.agents.detection.schema import DetectionOutput
from src.aegis_ai.agents.behavior.schema import BehavioralOutput
from src.aegis_ai.agents.network.schema import NetworkOutput
from src.aegis_ai.agents.confidence.schema import ConfidenceOutput


class ConfidenceAgent:
    """Confidence Agent - The Gatekeeper.
    
    Responsibilities:
    - Measure variance between agent scores
    - Penalize missing or weak evidence
    - Apply conservative thresholds
    - Decide whether AI may proceed
    
    Constraints:
    - Cannot label fraud
    - Cannot generate actions
    - No side effects
    - No logging decisions
    - No raising actions
    """
    
    # Thresholds for decision permission
    HIGH_CONFIDENCE_THRESHOLD = 0.75  # Above this = AI_ALLOWED
    LOW_DISAGREEMENT_THRESHOLD = 0.30  # Below this = agents agree
    
    # Penalties
    MISSING_EVIDENCE_PENALTY = 0.20
    HIGH_DISAGREEMENT_PENALTY = 0.25
    
    def evaluate(
        self,
        detection_output: DetectionOutput,
        behavioral_output: BehavioralOutput,
        network_output: NetworkOutput
    ) -> ConfidenceOutput:
        """Evaluate whether AI is allowed to decide.
        
        Args:
            detection_output: Output from DetectionAgent
            behavioral_output: Output from BehaviorAgent
            network_output: Output from NetworkAgent
            
        Returns:
            ConfidenceOutput with final_confidence, decision_permission, disagreement_score
        """
        # Collect scores from all agents
        scores = [
            detection_output.risk_signal_score,
            1.0 - behavioral_output.behavioral_match_score,  # Invert: low match = high risk
            network_output.network_risk_score
        ]
        
        # Calculate disagreement as variance-based metric
        disagreement_score = self._calculate_disagreement(scores)
        
        # Start with average confidence (inverse of average risk)
        avg_risk = sum(scores) / len(scores)
        
        # Base confidence: how certain we are about the situation
        # High risk with agreement = high confidence to act
        # Low risk with agreement = high confidence to allow
        # Either extreme with agreement = confident
        base_confidence = 1.0 - disagreement_score
        
        # Penalize missing evidence
        evidence_penalty = 0.0
        
        # Check for weak evidence in detection
        if len(detection_output.risk_factors) == 0 and detection_output.risk_signal_score > 0.3:
            # High risk but no factors = suspicious
            evidence_penalty += self.MISSING_EVIDENCE_PENALTY
        
        # Check for weak network evidence
        if len(network_output.evidence_links) == 0 and network_output.network_risk_score > 0.3:
            evidence_penalty += self.MISSING_EVIDENCE_PENALTY
        
        # Apply disagreement penalty if agents conflict
        if disagreement_score > self.LOW_DISAGREEMENT_THRESHOLD:
            evidence_penalty += self.HIGH_DISAGREEMENT_PENALTY * disagreement_score
        
        # Calculate final confidence
        final_confidence = max(0.0, min(1.0, base_confidence - evidence_penalty))
        
        # Determine decision permission
        decision_permission: Literal["AI_ALLOWED", "HUMAN_REQUIRED"]
        
        if final_confidence >= self.HIGH_CONFIDENCE_THRESHOLD:
            if disagreement_score < self.LOW_DISAGREEMENT_THRESHOLD:
                decision_permission = "AI_ALLOWED"
            else:
                # High confidence but high disagreement = need human
                decision_permission = "HUMAN_REQUIRED"
        else:
            # Low confidence = need human
            decision_permission = "HUMAN_REQUIRED"
        
        return ConfidenceOutput(
            final_confidence=final_confidence,
            decision_permission=decision_permission,
            disagreement_score=disagreement_score
        )
    
    def _calculate_disagreement(self, scores: list[float]) -> float:
        """Calculate disagreement score between agent outputs.
        
        Uses normalized standard deviation as disagreement metric.
        
        Args:
            scores: List of risk scores from agents (0-1 each)
            
        Returns:
            Disagreement score from 0 (perfect agreement) to 1 (maximum conflict)
        """
        if len(scores) < 2:
            return 0.0
        
        mean = sum(scores) / len(scores)
        variance = sum((s - mean) ** 2 for s in scores) / len(scores)
        std_dev = variance ** 0.5
        
        # Normalize to 0-1 range
        # Max possible std_dev for 0-1 values is 0.5 (all at 0 and 1)
        max_std_dev = 0.5
        normalized_disagreement = min(1.0, std_dev / max_std_dev)
        
        return normalized_disagreement
