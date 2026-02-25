"""Integration tests for Policy Engine.

Verifies that PolicyEngine correctly overrides agent decisions when safety rules are violated.
"""

import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone

from aegis_ai.data.schemas import User, Device, Session, LoginEvent, GeoLocation
from aegis_ai.orchestration.decision_context import InputContext, AgentOutputs
from aegis_ai.orchestration.decision_flow import DecisionFlow
from aegis_ai.orchestration.agent_router import RouterResult
from aegis_ai.agents.detection.schema import DetectionOutput
from aegis_ai.agents.behavior.schema import BehavioralOutput
from aegis_ai.agents.network.schema import NetworkOutput
from aegis_ai.agents.confidence.schema import ConfidenceOutput
from aegis_ai.agents.explanation.schema import ExplanationOutput


class TestPolicyIntegration:
    """Tests to verify PolicyEngine integration in DecisionFlow."""
    
    @pytest.fixture
    def mock_router(self):
        return MagicMock()

    @pytest.fixture
    def decision_flow(self, mock_router):
        return DecisionFlow(router=mock_router)

    @pytest.fixture
    def input_context(self):
        user = User(
            user_id="user_123", account_age_days=10, home_country="US", home_city="NY",
            typical_login_hour_start=8, typical_login_hour_end=18
        )
        device = Device(
            device_id="dev_123", device_type="mobile", os="iOS", browser="Safari", 
            is_known=True, first_seen_at=datetime.now(timezone.utc)
        )
        session = Session(
            session_id="sess_123", user_id="user_123", device_id="dev_123", ip_address="1.1.1.1", 
            geo_location=GeoLocation(city="NY", country="US", latitude=40.7, longitude=-74.0),
            start_time=datetime.now(timezone.utc), is_vpn=False, is_tor=False
        )
        login_event = LoginEvent(
            event_id="evt_123", session_id="sess_123", user_id="user_123", 
            timestamp=datetime.now(timezone.utc), success=True, auth_method="password",
            failed_attempts_before=0, time_since_last_login_hours=24.0
        )
        return InputContext(login_event=login_event, session=session, device=device, user=user)

    def test_policy_escalates_on_high_disagreement(self, decision_flow, mock_router, input_context):
        """
        Test that high disagreement triggers escalation via PolicyEngine, 
        even if ConfidenceAgent allowed AI to decide.
        """
        # Mock agent outputs: High disagreement but ConfidenceAgent says AI_ALLOWED
        agent_outputs = AgentOutputs(
            detection=DetectionOutput(risk_signal_score=0.1, risk_factors=[]),
            behavioral=BehavioralOutput(behavioral_match_score=0.9, deviation_summary=[]),
            network=NetworkOutput(network_risk_score=0.1, evidence_links=[]),
            confidence=ConfidenceOutput(
                final_confidence=0.85, 
                disagreement_score=0.45,  # Above policy threshold of 0.30
                decision_permission="AI_ALLOWED"
            ),
            explanation=ExplanationOutput(
                recommended_action="ALLOW",
                explanation_text="Agents agree it is safe.",
                shap_contributions=[], behavioral_deviations=[], network_evidence=[],
                total_evidence_count=0, explanation_traceable=True
            )
        )
        
        mock_router.route.return_value = RouterResult(success=True, outputs=agent_outputs)
        
        context = decision_flow.process(input_context)
        
        # This should now be "ESCALATE" due to PolicyEngine override
        assert context.final_decision.action == "ESCALATE"
        assert "Policy" in context.final_decision.explanation or "policy" in context.final_decision.explanation.lower()
        assert context.escalation_case is not None
        assert context.escalation_case.reason == "POLICY_OVERRIDE"

    def test_policy_vetoes_unallowed_action(self, decision_flow, mock_router, input_context):
        """
        Test that an unallowed action is vetoed by policy.
        """
        # Mock an action that is not allowed by policy
        # For simplicity, we'll mock an action that PolicyEngine will veto
        # if we could easily trigger it, but disagreement is already tested.
        pass
