"""Core types and enums."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional


class DecisionAction(str, Enum):
    """Final decision actions."""
    ALLOW = "allow"
    CHALLENGE = "challenge"
    BLOCK_TEMPORARY = "block_temporary"
    ESCALATE = "escalate"


class RiskLevel(str, Enum):
    """Risk levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RiskSignal:
    """Individual risk signal from an agent."""
    source: str  # agent name
    score: float  # 0.0 to 1.0
    factors: List[str]
    

@dataclass
class AgentOutput:
    """Standardized agent output."""
    agent_name: str
    timestamp: datetime
    signal_score: float
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LoginEvent:
    """Login event with context."""
    event_id: str
    user_id: str
    session_id: str
    device_id: str
    ip_address: str
    geo_location: str
    timestamp: datetime
    success: bool
    additional_context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskDecision:
    """Final risk decision."""
    decision_id: str
    session_id: str
    final_action: DecisionAction
    confidence_score: float
    explanation_text: str
    human_review: bool
    audit_entry: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
