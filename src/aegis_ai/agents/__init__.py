"""Agent modules for AegisAI."""

from aegis_ai.agents.detection.agent import DetectionAgent
from aegis_ai.agents.behavior.agent import BehaviorAgent
from aegis_ai.agents.network.agent import NetworkAgent
from aegis_ai.agents.confidence.agent import ConfidenceAgent
from aegis_ai.agents.explanation.agent import ExplanationAgent

__all__ = [
    "DetectionAgent",
    "BehaviorAgent",
    "NetworkAgent",
    "ConfidenceAgent",
    "ExplanationAgent",
]
