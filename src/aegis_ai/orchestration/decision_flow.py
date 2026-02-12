"""Decision Flow - The only place where decisions are made."""

import logging
from typing import Optional
from datetime import datetime, timezone
from uuid import uuid4

from aegis_ai.orchestration.decision_context import (
    InputContext, DecisionContext, AgentOutputs, FinalDecision, EscalationCase
)
from aegis_ai.orchestration.agent_router import AgentRouter, RouterResult, AgentError

logger = logging.getLogger(__name__)


class DecisionFlow:
    """Orchestrates the complete decision lifecycle."""
    
    HIGH_RISK_THRESHOLD = 0.70
    MEDIUM_RISK_THRESHOLD = 0.40
    
    def __init__(self, router: Optional[AgentRouter] = None):
        self.router = router or AgentRouter()
    
    def process(self, input_context: InputContext) -> DecisionContext:
        """Process a login event through the full decision pipeline."""
        context = DecisionContext.create(input_context)
        router_result = self.router.route(input_context)
        
        if not router_result.success or router_result.outputs is None:
            logger.warning(f"Agent routing failed: {[e.agent_name for e in (router_result.errors or [])]}")
            return self._handle_agent_failure(context, input_context, router_result.errors or [])
        
        agent_outputs = router_result.outputs
        context = context.with_agent_outputs(agent_outputs)
        
        if agent_outputs.confidence.decision_permission == "HUMAN_REQUIRED":
            escalation = self._create_escalation(input_context, agent_outputs)
            context = context.with_escalation(escalation)
            decision = FinalDecision.create(
                action="ESCALATE", decided_by="HUMAN_REQUIRED",
                confidence_score=agent_outputs.confidence.final_confidence,
                explanation=f"Escalated: {escalation.reason}. {agent_outputs.explanation.explanation_text}",
                session_id=input_context.session.session_id,
                user_id=input_context.user.user_id,
                agent_outputs=agent_outputs
            )
            context = context.with_decision(decision)
        else:
            decision = self._make_decision(input_context, agent_outputs)
            context = context.with_decision(decision)
        
        return context
    
    def _handle_agent_failure(
        self, context: DecisionContext, input_context: InputContext,
        errors: list[AgentError],
    ) -> DecisionContext:
        """Handle agent failures by creating an escalation."""
        error_summary = "; ".join(f"{e.agent_name}: {e.error_type}" for e in errors) if errors else "Unknown"
        
        escalation = EscalationCase(
            case_id=f"esc_{uuid4().hex[:12]}", timestamp=datetime.now(timezone.utc),
            session_id=input_context.session.session_id, user_id=input_context.user.user_id,
            reason="LOW_CONFIDENCE", confidence_score=0.0, disagreement_score=1.0,
            detection_factors=("Agent processing failed",), behavioral_deviations=(),
            network_evidence=(),
        )
        context = context.with_escalation(escalation)
        
        decision = FinalDecision(
            decision_id=f"dec_{uuid4().hex[:12]}", timestamp=datetime.now(timezone.utc),
            action="ESCALATE", decided_by="HUMAN_REQUIRED", confidence_score=0.0,
            explanation=f"System escalation due to error: {error_summary}. Human review required.",
            session_id=input_context.session.session_id, user_id=input_context.user.user_id,
            detection_score=0.0, behavioral_score=0.0, network_score=0.0,
            disagreement_score=1.0,
        )
        context = context.with_decision(decision)
        return context
    
    def _make_decision(self, input_context: InputContext, agent_outputs: AgentOutputs) -> FinalDecision:
        """Make final decision based on agent outputs."""
        recommended = str(agent_outputs.explanation.recommended_action or "CHALLENGE").upper()
        
        action = "BLOCK" if recommended == "BLOCK" else \
                 "CHALLENGE" if recommended == "CHALLENGE" else \
                 "ALLOW" if recommended == "ALLOW" else "CHALLENGE"
        
        explanation = agent_outputs.explanation.explanation_text or f"Decision: {action}"
        
        return FinalDecision.create(
            action=action, decided_by="AI",
            confidence_score=agent_outputs.confidence.final_confidence,
            explanation=explanation,
            session_id=input_context.session.session_id,
            user_id=input_context.user.user_id,
            agent_outputs=agent_outputs
        )
    
    def _create_escalation(self, input_context: InputContext, agent_outputs: AgentOutputs) -> EscalationCase:
        """Create an escalation case for human review."""
        reason = "HIGH_DISAGREEMENT" if agent_outputs.confidence.disagreement_score > 0.30 else "LOW_CONFIDENCE"
        return EscalationCase.create(
            session_id=input_context.session.session_id,
            user_id=input_context.user.user_id,
            reason=reason,
            agent_outputs=agent_outputs
        )

