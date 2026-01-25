"""Explanation Agent - Translator, Not Thinker.

Generates deterministic, template-based explanations.
No probabilistic language. No hallucinations.
Boring is correct.

This agent thinks. It does not act.
"""

from typing import Literal
from src.aegis_ai.agents.detection.schema import DetectionOutput
from src.aegis_ai.agents.behavior.schema import BehavioralOutput
from src.aegis_ai.agents.network.schema import NetworkOutput
from src.aegis_ai.agents.confidence.schema import ConfidenceOutput
from src.aegis_ai.agents.explanation.schema import ExplanationOutput


class ExplanationAgent:
    """Explanation Agent - Translator, Not Thinker.
    
    Responsibilities:
    - Translate agent outputs to human-readable text
    - Select appropriate action based on risk signals
    - Use deterministic templates
    
    Constraints:
    - No probabilistic language
    - No hallucinations
    - Pull phrases from agent outputs only
    - No side effects
    - No logging decisions
    - No raising actions
    """
    
    # Action thresholds based on aggregated risk
    HIGH_RISK_THRESHOLD = 0.70  # block
    MEDIUM_RISK_THRESHOLD = 0.45  # challenge
    ELEVATED_RISK_THRESHOLD = 0.25  # escalate
    
    # Template phrases for explanations
    TEMPLATES = {
        "new_device": "This login is from a new device not previously associated with this account.",
        "new_location": "This login originates from a new geographic location.",
        "new_ip": "This login is from a new IP address.",
        "behavioral_deviation": "This session deviates from the user's typical behavioral patterns.",
        "network_risk": "Network analysis indicates shared infrastructure with other accounts.",
        "time_anomaly": "This login occurred outside the user's typical hours.",
        "vpn_tor": "This connection uses anonymization technology.",
        "high_velocity": "Multiple login attempts were detected in a short period.",
        "low_confidence": "Due to uncertainty in the analysis, additional verification is recommended.",
        "agent_disagreement": "Analysis signals show conflicting indicators.",
    }
    
    # Action descriptions
    ACTION_TEMPLATES = {
        "allow": "No additional verification required. Login may proceed.",
        "challenge": "Additional verification is recommended before allowing access.",
        "escalate": "This case requires human review before proceeding.",
        "block": "Access should be temporarily blocked pending verification.",
    }
    
    def generate(
        self,
        detection_output: DetectionOutput,
        behavioral_output: BehavioralOutput,
        network_output: NetworkOutput,
        confidence_output: ConfidenceOutput
    ) -> ExplanationOutput:
        """Generate action and explanation from agent outputs.
        
        Args:
            detection_output: Output from DetectionAgent
            behavioral_output: Output from BehaviorAgent  
            network_output: Output from NetworkAgent
            confidence_output: Output from ConfidenceAgent
            
        Returns:
            ExplanationOutput with recommended_action and explanation_text
        """
        # Calculate aggregate risk for action determination
        aggregate_risk = self._calculate_aggregate_risk(
            detection_output,
            behavioral_output,
            network_output
        )
        
        # Determine action based on risk and confidence
        action = self._determine_action(
            aggregate_risk,
            confidence_output
        )
        
        # Build explanation text from templates
        explanation = self._build_explanation(
            detection_output,
            behavioral_output,
            network_output,
            confidence_output,
            action
        )
        
        return ExplanationOutput(
            recommended_action=action,
            explanation_text=explanation
        )
    
    def _calculate_aggregate_risk(
        self,
        detection: DetectionOutput,
        behavioral: BehavioralOutput,
        network: NetworkOutput
    ) -> float:
        """Calculate weighted aggregate risk score."""
        # Weight detection highest, then behavioral, then network
        weights = {
            "detection": 0.45,
            "behavioral": 0.30,
            "network": 0.25,
        }
        
        behavioral_risk = 1.0 - behavioral.behavioral_match_score
        
        aggregate = (
            weights["detection"] * detection.risk_signal_score +
            weights["behavioral"] * behavioral_risk +
            weights["network"] * network.network_risk_score
        )
        
        return max(0.0, min(1.0, aggregate))
    
    def _determine_action(
        self,
        aggregate_risk: float,
        confidence: ConfidenceOutput
    ) -> str:
        """Determine recommended action based on risk and confidence."""
        # If human required, always escalate
        if confidence.decision_permission == "HUMAN_REQUIRED":
            return "escalate"
        
        # Risk-based action selection
        if aggregate_risk >= self.HIGH_RISK_THRESHOLD:
            return "block"
        elif aggregate_risk >= self.MEDIUM_RISK_THRESHOLD:
            return "challenge"
        elif aggregate_risk >= self.ELEVATED_RISK_THRESHOLD:
            # Low confidence at elevated risk = challenge
            if confidence.final_confidence < 0.7:
                return "challenge"
            return "allow"
        else:
            return "allow"
    
    def _build_explanation(
        self,
        detection: DetectionOutput,
        behavioral: BehavioralOutput,
        network: NetworkOutput,
        confidence: ConfidenceOutput,
        action: str
    ) -> str:
        """Build deterministic explanation from templates."""
        parts: list[str] = []
        
        # Detection factors
        for factor in detection.risk_factors:
            if "new_device" in factor:
                parts.append(self.TEMPLATES["new_device"])
            elif "new_country" in factor or "new_location" in factor:
                parts.append(self.TEMPLATES["new_location"])
            elif "new_ip" in factor:
                parts.append(self.TEMPLATES["new_ip"])
            elif "velocity" in factor or "failed_attempts" in factor:
                parts.append(self.TEMPLATES["high_velocity"])
            elif "vpn" in factor or "tor" in factor:
                parts.append(self.TEMPLATES["vpn_tor"])
        
        # Behavioral deviations
        if behavioral.deviation_summary:
            if any("time" in d for d in behavioral.deviation_summary):
                parts.append(self.TEMPLATES["time_anomaly"])
            if len(behavioral.deviation_summary) > 1:
                parts.append(self.TEMPLATES["behavioral_deviation"])
        
        # Network evidence
        if network.evidence_links:
            parts.append(self.TEMPLATES["network_risk"])
        
        # Confidence concerns
        if confidence.decision_permission == "HUMAN_REQUIRED":
            parts.append(self.TEMPLATES["low_confidence"])
        if confidence.disagreement_score > 0.3:
            parts.append(self.TEMPLATES["agent_disagreement"])
        
        # Remove duplicates while preserving order
        seen = set()
        unique_parts = []
        for part in parts:
            if part not in seen:
                seen.add(part)
                unique_parts.append(part)
        
        # Add action template
        action_text = self.ACTION_TEMPLATES.get(action, "")
        
        # Combine into final explanation
        if unique_parts:
            explanation = " ".join(unique_parts) + " " + action_text
        else:
            explanation = "No risk factors identified. " + action_text
        
        return explanation.strip()
