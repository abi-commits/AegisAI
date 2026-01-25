"""Unit tests for Confidence Agent.

Testing discipline: Light but mandatory.
- One happy path test
- One edge case test  
- One weird but valid input test
"""

import pytest

from src.aegis_ai.agents.confidence.agent import ConfidenceAgent
from src.aegis_ai.agents.confidence.schema import ConfidenceOutput
from src.aegis_ai.agents.detection.schema import DetectionOutput
from src.aegis_ai.agents.behavior.schema import BehavioralOutput
from src.aegis_ai.agents.network.schema import NetworkOutput


@pytest.fixture
def confidence_agent():
    """Create a ConfidenceAgent instance."""
    return ConfidenceAgent()


@pytest.fixture
def agreeing_low_risk_outputs():
    """Agent outputs that all agree on low risk."""
    return {
        "detection": DetectionOutput(
            risk_signal_score=0.1,
            risk_factors=[]
        ),
        "behavioral": BehavioralOutput(
            behavioral_match_score=0.95,  # High match = low risk
            deviation_summary=[]
        ),
        "network": NetworkOutput(
            network_risk_score=0.05,
            evidence_links=[]
        ),
    }


@pytest.fixture
def agreeing_high_risk_outputs():
    """Agent outputs that all agree on high risk."""
    return {
        "detection": DetectionOutput(
            risk_signal_score=0.85,
            risk_factors=["new_device", "new_location", "vpn_detected"]
        ),
        "behavioral": BehavioralOutput(
            behavioral_match_score=0.15,  # Low match = high risk
            deviation_summary=["time_anomaly", "location_mismatch"]
        ),
        "network": NetworkOutput(
            network_risk_score=0.80,
            evidence_links=["ip_shared", "datacenter_ip"]
        ),
    }


class TestConfidenceAgentHappyPath:
    """Happy path tests for ConfidenceAgent."""
    
    def test_agreeing_low_risk_allows_ai(
        self,
        confidence_agent,
        agreeing_low_risk_outputs
    ):
        """When all agents agree on low risk, AI should be allowed."""
        result = confidence_agent.evaluate(
            agreeing_low_risk_outputs["detection"],
            agreeing_low_risk_outputs["behavioral"],
            agreeing_low_risk_outputs["network"],
        )
        
        # Verify output type
        assert isinstance(result, ConfidenceOutput)
        
        # AI should be allowed when agents agree
        assert result.decision_permission == "AI_ALLOWED"
        
        # High confidence expected
        assert result.final_confidence >= 0.7
        
        # Low disagreement expected
        assert result.disagreement_score < 0.3
    
    def test_output_validates_via_schema(
        self,
        confidence_agent,
        agreeing_low_risk_outputs
    ):
        """Output should validate via Pydantic schema."""
        result = confidence_agent.evaluate(
            agreeing_low_risk_outputs["detection"],
            agreeing_low_risk_outputs["behavioral"],
            agreeing_low_risk_outputs["network"],
        )
        
        # Convert to dict and back
        result_dict = result.model_dump()
        validated = ConfidenceOutput(**result_dict)
        
        assert validated.decision_permission == result.decision_permission


class TestConfidenceAgentEdgeCases:
    """Edge case tests for ConfidenceAgent."""
    
    def test_disagreeing_agents_require_human(self, confidence_agent):
        """When agents disagree significantly, human should be required."""
        # Detection says high risk, behavior says low risk, network neutral
        conflicting_detection = DetectionOutput(
            risk_signal_score=0.9,  # High risk
            risk_factors=["new_device", "new_location"]
        )
        conflicting_behavioral = BehavioralOutput(
            behavioral_match_score=0.95,  # High match = low risk
            deviation_summary=[]
        )
        conflicting_network = NetworkOutput(
            network_risk_score=0.1,  # Low risk
            evidence_links=[]
        )
        
        result = confidence_agent.evaluate(
            conflicting_detection,
            conflicting_behavioral,
            conflicting_network,
        )
        
        # High disagreement expected
        assert result.disagreement_score > 0.2
        
        # Human should be required due to disagreement
        assert result.decision_permission == "HUMAN_REQUIRED"
    
    def test_missing_evidence_penalizes_confidence(self, confidence_agent):
        """High risk with no evidence should reduce confidence."""
        no_evidence_detection = DetectionOutput(
            risk_signal_score=0.5,  # Elevated risk
            risk_factors=[]  # But no factors explaining why
        )
        normal_behavioral = BehavioralOutput(
            behavioral_match_score=0.5,
            deviation_summary=[]
        )
        no_evidence_network = NetworkOutput(
            network_risk_score=0.5,  # Elevated risk
            evidence_links=[]  # But no evidence
        )
        
        result = confidence_agent.evaluate(
            no_evidence_detection,
            normal_behavioral,
            no_evidence_network,
        )
        
        # Confidence should be penalized
        assert result.final_confidence < 0.7


class TestConfidenceAgentWeirdButValid:
    """Weird but valid input tests."""
    
    def test_perfect_agreement_on_extreme_risk(
        self,
        confidence_agent,
        agreeing_high_risk_outputs
    ):
        """Perfect agreement on high risk should allow AI to act."""
        result = confidence_agent.evaluate(
            agreeing_high_risk_outputs["detection"],
            agreeing_high_risk_outputs["behavioral"],
            agreeing_high_risk_outputs["network"],
        )
        
        # Even high risk with agreement should have high confidence
        # Low disagreement expected
        assert result.disagreement_score < 0.3
        
        # AI allowed because agents agree (even on high risk)
        assert result.decision_permission == "AI_ALLOWED"
    
    def test_all_zeros_is_valid_agreement(self, confidence_agent):
        """All zero risk scores should be valid and allow AI."""
        zero_detection = DetectionOutput(
            risk_signal_score=0.0,
            risk_factors=[]
        )
        perfect_behavioral = BehavioralOutput(
            behavioral_match_score=1.0,  # Perfect match
            deviation_summary=[]
        )
        zero_network = NetworkOutput(
            network_risk_score=0.0,
            evidence_links=[]
        )
        
        result = confidence_agent.evaluate(
            zero_detection,
            perfect_behavioral,
            zero_network,
        )
        
        # Perfect agreement, AI should be allowed
        assert result.decision_permission == "AI_ALLOWED"
        assert result.disagreement_score == 0.0
    
    def test_boundary_confidence_threshold(self, confidence_agent):
        """Test behavior at confidence threshold boundary."""
        # Create outputs that result in boundary confidence
        boundary_detection = DetectionOutput(
            risk_signal_score=0.3,
            risk_factors=["minor_factor"]
        )
        boundary_behavioral = BehavioralOutput(
            behavioral_match_score=0.7,
            deviation_summary=["minor_deviation"]
        )
        boundary_network = NetworkOutput(
            network_risk_score=0.25,
            evidence_links=["minor_evidence"]
        )
        
        result = confidence_agent.evaluate(
            boundary_detection,
            boundary_behavioral,
            boundary_network,
        )
        
        # Scores should still be in valid range
        assert 0.0 <= result.final_confidence <= 1.0
        assert 0.0 <= result.disagreement_score <= 1.0
        assert result.decision_permission in ["AI_ALLOWED", "HUMAN_REQUIRED"]
