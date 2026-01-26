"""Decision Context - The Immutable Spine of the System.

This module defines the core data structures that flow through the decision lifecycle.
All context is immutable once created. No agent can modify the spine.

Design principles:
- Frozen dataclasses for immutability
- Clear separation between input, agent outputs, and final decision
- Audit-ready structure from inception
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Optional
from uuid import uuid4

from src.aegis_ai.data.schemas.login_event import LoginEvent
from src.aegis_ai.data.schemas.session import Session
from src.aegis_ai.data.schemas.device import Device
from src.aegis_ai.data.schemas.user import User
from src.aegis_ai.agents.detection.schema import DetectionOutput
from src.aegis_ai.agents.behavior.schema import BehavioralOutput
from src.aegis_ai.agents.network.schema import NetworkOutput
from src.aegis_ai.agents.confidence.schema import ConfidenceOutput
from src.aegis_ai.agents.explanation.schema import ExplanationOutput


@dataclass(frozen=True)
class InputContext:
    """Validated input data for decision pipeline.
    
    All input must be validated Pydantic models.
    This is the starting point of every decision.
    """
    login_event: LoginEvent
    session: Session
    device: Device
    user: User
    
    def __post_init__(self):
        """Validate that all inputs are proper Pydantic models."""
        assert isinstance(self.login_event, LoginEvent), "login_event must be LoginEvent"
        assert isinstance(self.session, Session), "session must be Session"
        assert isinstance(self.device, Device), "device must be Device"
        assert isinstance(self.user, User), "user must be User"


@dataclass(frozen=True)
class AgentOutputs:
    """Collected outputs from all agents.
    
    Each agent runs independently. This structure collects their outputs.
    Agents cannot see each other's outputs during execution.
    """
    detection: DetectionOutput
    behavioral: BehavioralOutput
    network: NetworkOutput
    confidence: ConfidenceOutput
    explanation: ExplanationOutput


@dataclass(frozen=True)
class FinalDecision:
    """The final decision record.
    
    Immutable. Audit-ready. This is what gets logged.
    """
    decision_id: str
    timestamp: datetime
    action: Literal["ALLOW", "BLOCK", "CHALLENGE", "ESCALATE"]
    decided_by: Literal["AI", "HUMAN_REQUIRED"]
    confidence_score: float
    explanation: str
    
    # Traceability
    session_id: str
    user_id: str
    
    # Agent evidence summary
    detection_score: float
    behavioral_score: float
    network_score: float
    disagreement_score: float
    
    @classmethod
    def create(
        cls,
        action: Literal["ALLOW", "BLOCK", "CHALLENGE", "ESCALATE"],
        decided_by: Literal["AI", "HUMAN_REQUIRED"],
        confidence_score: float,
        explanation: str,
        session_id: str,
        user_id: str,
        agent_outputs: AgentOutputs
    ) -> "FinalDecision":
        """Factory method to create a FinalDecision with proper ID and timestamp."""
        return cls(
            decision_id=f"dec_{uuid4().hex[:12]}",
            timestamp=datetime.utcnow(),
            action=action,
            decided_by=decided_by,
            confidence_score=confidence_score,
            explanation=explanation,
            session_id=session_id,
            user_id=user_id,
            detection_score=agent_outputs.detection.risk_signal_score,
            behavioral_score=agent_outputs.behavioral.behavioral_match_score,
            network_score=agent_outputs.network.network_risk_score,
            disagreement_score=agent_outputs.confidence.disagreement_score
        )


@dataclass(frozen=True)
class EscalationCase:
    """Structured escalation for human review.
    
    When AI cannot decide, this is what the human sees.
    Facts only. No recommendations. No persuasion.
    """
    case_id: str
    timestamp: datetime
    session_id: str
    user_id: str
    
    # Why escalated
    reason: Literal["LOW_CONFIDENCE", "HIGH_DISAGREEMENT", "POLICY_OVERRIDE"]
    confidence_score: float
    disagreement_score: float
    
    # Facts for human review (no interpretation)
    detection_factors: tuple[str, ...]
    behavioral_deviations: tuple[str, ...]
    network_evidence: tuple[str, ...]
    
    @classmethod
    def create(
        cls,
        session_id: str,
        user_id: str,
        reason: Literal["LOW_CONFIDENCE", "HIGH_DISAGREEMENT", "POLICY_OVERRIDE"],
        agent_outputs: AgentOutputs
    ) -> "EscalationCase":
        """Factory method to create an EscalationCase from agent outputs."""
        return cls(
            case_id=f"esc_{uuid4().hex[:12]}",
            timestamp=datetime.utcnow(),
            session_id=session_id,
            user_id=user_id,
            reason=reason,
            confidence_score=agent_outputs.confidence.final_confidence,
            disagreement_score=agent_outputs.confidence.disagreement_score,
            detection_factors=tuple(agent_outputs.detection.risk_factors),
            behavioral_deviations=tuple(agent_outputs.behavioral.deviation_summary),
            network_evidence=tuple(agent_outputs.network.evidence_links)
        )


@dataclass(frozen=True)
class DecisionContext:
    """The complete decision record - the spine of the system.
    
    This is the immutable case file that flows through the pipeline.
    Once created, nothing can modify it.
    
    Lifecycle:
    1. Created with input context
    2. Enriched with agent outputs
    3. Finalized with decision or escalation
    """
    context_id: str
    created_at: datetime
    input_context: InputContext
    agent_outputs: Optional[AgentOutputs] = None
    final_decision: Optional[FinalDecision] = None
    escalation_case: Optional[EscalationCase] = None
    
    @classmethod
    def create(cls, input_context: InputContext) -> "DecisionContext":
        """Factory method to create a new DecisionContext."""
        return cls(
            context_id=f"ctx_{uuid4().hex[:12]}",
            created_at=datetime.utcnow(),
            input_context=input_context
        )
    
    def with_agent_outputs(self, agent_outputs: AgentOutputs) -> "DecisionContext":
        """Return new context with agent outputs added."""
        return DecisionContext(
            context_id=self.context_id,
            created_at=self.created_at,
            input_context=self.input_context,
            agent_outputs=agent_outputs,
            final_decision=self.final_decision,
            escalation_case=self.escalation_case
        )
    
    def with_decision(self, decision: FinalDecision) -> "DecisionContext":
        """Return new context with final decision added."""
        return DecisionContext(
            context_id=self.context_id,
            created_at=self.created_at,
            input_context=self.input_context,
            agent_outputs=self.agent_outputs,
            final_decision=decision,
            escalation_case=self.escalation_case
        )
    
    def with_escalation(self, escalation: EscalationCase) -> "DecisionContext":
        """Return new context with escalation case added."""
        return DecisionContext(
            context_id=self.context_id,
            created_at=self.created_at,
            input_context=self.input_context,
            agent_outputs=self.agent_outputs,
            final_decision=self.final_decision,
            escalation_case=escalation
        )
