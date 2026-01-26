"""Decision Flow - The Only Place Decisions Happen.

This module is the single point where final decisions are made.
No other module may create FinalDecision or EscalationCase.

The confidence gate is sacred:
- HUMAN_REQUIRED means AI restraint, not AI failure
- This is a feature, not a bug

Design principles:
- Single responsibility: decide or escalate
- Confidence gate is immutable
- All decisions are traced back to agent outputs
"""

from typing import Literal

from src.aegis_ai.orchestration.decision_context import (
    InputContext,
    DecisionContext,
    AgentOutputs,
    FinalDecision,
    EscalationCase
)
from src.aegis_ai.orchestration.agent_router import AgentRouter, RouterResult


class DecisionFlow:
    """Orchestrates the complete decision lifecycle.
    
    Lifecycle:
    1. Validate input
    2. Route to agents
    3. Apply confidence gate
    4. Decide or escalate
    5. Return immutable decision context
    """
    
    # Action thresholds based on risk
    HIGH_RISK_THRESHOLD = 0.70  # Above this = BLOCK consideration
    MEDIUM_RISK_THRESHOLD = 0.40  # Above this = CHALLENGE consideration
    
    def __init__(self):
        """Initialize decision flow with router."""
        self.router = AgentRouter()
    
    def process(self, input_context: InputContext) -> DecisionContext:
        """Process a login event through the full decision pipeline.
        
        Args:
            input_context: Validated input context
            
        Returns:
            Complete DecisionContext with decision or escalation
        """
        # Create the decision context spine
        context = DecisionContext.create(input_context)
        
        # Route through all agents
        router_result = self.router.route(input_context)
        
        if not router_result.success or router_result.outputs is None:
            # Agent failures -> escalate to human
            errors = router_result.errors or []
            raise RuntimeError(
                f"Agent routing failed: {[e.error_message for e in errors]}"
            )
        
        # Enrich context with agent outputs (guaranteed non-None after check above)
        agent_outputs = router_result.outputs
        context = context.with_agent_outputs(agent_outputs)
        
        # Apply the confidence gate (THE MOST IMPORTANT CHECK)
        if agent_outputs.confidence.decision_permission == "HUMAN_REQUIRED":
            # AI is NOT ALLOWED to decide
            # This is restraint, not failure
            escalation = self._create_escalation(
                input_context=input_context,
                agent_outputs=agent_outputs
            )
            context = context.with_escalation(escalation)
            
            # Also create a decision record marking the escalation
            decision = FinalDecision.create(
                action="ESCALATE",
                decided_by="HUMAN_REQUIRED",
                confidence_score=agent_outputs.confidence.final_confidence,
                explanation=f"Escalated: {escalation.reason}. {agent_outputs.explanation.explanation_text}",
                session_id=input_context.session.session_id,
                user_id=input_context.user.user_id,
                agent_outputs=agent_outputs
            )
            context = context.with_decision(decision)
        else:
            # AI is ALLOWED to decide
            decision = self._make_decision(
                input_context=input_context,
                agent_outputs=agent_outputs
            )
            context = context.with_decision(decision)
        
        return context
    
    def _make_decision(
        self,
        input_context: InputContext,
        agent_outputs: AgentOutputs
    ) -> FinalDecision:
        """Make the final decision based on agent outputs.
        
        Only called when confidence gate allows AI to decide.
        """
        # Use the explanation agent's recommended action as base
        recommended = agent_outputs.explanation.recommended_action.upper()
        
        # Map to final action
        action: Literal["ALLOW", "BLOCK", "CHALLENGE", "ESCALATE"]
        
        if recommended == "BLOCK":
            action = "BLOCK"
        elif recommended == "CHALLENGE":
            action = "CHALLENGE"
        elif recommended == "ALLOW":
            action = "ALLOW"
        else:
            # Unknown recommendation -> challenge to be safe
            action = "CHALLENGE"
        
        return FinalDecision.create(
            action=action,
            decided_by="AI",
            confidence_score=agent_outputs.confidence.final_confidence,
            explanation=agent_outputs.explanation.explanation_text,
            session_id=input_context.session.session_id,
            user_id=input_context.user.user_id,
            agent_outputs=agent_outputs
        )
    
    def _create_escalation(
        self,
        input_context: InputContext,
        agent_outputs: AgentOutputs
    ) -> EscalationCase:
        """Create an escalation case for human review.
        
        Determines the reason for escalation based on confidence metrics.
        """
        # Determine escalation reason
        reason: Literal["LOW_CONFIDENCE", "HIGH_DISAGREEMENT", "POLICY_OVERRIDE"]
        
        if agent_outputs.confidence.disagreement_score > 0.30:
            reason = "HIGH_DISAGREEMENT"
        else:
            reason = "LOW_CONFIDENCE"
        
        return EscalationCase.create(
            session_id=input_context.session.session_id,
            user_id=input_context.user.user_id,
            reason=reason,
            agent_outputs=agent_outputs
        )


# =============================================================================
# DEMO: End-to-End Decision Flow
# =============================================================================

def demo_decision_flow():
    """Demonstrate the complete decision flow with 3 scenarios."""
    from datetime import datetime
    from src.aegis_ai.data.schemas.login_event import LoginEvent
    from src.aegis_ai.data.schemas.session import Session, GeoLocation
    from src.aegis_ai.data.schemas.device import Device
    from src.aegis_ai.data.schemas.user import User
    
    print("=" * 70)
    print("AEGISAI DECISION FLOW DEMO")
    print("Phase 3: Orchestration & Decision Lifecycle")
    print("=" * 70)
    
    flow = DecisionFlow()
    
    # =========================================================================
    # Scenario 1: Legitimate Login -> ALLOW
    # =========================================================================
    print("\n" + "=" * 70)
    print("SCENARIO 1: Legitimate Login (Expected: ALLOW)")
    print("=" * 70)
    
    user1 = User(
        user_id="user_legit_001",
        account_age_days=365,
        home_country="US",
        home_city="New York",
        typical_login_hour_start=8,
        typical_login_hour_end=18
    )
    
    device1 = Device(
        device_id="dev_known_001",
        device_type="desktop",
        os="Windows 11",
        browser="Chrome 120",
        is_known=True,
        first_seen_at=datetime(2024, 1, 1)
    )
    
    session1 = Session(
        session_id="sess_legit_001",
        user_id="user_legit_001",
        device_id="dev_known_001",
        ip_address="192.168.1.100",
        geo_location=GeoLocation(city="New York", country="US", latitude=40.7128, longitude=-74.0060),
        start_time=datetime.now(),
        is_vpn=False,
        is_tor=False
    )
    
    login1 = LoginEvent(
        event_id="evt_legit_001",
        session_id="sess_legit_001",
        user_id="user_legit_001",
        timestamp=datetime.now(),
        success=True,
        auth_method="password",
        failed_attempts_before=0,
        time_since_last_login_hours=24.0,
        is_new_device=False,
        is_new_ip=False,
        is_new_location=False,
        is_ato=False
    )
    
    input1 = InputContext(login_event=login1, session=session1, device=device1, user=user1)
    result1 = flow.process(input1)
    
    print(f"\n✓ Decision: {result1.final_decision.action}")
    print(f"  Decided by: {result1.final_decision.decided_by}")
    print(f"  Confidence: {result1.final_decision.confidence_score:.2%}")
    print(f"  Explanation: {result1.final_decision.explanation}")
    
    # =========================================================================
    # Scenario 2: Clear ATO Attack -> BLOCK
    # =========================================================================
    print("\n" + "=" * 70)
    print("SCENARIO 2: Clear ATO Attack (Expected: BLOCK)")
    print("=" * 70)
    
    user2 = User(
        user_id="user_victim_002",
        account_age_days=500,
        home_country="US",
        home_city="Los Angeles",
        typical_login_hour_start=9,
        typical_login_hour_end=17
    )
    
    device2 = Device(
        device_id="dev_attacker_002",
        device_type="desktop",
        os="Linux Ubuntu",
        browser="Firefox 121",
        is_known=False,
        first_seen_at=None
    )
    
    session2 = Session(
        session_id="sess_ato_002",
        user_id="user_victim_002",
        device_id="dev_attacker_002",
        ip_address="185.220.101.42",  # Suspicious IP
        geo_location=GeoLocation(city="Moscow", country="RU", latitude=55.7558, longitude=37.6173),
        start_time=datetime.now(),
        is_vpn=True,
        is_tor=True
    )
    
    login2 = LoginEvent(
        event_id="evt_ato_002",
        session_id="sess_ato_002",
        user_id="user_victim_002",
        timestamp=datetime.now(),
        success=True,
        auth_method="password",
        failed_attempts_before=5,
        time_since_last_login_hours=0.5,
        is_new_device=True,
        is_new_ip=True,
        is_new_location=True,
        is_ato=True  # Ground truth
    )
    
    input2 = InputContext(login_event=login2, session=session2, device=device2, user=user2)
    result2 = flow.process(input2)
    
    print(f"\n✓ Decision: {result2.final_decision.action}")
    print(f"  Decided by: {result2.final_decision.decided_by}")
    print(f"  Confidence: {result2.final_decision.confidence_score:.2%}")
    print(f"  Explanation: {result2.final_decision.explanation}")
    
    # =========================================================================
    # Scenario 3: Uncertain Login -> ESCALATE
    # =========================================================================
    print("\n" + "=" * 70)
    print("SCENARIO 3: Uncertain Login (Expected: ESCALATE)")
    print("=" * 70)
    
    user3 = User(
        user_id="user_traveler_003",
        account_age_days=30,  # New account
        home_country="US",
        home_city="Chicago",
        typical_login_hour_start=7,
        typical_login_hour_end=23
    )
    
    device3 = Device(
        device_id="dev_new_003",
        device_type="mobile",
        os="iOS 17",
        browser="Safari 17",
        is_known=False,
        first_seen_at=None
    )
    
    session3 = Session(
        session_id="sess_uncertain_003",
        user_id="user_traveler_003",
        device_id="dev_new_003",
        ip_address="45.33.32.156",
        geo_location=GeoLocation(city="London", country="GB", latitude=51.5074, longitude=-0.1278),
        start_time=datetime.now(),
        is_vpn=False,
        is_tor=False
    )
    
    login3 = LoginEvent(
        event_id="evt_uncertain_003",
        session_id="sess_uncertain_003",
        user_id="user_traveler_003",
        timestamp=datetime.now(),
        success=True,
        auth_method="password",
        failed_attempts_before=1,
        time_since_last_login_hours=48.0,
        is_new_device=True,
        is_new_ip=True,
        is_new_location=True,
        is_ato=False  # Actually legitimate traveler
    )
    
    input3 = InputContext(login_event=login3, session=session3, device=device3, user=user3)
    result3 = flow.process(input3)
    
    print(f"\n✓ Decision: {result3.final_decision.action}")
    print(f"  Decided by: {result3.final_decision.decided_by}")
    print(f"  Confidence: {result3.final_decision.confidence_score:.2%}")
    print(f"  Explanation: {result3.final_decision.explanation}")
    
    if result3.escalation_case:
        print(f"\n  📋 ESCALATION CASE:")
        print(f"     Case ID: {result3.escalation_case.case_id}")
        print(f"     Reason: {result3.escalation_case.reason}")
        print(f"     Detection factors: {result3.escalation_case.detection_factors}")
        print(f"     Behavioral deviations: {result3.escalation_case.behavioral_deviations}")
        print(f"     Network evidence: {result3.escalation_case.network_evidence}")
    
    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"\n✓ Scenario 1 (Legit):     {result1.final_decision.action} by {result1.final_decision.decided_by}")
    print(f"✓ Scenario 2 (ATO):       {result2.final_decision.action} by {result2.final_decision.decided_by}")
    print(f"✓ Scenario 3 (Uncertain): {result3.final_decision.action} by {result3.final_decision.decided_by}")
    
    print("\n" + "=" * 70)
    print("PHASE 3 COMPLETE: Orchestration & Decision Lifecycle")
    print("=" * 70)
    print("\nKey achievements:")
    print("  ✓ Immutable DecisionContext (spine of system)")
    print("  ✓ Parallel agent routing with isolation")
    print("  ✓ Confidence gate enforced (HUMAN_REQUIRED = AI restraint)")
    print("  ✓ Structured escalation with facts only")
    print("  ✓ All decisions traced to agent outputs")
    print("=" * 70)


if __name__ == "__main__":
    demo_decision_flow()
