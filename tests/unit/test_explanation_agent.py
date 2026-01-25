"""Unit tests for Explanation Agent.

Testing discipline: Light but mandatory.
- One happy path test
- One edge case test  
- One weird but valid input test
"""

import pytest

from src.aegis_ai.agents.explanation.agent import ExplanationAgent
from src.aegis_ai.agents.explanation.schema import ExplanationOutput
from src.aegis_ai.agents.detection.schema import DetectionOutput
from src.aegis_ai.agents.behavior.schema import BehavioralOutput
from src.aegis_ai.agents.network.schema import NetworkOutput
from src.aegis_ai.agents.confidence.schema import ConfidenceOutput


@pytest.fixture
def explanation_agent():
    """Create an ExplanationAgent instance."""
    return ExplanationAgent()


@pytest.fixture
def low_risk_outputs():
    """Agent outputs indicating low risk."""
    return {
        "detection": DetectionOutput(
            risk_signal_score=0.1,
            risk_factors=[]
        ),
        "behavioral": BehavioralOutput(
            behavioral_match_score=0.9,
            deviation_summary=[]
        ),
        "network": NetworkOutput(
            network_risk_score=0.05,
            evidence_links=[]
        ),
        "confidence": ConfidenceOutput(
            final_confidence=0.9,
            decision_permission="AI_ALLOWED",
            disagreement_score=0.1
        ),
    }


@pytest.fixture
def high_risk_outputs():
    """Agent outputs indicating high risk."""
    return {
        "detection": DetectionOutput(
            risk_signal_score=0.85,
            risk_factors=[
                "new_device_detected",
                "login_from_new_country",
                "vpn_or_proxy_detected"
            ]
        ),
        "behavioral": BehavioralOutput(
            behavioral_match_score=0.2,
            deviation_summary=[
                "login_time_outside_typical_window",
                "different_location"
            ]
        ),
        "network": NetworkOutput(
            network_risk_score=0.7,
            evidence_links=[
                "ip_shared_with_5_other_accounts",
                "datacenter_ip"
            ]
        ),
        "confidence": ConfidenceOutput(
            final_confidence=0.85,
            decision_permission="AI_ALLOWED",
            disagreement_score=0.1
        ),
    }


class TestExplanationAgentHappyPath:
    """Happy path tests for ExplanationAgent."""
    
    def test_low_risk_recommends_allow(
        self,
        explanation_agent,
        low_risk_outputs
    ):
        """Low risk should recommend allow action."""
        result = explanation_agent.generate(
            low_risk_outputs["detection"],
            low_risk_outputs["behavioral"],
            low_risk_outputs["network"],
            low_risk_outputs["confidence"],
        )
        
        # Verify output type
        assert isinstance(result, ExplanationOutput)
        
        # Should recommend allow
        assert result.recommended_action == "allow"
        
        # Explanation should be non-empty
        assert len(result.explanation_text) > 0
    
    def test_output_validates_via_schema(
        self,
        explanation_agent,
        low_risk_outputs
    ):
        """Output should validate via Pydantic schema."""
        result = explanation_agent.generate(
            low_risk_outputs["detection"],
            low_risk_outputs["behavioral"],
            low_risk_outputs["network"],
            low_risk_outputs["confidence"],
        )
        
        # Convert to dict and back
        result_dict = result.model_dump()
        validated = ExplanationOutput(**result_dict)
        
        assert validated.recommended_action == result.recommended_action


class TestExplanationAgentEdgeCases:
    """Edge case tests for ExplanationAgent."""
    
    def test_high_risk_recommends_block(
        self,
        explanation_agent,
        high_risk_outputs
    ):
        """High risk should recommend block action."""
        result = explanation_agent.generate(
            high_risk_outputs["detection"],
            high_risk_outputs["behavioral"],
            high_risk_outputs["network"],
            high_risk_outputs["confidence"],
        )
        
        # Should recommend block for high risk
        assert result.recommended_action == "block"
        
        # Explanation should mention risk factors
        assert "device" in result.explanation_text.lower() or \
               "location" in result.explanation_text.lower()
    
    def test_human_required_always_escalates(self, explanation_agent):
        """When confidence says HUMAN_REQUIRED, should always escalate."""
        detection = DetectionOutput(
            risk_signal_score=0.3,  # Medium risk
            risk_factors=["new_device_detected"]
        )
        behavioral = BehavioralOutput(
            behavioral_match_score=0.7,
            deviation_summary=[]
        )
        network = NetworkOutput(
            network_risk_score=0.2,
            evidence_links=[]
        )
        # Key: HUMAN_REQUIRED
        confidence = ConfidenceOutput(
            final_confidence=0.5,
            decision_permission="HUMAN_REQUIRED",
            disagreement_score=0.4
        )
        
        result = explanation_agent.generate(
            detection,
            behavioral,
            network,
            confidence,
        )
        
        # Must escalate when human required
        assert result.recommended_action == "escalate"
        
        # Should mention uncertainty or human review
        assert "uncertainty" in result.explanation_text.lower() or \
               "verification" in result.explanation_text.lower() or \
               "review" in result.explanation_text.lower()
    
    def test_explanation_uses_deterministic_templates(
        self,
        explanation_agent,
        high_risk_outputs
    ):
        """Same inputs should produce same outputs (deterministic)."""
        result1 = explanation_agent.generate(
            high_risk_outputs["detection"],
            high_risk_outputs["behavioral"],
            high_risk_outputs["network"],
            high_risk_outputs["confidence"],
        )
        
        result2 = explanation_agent.generate(
            high_risk_outputs["detection"],
            high_risk_outputs["behavioral"],
            high_risk_outputs["network"],
            high_risk_outputs["confidence"],
        )
        
        # Should be identical - deterministic
        assert result1.recommended_action == result2.recommended_action
        assert result1.explanation_text == result2.explanation_text


class TestExplanationAgentWeirdButValid:
    """Weird but valid input tests."""
    
    def test_no_risk_factors_clean_explanation(self, explanation_agent):
        """No risk factors should produce clean, simple explanation."""
        clean_detection = DetectionOutput(
            risk_signal_score=0.0,
            risk_factors=[]
        )
        perfect_behavioral = BehavioralOutput(
            behavioral_match_score=1.0,
            deviation_summary=[]
        )
        clean_network = NetworkOutput(
            network_risk_score=0.0,
            evidence_links=[]
        )
        high_confidence = ConfidenceOutput(
            final_confidence=0.95,
            decision_permission="AI_ALLOWED",
            disagreement_score=0.0
        )
        
        result = explanation_agent.generate(
            clean_detection,
            perfect_behavioral,
            clean_network,
            high_confidence,
        )
        
        # Should allow
        assert result.recommended_action == "allow"
        
        # Should mention no risk factors
        assert "no risk" in result.explanation_text.lower() or \
               "proceed" in result.explanation_text.lower()
    
    def test_medium_risk_with_low_confidence_challenges(self, explanation_agent):
        """Medium risk with low confidence should challenge."""
        medium_detection = DetectionOutput(
            risk_signal_score=0.4,
            risk_factors=["new_device_detected"]
        )
        medium_behavioral = BehavioralOutput(
            behavioral_match_score=0.6,
            deviation_summary=["minor_deviation"]
        )
        low_network = NetworkOutput(
            network_risk_score=0.1,
            evidence_links=[]
        )
        # Low confidence triggers more caution
        low_confidence = ConfidenceOutput(
            final_confidence=0.6,
            decision_permission="AI_ALLOWED",
            disagreement_score=0.25
        )
        
        result = explanation_agent.generate(
            medium_detection,
            medium_behavioral,
            low_network,
            low_confidence,
        )
        
        # Should challenge or escalate due to low confidence
        assert result.recommended_action in ["challenge", "escalate"]
    
    def test_explanation_never_empty(self, explanation_agent, low_risk_outputs):
        """Explanation should never be empty string."""
        result = explanation_agent.generate(
            low_risk_outputs["detection"],
            low_risk_outputs["behavioral"],
            low_risk_outputs["network"],
            low_risk_outputs["confidence"],
        )
        
        assert result.explanation_text is not None
        assert len(result.explanation_text.strip()) > 0
