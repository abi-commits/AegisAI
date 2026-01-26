"""Graph Neural Network models for network-based risk scoring.

Uses GraphSAGE for inductive learning on user-device-IP graphs.
Graph signals are context, not verdicts.

Key design:
- Nodes: User, Device, IP
- Edges: user-device, device-ip, user-ip (derived)
- GraphSAGE for scalability and handling new nodes
"""

from src.aegis_ai.models.graph.schema import (
    NodeType,
    EdgeType,
    GraphNode,
    GraphEdge,
    FraudGraph,
)
from src.aegis_ai.models.graph.builder import GraphBuilder
from src.aegis_ai.models.graph.sage_model import (
    GraphSAGEModel,
    GraphSAGEConfig,
)

__all__ = [
    "NodeType",
    "EdgeType",
    "GraphNode",
    "GraphEdge",
    "FraudGraph",
    "GraphBuilder",
    "GraphSAGEModel",
    "GraphSAGEConfig",
]
