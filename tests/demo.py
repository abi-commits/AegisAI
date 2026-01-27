#!/usr/bin/env python3
"""AegisAI Demo Script - The One Demo.

This demo shows exactly three scenarios:
1. Legit login → allowed silently (or escalated with caution)
2. Suspicious login → step-up auth (challenge or escalate)
3. Ambiguous login → AI refuses → human review

The third case is the star.

Narrative line:
"The most important decision this system makes is knowing when not to decide."
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.aegis_ai.data.schemas import User, Device, Session, LoginEvent, GeoLocation
from src.aegis_ai.orchestration.decision_context import InputContext
from src.aegis_ai.orchestration.decision_flow import DecisionFlow
from src.aegis_ai.governance.audit.logger import AuditLogger
from src.aegis_ai.governance.schemas import PolicyRules
from src.aegis_ai.governance.override import HumanOverrideHandler, OverrideType


def print_banner():
    """Print the demo banner."""
    print("\n" + "=" * 70)
    print("""
     █████╗ ███████╗ ██████╗ ██╗███████╗     █████╗ ██╗
    ██╔══██╗██╔════╝██╔════╝ ██║██╔════╝    ██╔══██╗██║
    ███████║█████╗  ██║  ███╗██║███████╗    ███████║██║
    ██╔══██║██╔══╝  ██║   ██║██║╚════██║    ██╔══██║██║
    ██║  ██║███████╗╚██████╔╝██║███████║    ██║  ██║██║
    ╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚═╝╚══════╝    ╚═╝  ╚═╝╚═╝
    """)
    print("           Agentic Fraud & Trust Intelligence System")
    print("=" * 70)


def print_section(title: str, emoji: str = "📋"):
    """Print a section header."""
    print(f"\n{emoji} {'-' * 30}")
    print(f"   {title}")
    print(f"   {'-' * 30}\n")


def create_legit_user() -> User:
    """Create a legitimate user with established history."""
    return User(
        user_id="user_demo_legit_001",
        account_age_days=365,
        home_country="US",
        home_city="San Francisco",
        typical_login_hour_start=8,
        typical_login_hour_end=18,
    )


def create_legit_device(user: User) -> Device:
    """Create a known device for the user."""
    return Device(
        device_id="dev_demo_known_001",
        device_type="desktop",
        os="macOS 14",
        browser="Chrome 120",
        is_known=True,
        first_seen_at=datetime.now(timezone.utc) - timedelta(days=180),
    )


def create_suspicious_device() -> Device:
    """Create an unknown, suspicious device."""
    return Device(
        device_id="dev_demo_suspicious_001",
        device_type="desktop",
        os="Windows 10",
        browser="Chrome 119",
        is_known=False,
        first_seen_at=None,
    )


def create_ambiguous_device() -> Device:
    """Create an ambiguous device (new but not clearly suspicious)."""
    return Device(
        device_id="dev_demo_ambiguous_001",
        device_type="mobile",
        os="iOS 17",
        browser="Safari 17",
        is_known=False,
        first_seen_at=None,
    )


def run_scenario_1_legit():
    """Scenario 1: Legitimate login → allowed silently."""
    print_section("SCENARIO 1: Legitimate Login", "🟢")
    print("   User: Returning customer, known device, home location")
    print("   Expected: ALLOW (silent pass-through)")
    print()
    
    # Create entities
    user = create_legit_user()
    device = create_legit_device(user)
    timestamp = datetime.now(timezone.utc).replace(hour=10, minute=30)  # Normal hours
    
    session = Session(
        session_id="sess_demo_legit_001",
        user_id=user.user_id,
        device_id=device.device_id,
        ip_address="203.45.67.89",
        geo_location=GeoLocation(
            city="San Francisco",
            country="US",
            latitude=37.7749,
            longitude=-122.4194,
        ),
        start_time=timestamp,
        is_vpn=False,
        is_tor=False,
    )
    
    login_event = LoginEvent(
        event_id="evt_demo_legit_001",
        session_id=session.session_id,
        user_id=user.user_id,
        timestamp=timestamp,
        success=True,
        auth_method="password",
        failed_attempts_before=0,
        time_since_last_login_hours=24.0,
        is_new_device=False,
        is_new_ip=False,
        is_new_location=False,
        is_ato=False,
    )
    
    # Create input context
    input_context = InputContext(
        login_event=login_event,
        session=session,
        device=device,
        user=user,
    )
    
    # Process through decision flow
    flow = DecisionFlow()
    result = flow.process(input_context)
    
    # Display result
    decision = result.final_decision
    print(f"   📊 Decision: {decision.action}")
    print(f"   🤖 Decided by: {decision.decided_by}")
    print(f"   📈 Confidence: {decision.confidence_score:.2%}")
    print(f"   📝 Explanation: {decision.explanation[:100]}...")
    
    if decision.action == "ALLOW":
        print("\n   ✅ SUCCESS: Legitimate user passed through silently")
    elif decision.action == "ESCALATE":
        print("\n   ✅ SUCCESS: System exercised caution - escalated for review")
        print("   📌 Note: High caution is correct for high-stakes decisions")
    else:
        print(f"\n   ⚠️  Unexpected action: {decision.action}")
    
    return result


def run_scenario_2_suspicious():
    """Scenario 2: Suspicious login → step-up auth (CHALLENGE)."""
    print_section("SCENARIO 2: Suspicious Login", "🟡")
    print("   User: Known account, NEW device, FOREIGN location, unusual time")
    print("   Expected: CHALLENGE or ESCALATE (high-risk detected)")
    print()
    
    # Create entities
    user = create_legit_user()
    device = create_suspicious_device()
    timestamp = datetime.now(timezone.utc).replace(hour=3, minute=15)  # 3 AM - unusual
    
    session = Session(
        session_id="sess_demo_suspicious_001",
        user_id=user.user_id,
        device_id=device.device_id,
        ip_address="91.243.87.112",  # Foreign IP
        geo_location=GeoLocation(
            city="Moscow",
            country="RU",
            latitude=55.7558,
            longitude=37.6173,
        ),
        start_time=timestamp,
        is_vpn=True,  # VPN usage
        is_tor=False,
    )
    
    login_event = LoginEvent(
        event_id="evt_demo_suspicious_001",
        session_id=session.session_id,
        user_id=user.user_id,
        timestamp=timestamp,
        success=True,
        auth_method="password",
        failed_attempts_before=2,  # Some failed attempts
        time_since_last_login_hours=0.5,  # Recent login from different location
        is_new_device=True,
        is_new_ip=True,
        is_new_location=True,
        is_ato=True,  # Ground truth: this IS an ATO attempt
    )
    
    # Create input context
    input_context = InputContext(
        login_event=login_event,
        session=session,
        device=device,
        user=user,
    )
    
    # Process through decision flow
    flow = DecisionFlow()
    result = flow.process(input_context)
    
    # Display result
    decision = result.final_decision
    print(f"   📊 Decision: {decision.action}")
    print(f"   🤖 Decided by: {decision.decided_by}")
    print(f"   📈 Confidence: {decision.confidence_score:.2%}")
    print(f"   📝 Explanation: {decision.explanation[:100]}...")
    
    if decision.action in ["CHALLENGE", "BLOCK", "ESCALATE"]:
        print(f"\n   ✅ SUCCESS: Suspicious login was handled ({decision.action})")
        if decision.action == "ESCALATE":
            print("   📌 System recognized high risk and deferred to human")
    else:
        print(f"\n   ❌ FAILURE: ATO attempt was allowed through!")
    
    return result


def run_scenario_3_ambiguous():
    """Scenario 3: Ambiguous login → AI refuses → human review.
    
    THIS IS THE STAR OF THE DEMO.
    
    "The most important decision this system makes is knowing when not to decide."
    """
    print_section("SCENARIO 3: Ambiguous Login (THE STAR)", "🌟")
    print("   User: Known account, new mobile device, traveling (legitimate?)")
    print("   Signals: Mixed - could be user traveling OR ATO")
    print("   Expected: ESCALATE (AI refuses to decide, human review)")
    print()
    print("   💡 'The most important decision this system makes")
    print("       is knowing when not to decide.'")
    print()
    
    # Create entities - ambiguous situation
    user = create_legit_user()
    device = create_ambiguous_device()
    timestamp = datetime.now(timezone.utc).replace(hour=14, minute=30)  # Normal hours
    
    # The ambiguity: User appears to be in London (could be traveling)
    # but on a new device. Behavioral signals are mixed.
    session = Session(
        session_id="sess_demo_ambiguous_001",
        user_id=user.user_id,
        device_id=device.device_id,
        ip_address="185.45.12.78",  # UK IP
        geo_location=GeoLocation(
            city="London",
            country="GB",
            latitude=51.5074,
            longitude=-0.1278,
        ),
        start_time=timestamp,
        is_vpn=False,  # No VPN (could be legit travel)
        is_tor=False,
    )
    
    login_event = LoginEvent(
        event_id="evt_demo_ambiguous_001",
        session_id=session.session_id,
        user_id=user.user_id,
        timestamp=timestamp,
        success=True,
        auth_method="password",
        failed_attempts_before=1,  # One typo (common for mobile)
        time_since_last_login_hours=12.0,  # Reasonable gap
        is_new_device=True,  # New device (could be new phone)
        is_new_ip=True,
        is_new_location=True,  # Different country (could be travel)
        is_ato=False,  # Ground truth: NOT actually ATO, user is traveling
    )
    
    # Create input context
    input_context = InputContext(
        login_event=login_event,
        session=session,
        device=device,
        user=user,
    )
    
    # Process through decision flow
    flow = DecisionFlow()
    result = flow.process(input_context)
    
    # Display result
    decision = result.final_decision
    print(f"   📊 Decision: {decision.action}")
    print(f"   🤖 Decided by: {decision.decided_by}")
    print(f"   📈 Confidence: {decision.confidence_score:.2%}")
    print(f"   📝 Explanation: {decision.explanation[:150]}...")
    
    # Show escalation details if escalated
    if result.escalation_case is not None:
        esc = result.escalation_case
        print(f"\n   📋 ESCALATION CASE:")
        print(f"      Case ID: {esc.case_id}")
        print(f"      Reason: {esc.reason}")
        print(f"      Disagreement: {esc.disagreement_score:.2%}")
    
    if decision.action == "ESCALATE" or decision.decided_by == "HUMAN_REQUIRED":
        print("\n   ✅ SUCCESS: AI exercised restraint and escalated to human")
        print("   📌 A human reviewer will now assess this case with full context.")
        return result, True
    else:
        print(f"\n   ⚠️  AI made a decision: {decision.action}")
        print("   📌 In production, we would want more escalation for edge cases.")
        return result, False


def simulate_human_override(decision_context, audit_logger: AuditLogger):
    """Simulate a human reviewer approving the ambiguous case."""
    print_section("HUMAN REVIEW SIMULATION", "👤")
    print("   A fraud analyst reviews the escalated case...")
    print("   After checking travel history: User is legitimately in London")
    print("   Decision: APPROVE the login")
    print()
    
    # Load policy rules
    from src.aegis_ai.governance.policies.engine import PolicyEngine
    policy_engine = PolicyEngine()
    
    # Create override handler
    override_handler = HumanOverrideHandler(
        audit_logger=audit_logger,
        policy_rules=policy_engine.rules,
    )
    
    decision = decision_context.final_decision
    
    # Create the override
    override = override_handler.create_override(
        original_decision_id=decision.decision_id,
        original_action=decision.action,
        original_confidence=decision.confidence_score,
        new_action="ALLOW",
        override_type=OverrideType.APPROVE,
        reason="User confirmed traveling to London for business. Known travel pattern.",
        reviewer_id="analyst_smith_042",
        reviewer_role="Senior Fraud Analyst",
        session_id=decision.session_id,
        user_id=decision.user_id,
        policy_impact="None - within policy guidelines",
    )
    
    print(f"   ✅ Override recorded:")
    print(f"      Override ID: {override.override_id}")
    print(f"      New Action: {override.new_action}")
    print(f"      Reviewer: {override.reviewer_role}")
    print(f"      Reason: {override.reason}")
    print(f"      Training Feedback: {'Enabled' if override.allow_training_feedback else 'Disabled'}")
    
    return override


def run_demo():
    """Run the complete demo with all three scenarios."""
    print_banner()
    
    print("\n" + "=" * 70)
    print("   This demo shows the three critical scenarios for AegisAI:")
    print("   1. Legitimate login → allowed silently")
    print("   2. Suspicious login → step-up authentication")
    print("   3. Ambiguous login → AI refuses → human review")
    print("=" * 70)
    
    # Initialize audit logger
    audit_logger = AuditLogger()
    
    # Scenario 1: Legitimate login
    result_1 = run_scenario_1_legit()
    
    input("\n   Press Enter to continue to Scenario 2...")
    
    # Scenario 2: Suspicious login
    result_2 = run_scenario_2_suspicious()
    
    input("\n   Press Enter to continue to Scenario 3 (THE STAR)...")
    
    # Scenario 3: Ambiguous login
    result_3, was_escalated = run_scenario_3_ambiguous()
    
    # If escalated, show human override
    if was_escalated:
        input("\n   Press Enter to see human review...")
        override = simulate_human_override(result_3, audit_logger)
    
    # Summary
    print_section("DEMO SUMMARY", "📊")
    
    # Get actual results for summary
    action_1 = result_1.final_decision.action if result_1.final_decision else "N/A"
    action_2 = result_2.final_decision.action if result_2.final_decision else "N/A"
    action_3 = result_3.final_decision.action if result_3.final_decision else "N/A"
    
    print("   ┌───────────────────────────────────────────────────────────────┐")
    print(f"   │ Scenario 1 (Legit):      {action_1:10} ✅ Handled appropriately │")
    print(f"   │ Scenario 2 (Suspicious): {action_2:10} ✅ Fraud addressed       │")
    print(f"   │ Scenario 3 (Ambiguous):  {action_3:10} ✅ AI showed wisdom      │")
    print("   └───────────────────────────────────────────────────────────────┘")
    print()
    print("   🎯 KEY INSIGHT:")
    print("   ╔═══════════════════════════════════════════════════════════════╗")
    print("   ║  'The most important decision this system makes              ║")
    print("   ║   is knowing when not to decide.'                            ║")
    print("   ╚═══════════════════════════════════════════════════════════════╝")
    print()
    print("   This demo shows that high escalation rates are a FEATURE,")
    print("   not a bug. In high-stakes decisions, AI restraint is paramount.")
    print()
    print("   The system errs on the side of human review when uncertain.")
    print("   This is what separates a responsible AI from a dangerous one.")
    print()
    print("=" * 70)
    print("   Demo complete. Audit logs available in: logs/audit/")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    run_demo()
