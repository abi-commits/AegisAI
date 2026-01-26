"""Orchestration - Agent routing and decision flow.

Phase 3: The Decision Lifecycle

Components:
- DecisionContext: Immutable spine of the system
- AgentRouter: Parallel, blind, fair agent invocation
- DecisionFlow: The only place decisions happen
"""

from src.aegis_ai.orchestration.decision_context import (
    InputContext,
    AgentOutputs,
    FinalDecision,
    EscalationCase,
    DecisionContext,
)
from src.aegis_ai.orchestration.agent_router import (
    AgentRouter,
    AgentError,
    RouterResult,
)
from src.aegis_ai.orchestration.decision_flow import DecisionFlow

__all__ = [
    # Decision Context (the spine)
    "InputContext",
    "AgentOutputs",
    "FinalDecision",
    "EscalationCase",
    "DecisionContext",
    # Agent Router
    "AgentRouter",
    "AgentError",
    "RouterResult",
    # Decision Flow
    "DecisionFlow",
]
