"""Explanation templates for human-readable risk decisions."""

from dataclasses import dataclass
from typing import List, Dict, Any
from enum import Enum


class RiskFactor(str, Enum):
    """Common fraud risk factors."""
    NEW_DEVICE = "new_device"
    UNUSUAL_LOCATION = "unusual_location"
    HIGH_LOGIN_VELOCITY = "high_login_velocity"
    FAILED_ATTEMPTS = "failed_attempts"
    IMPOSSIBLE_TRAVEL = "impossible_travel"
    NEW_IP = "new_ip"
    BEHAVIOR_DEVIATION = "behavior_deviation"
    NETWORK_ANOMALY = "network_anomaly"
    TIME_ANOMALY = "time_anomaly"
    DEVICE_MISMATCH = "device_mismatch"


@dataclass
class ExplanationTemplate:
    """Template for human-readable explanations."""
    risk_factor: RiskFactor
    short_description: str
    explanation_template: str
    severity: str  # 'low', 'medium', 'high', 'critical'


# Library of explanation templates
EXPLANATION_TEMPLATES: Dict[RiskFactor, ExplanationTemplate] = {
    RiskFactor.NEW_DEVICE: ExplanationTemplate(
        risk_factor=RiskFactor.NEW_DEVICE,
        short_description="First login from this device",
        explanation_template="Login flagged: New device detected. First time this device has accessed the account.",
        severity="medium"
    ),
    RiskFactor.UNUSUAL_LOCATION: ExplanationTemplate(
        risk_factor=RiskFactor.UNUSUAL_LOCATION,
        short_description="Login from unusual geographic location",
        explanation_template="Login flagged: Unusual location '{location}'. This differs from typical login patterns.",
        severity="medium"
    ),
    RiskFactor.HIGH_LOGIN_VELOCITY: ExplanationTemplate(
        risk_factor=RiskFactor.HIGH_LOGIN_VELOCITY,
        short_description="High frequency of login attempts",
        explanation_template="Login flagged: High login velocity detected. {attempts} attempts in {timeframe}.",
        severity="high"
    ),
    RiskFactor.FAILED_ATTEMPTS: ExplanationTemplate(
        risk_factor=RiskFactor.FAILED_ATTEMPTS,
        short_description="Multiple failed login attempts",
        explanation_template="Login flagged: {failed_count} failed attempts before this login.",
        severity="high"
    ),
    RiskFactor.IMPOSSIBLE_TRAVEL: ExplanationTemplate(
        risk_factor=RiskFactor.IMPOSSIBLE_TRAVEL,
        short_description="Impossible travel between locations",
        explanation_template="Login flagged: Physically impossible travel. Previous login from '{prev_location}' {time_diff} ago.",
        severity="critical"
    ),
    RiskFactor.NEW_IP: ExplanationTemplate(
        risk_factor=RiskFactor.NEW_IP,
        short_description="First login from this IP address",
        explanation_template="Login flagged: New IP address detected. First login from this network.",
        severity="low"
    ),
    RiskFactor.BEHAVIOR_DEVIATION: ExplanationTemplate(
        risk_factor=RiskFactor.BEHAVIOR_DEVIATION,
        short_description="Deviation from user behavior",
        explanation_template="Login flagged: Behavior differs from historical patterns. Similarity score: {similarity}%.",
        severity="medium"
    ),
    RiskFactor.NETWORK_ANOMALY: ExplanationTemplate(
        risk_factor=RiskFactor.NETWORK_ANOMALY,
        short_description="Network graph anomaly detected",
        explanation_template="Login flagged: Device shared with {shared_count} other accounts.",
        severity="high"
    ),
    RiskFactor.TIME_ANOMALY: ExplanationTemplate(
        risk_factor=RiskFactor.TIME_ANOMALY,
        short_description="Login at unusual time",
        explanation_template="Login flagged: Unusual login time. User typically logs in at {typical_time}.",
        severity="low"
    ),
    RiskFactor.DEVICE_MISMATCH: ExplanationTemplate(
        risk_factor=RiskFactor.DEVICE_MISMATCH,
        short_description="Device characteristics mismatch",
        explanation_template="Login flagged: Device characteristics don't match profile (OS: {os}, Browser: {browser}).",
        severity="medium"
    ),
}


class ExplanationBuilder:
    """Build human-readable explanations from detected risk factors."""
    
    @staticmethod
    def build_explanation(
        risk_factors: List[RiskFactor],
        factor_details: Dict[RiskFactor, Dict[str, Any]] = None,
        confidence: float = None
    ) -> str:
        """
        Build a human-readable explanation from risk factors.
        
        Args:
            risk_factors: List of detected risk factors (in order of importance)
            factor_details: Dict mapping factor to detail parameters
            confidence: Model confidence score (0.0-1.0)
            
        Returns:
            Human-readable explanation string
        """
        if not risk_factors:
            return "No risk factors detected. Login appears normal."
        
        factor_details = factor_details or {}
        explanations = []
        
        # Build top factors explanation
        for factor in risk_factors[:3]:  # Top 3 factors
            if factor in EXPLANATION_TEMPLATES:
                template = EXPLANATION_TEMPLATES[factor]
                
                # Fill in template with details if available
                explanation_text = template.explanation_template
                if factor in factor_details:
                    try:
                        explanation_text = explanation_text.format(**factor_details[factor])
                    except KeyError:
                        pass  # Keep template as-is if params missing
                
                explanations.append(explanation_text)
        
        # Combine explanations
        if explanations:
            combined = " ".join(explanations)
            
            # Add confidence note if provided
            if confidence is not None:
                if confidence >= 0.8:
                    combined += f" (High confidence: {confidence:.0%})"
                elif confidence < 0.5:
                    combined += f" (Low confidence: {confidence:.0%} - Human review recommended)"
            
            return combined
        
        return "Unable to generate explanation."
    
    @staticmethod
    def build_summary(risk_factors: List[RiskFactor]) -> str:
        """Build a short summary of risk factors."""
        if not risk_factors:
            return "No risks detected"
        
        factor_names = []
        for factor in risk_factors[:3]:
            if factor in EXPLANATION_TEMPLATES:
                factor_names.append(EXPLANATION_TEMPLATES[factor].short_description)
        
        if not factor_names:
            return f"Multiple risk factors detected ({len(risk_factors)})"
        
        return "Due to: " + ", ".join(factor_names)
