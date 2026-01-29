"""Explanation Agent - Translator, Not Thinker.

Phase 4 Upgrades:
- SHAP top features from Detection Agent
- Behavioral deviations from Behavior Agent
- Network evidence counts from Network Agent
"""

from typing import Any, Literal, Optional
from aegis_ai.agents.detection.schema import DetectionOutput
from aegis_ai.agents.behavior.schema import BehavioralOutput
from aegis_ai.agents.network.schema import NetworkOutput
from aegis_ai.agents.confidence.schema import ConfidenceOutput
from aegis_ai.agents.explanation.schema import (
    ExplanationOutput,
    SHAPContribution,
    BehavioralDeviation,
    NetworkEvidence,
)


class ExplanationAgent:
    """Explanation Agent - Translator, Not Thinker.
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
    
    # Feature to human-readable mappings for SHAP
    FEATURE_DESCRIPTIONS = {
        "is_new_device": "First-time device increases risk",
        "device_not_known": "Unknown device increases risk",
        "is_new_ip": "New IP address increases risk",
        "is_new_location": "Login from new geographic location increases risk",
        "is_vpn": "VPN usage increases risk",
        "is_tor": "Tor network usage significantly increases risk",
        "failed_attempts_before": "Failed login attempts before this session",
        "failed_attempts_capped": "High number of failed attempts detected",
        "time_since_last_login_hours": "Time since last login",
        "is_long_absence": "Extended absence from account increases risk",
        "auth_method_password": "Password authentication used",
        "auth_method_mfa": "Multi-factor authentication used",
        "auth_method_sso": "Single sign-on authentication used",
        "auth_method_biometric": "Biometric authentication used",
    }
    
    # Behavioral deviation types to descriptions
    BEHAVIORAL_DESCRIPTIONS = {
        "time": "Login time differs from typical pattern",
        "device": "Device usage differs from typical pattern",
        "browser": "Browser usage differs from typical pattern",
        "location": "Login location differs from typical pattern",
        "velocity": "Login frequency differs from typical pattern",
    }
    
    def __init__(
        self,
        shap_explanation: Optional[Any] = None
    ):
        """Initialize Explanation Agent."""
        self._shap_explanation = shap_explanation
    
    def generate(
        self,
        detection_output: DetectionOutput,
        behavioral_output: BehavioralOutput,
        network_output: NetworkOutput,
        confidence_output: ConfidenceOutput,
        shap_explanation: Optional[Any] = None
    ) -> ExplanationOutput:
        """Generate action and explanation from agent outputs."""
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
        
        # Phase 4: Extract model-aware components
        shap_contributions = self._extract_shap_contributions(
            detection_output,
            shap_explanation
        )
        
        behavioral_deviations = self._extract_behavioral_deviations(
            behavioral_output
        )
        
        network_evidence = self._extract_network_evidence(
            network_output
        )
        
        # Calculate total evidence count
        total_evidence = (
            len(shap_contributions) +
            len(behavioral_deviations) +
            len(network_evidence)
        )
        
        # Verify all explanation components are traceable
        explanation_traceable = self._verify_traceability(
            shap_contributions,
            behavioral_deviations,
            network_evidence
        )
        
        return ExplanationOutput(
            recommended_action=action,
            explanation_text=explanation,
            shap_contributions=shap_contributions,
            behavioral_deviations=behavioral_deviations,
            network_evidence=network_evidence,
            total_evidence_count=total_evidence,
            explanation_traceable=explanation_traceable
        )
    
    def _extract_shap_contributions(
        self,
        detection_output: DetectionOutput,
        shap_explanation: Optional[Any] = None
    ) -> list[SHAPContribution]:
        """Extract SHAP feature contributions from detection output."""
        contributions = []
        
        # If we have a SHAP explanation, use it
        if shap_explanation is not None:
            try:
                # Get top contributors from SHAP
                top_contributors = shap_explanation.get_top_contributors(
                    n=5,
                    min_contribution=0.02
                )
                
                for feature_name, shap_value in top_contributors:
                    # Only include if we have a known description
                    if feature_name in self.FEATURE_DESCRIPTIONS:
                        contributions.append(SHAPContribution(
                            feature_name=feature_name,
                            contribution=round(float(shap_value), 4),
                            human_readable=self.FEATURE_DESCRIPTIONS[feature_name]
                        ))
            except (AttributeError, TypeError):
                # SHAP explanation doesn't have expected interface
                pass
        
        # Fallback: derive from risk_factors if no SHAP
        if not contributions and detection_output.risk_factors:
            # Map risk factors to pseudo-SHAP contributions
            # Equal weight since we don't have actual SHAP values
            weight = min(0.2, 1.0 / max(1, len(detection_output.risk_factors)))
            
            for factor in detection_output.risk_factors[:5]:
                feature_name = self._factor_to_feature(factor)
                if feature_name and feature_name in self.FEATURE_DESCRIPTIONS:
                    contributions.append(SHAPContribution(
                        feature_name=feature_name,
                        contribution=round(weight, 4),
                        human_readable=self.FEATURE_DESCRIPTIONS[feature_name]
                    ))
        
        return contributions[:5]  # Max 5 contributions
    
    def _factor_to_feature(self, factor: str) -> Optional[str]:
        """Map a risk factor string to a feature name.
        
        Returns:
            Feature name or None if not mappable
        """
        factor_lower = factor.lower()
        
        if "new_device" in factor_lower:
            return "is_new_device"
        elif "new_ip" in factor_lower:
            return "is_new_ip"
        elif "new_country" in factor_lower or "new_location" in factor_lower:
            return "is_new_location"
        elif "velocity" in factor_lower or "failed_attempt" in factor_lower:
            return "failed_attempts_before"
        elif "vpn" in factor_lower or "proxy" in factor_lower:
            return "is_vpn"
        elif "tor" in factor_lower:
            return "is_tor"
        elif "absence" in factor_lower:
            return "is_long_absence"
        
        return None
    
    def _extract_behavioral_deviations(
        self,
        behavioral_output: BehavioralOutput
    ) -> list[BehavioralDeviation]:
        """Extract behavioral deviations from behavior agent output."""
        deviations = []
        
        for deviation_str in behavioral_output.deviation_summary:
            deviation_lower = deviation_str.lower()
            
            # Map to deviation type and determine severity
            deviation_type = None
            severity = "medium"
            description = deviation_str  # Use raw if no template
            
            if "time" in deviation_lower or "hour" in deviation_lower:
                deviation_type = "time_anomaly"
                description = self.BEHAVIORAL_DESCRIPTIONS.get("time", deviation_str)
                severity = "medium"
            elif "device" in deviation_lower:
                deviation_type = "device_change"
                description = self.BEHAVIORAL_DESCRIPTIONS.get("device", deviation_str)
                severity = "medium"
            elif "browser" in deviation_lower:
                deviation_type = "browser_change"
                description = self.BEHAVIORAL_DESCRIPTIONS.get("browser", deviation_str)
                severity = "low"
            elif "location" in deviation_lower or "country" in deviation_lower:
                deviation_type = "location_change"
                description = self.BEHAVIORAL_DESCRIPTIONS.get("location", deviation_str)
                severity = "high"
            elif "velocity" in deviation_lower or "frequency" in deviation_lower:
                deviation_type = "velocity_anomaly"
                description = self.BEHAVIORAL_DESCRIPTIONS.get("velocity", deviation_str)
                severity = "high"
            
            # Only add if we could determine a type (traceable)
            if deviation_type is not None:
                deviations.append(BehavioralDeviation(
                    deviation_type=deviation_type,
                    description=description,
                    severity=severity
                ))
        
        return deviations
    
    def _extract_network_evidence(
        self,
        network_output: NetworkOutput
    ) -> list[NetworkEvidence]:
        """Extract network evidence from network agent output."""
        evidence_list = []
        
        for evidence_str in network_output.evidence_links:
            evidence_lower = evidence_str.lower()
            
            # Parse evidence type and count
            evidence_type = None
            description = evidence_str
            count = 1
            
            # Try to extract count from evidence string
            import re
            count_match = re.search(r'(\d+)', evidence_str)
            if count_match:
                count = int(count_match.group(1))
            
            if "ip" in evidence_lower and "shared" in evidence_lower:
                evidence_type = "shared_ip"
                description = f"IP address shared with {count} other account(s)"
            elif "device" in evidence_lower and "shared" in evidence_lower:
                evidence_type = "shared_device"
                description = f"Device shared with {count} other user(s)"
            elif "proxy" in evidence_lower:
                evidence_type = "proxy_detected"
                description = "IP in known proxy range"
                count = 1
            elif "tor" in evidence_lower:
                evidence_type = "tor_detected"
                description = "Tor exit node detected"
                count = 1
            elif "vpn" in evidence_lower:
                evidence_type = "vpn_detected"
                description = "VPN service detected"
                count = 1
            
            # Only add if we could determine a type (traceable)
            if evidence_type is not None:
                evidence_list.append(NetworkEvidence(
                    evidence_type=evidence_type,
                    description=description,
                    count=count
                ))
        
        return evidence_list
    
    def _verify_traceability(
        self,
        shap_contributions: list[SHAPContribution],
        behavioral_deviations: list[BehavioralDeviation],
        network_evidence: list[NetworkEvidence]
    ) -> bool:
        """Verify all explanation components are traceable to signals."""
    
        # All SHAP contributions must map to known features
        for contrib in shap_contributions:
            if contrib.feature_name not in self.FEATURE_DESCRIPTIONS:
                return False
        
        # All behavioral deviations must have a type
        for deviation in behavioral_deviations:
            if not deviation.deviation_type:
                return False
        
        # All network evidence must have a type
        for evidence in network_evidence:
            if not evidence.evidence_type:
                return False
        
        return True
    
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
