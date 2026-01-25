"""Agent modules for AegisAI."""

from src.aegis_ai.agents.detection.agent import DetectionAgent
from src.aegis_ai.agents.behavior.agent import BehaviorAgent
from src.aegis_ai.agents.network.agent import NetworkAgent
from src.aegis_ai.agents.confidence.agent import ConfidenceAgent
from src.aegis_ai.agents.explanation.agent import ExplanationAgent

__all__ = [
    "DetectionAgent",
    "BehaviorAgent",
    "NetworkAgent",
    "ConfidenceAgent",
    "ExplanationAgent",
]
