"""Graph schema definitions for fraud detection.

Defines node and edge types for the user-device-IP graph.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime

import numpy as np


class NodeType(str, Enum):
    """Types of nodes in the fraud graph."""
    USER = "user"
    DEVICE = "device"
    IP = "ip"


class EdgeType(str, Enum):
    """Types of edges in the fraud graph."""
    USER_DEVICE = "user_device"      # User logged in from device
    DEVICE_IP = "device_ip"          # Device connected from IP
    USER_IP = "user_ip"              # Derived: User connected from IP


@dataclass
class GraphNode:
    """A node in the fraud graph.
    
    Attributes:
        node_id: Unique identifier for the node
        node_type: Type of node (user, device, ip)
        features: Feature vector for the node
        metadata: Additional metadata (not used in model)
    """
    node_id: str
    node_type: NodeType
    features: np.ndarray = field(default_factory=lambda: np.zeros(8))
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not isinstance(self.features, np.ndarray):
            self.features = np.array(self.features, dtype=np.float32)


@dataclass
class GraphEdge:
    """An edge in the fraud graph.
    """
    source_id: str
    target_id: str
    edge_type: EdgeType
    weight: float = 1.0
    timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FraudGraph:
    """The fraud detection graph.
    """
    nodes: Dict[str, GraphNode] = field(default_factory=dict)
    edges: List[GraphEdge] = field(default_factory=list)
    
    # Index for fast edge lookup
    _edge_index: Dict[str, List[GraphEdge]] = field(default_factory=dict)
    
    def add_node(self, node: GraphNode) -> None:
        """Add a node to the graph."""
        self.nodes[node.node_id] = node
    
    def add_edge(self, edge: GraphEdge) -> None:
        """Add an edge to the graph."""
        self.edges.append(edge)
        
        # Update edge index
        if edge.source_id not in self._edge_index:
            self._edge_index[edge.source_id] = []
        self._edge_index[edge.source_id].append(edge)
        
        if edge.target_id not in self._edge_index:
            self._edge_index[edge.target_id] = []
        self._edge_index[edge.target_id].append(edge)
    
    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Get a node by ID."""
        return self.nodes.get(node_id)
    
    def get_neighbors(self, node_id: str) -> List[GraphNode]:
        """Get all neighbors of a node."""
        neighbors = []
        for edge in self._edge_index.get(node_id, []):
            neighbor_id = edge.target_id if edge.source_id == node_id else edge.source_id
            if neighbor_id in self.nodes:
                neighbors.append(self.nodes[neighbor_id])
        return neighbors
    
    def get_edges_for_node(self, node_id: str) -> List[GraphEdge]:
        """Get all edges connected to a node."""
        return self._edge_index.get(node_id, [])
    
    def get_k_hop_subgraph(
        self,
        center_node_id: str,
        k: int = 2,
        max_nodes: int = 100
    ) -> "FraudGraph":
        """Extract k-hop subgraph around a node.
        
        Args:
            center_node_id: Node to center subgraph on
            k: Number of hops
            max_nodes: Maximum nodes to include
            
        Returns:
            Subgraph containing k-hop neighborhood
        """
        visited = set()
        frontier = {center_node_id}
        
        for _ in range(k):
            new_frontier = set()
            for node_id in frontier:
                if node_id in visited:
                    continue
                visited.add(node_id)
                if len(visited) >= max_nodes:
                    break
                
                # Add neighbors to new frontier
                for edge in self._edge_index.get(node_id, []):
                    neighbor_id = (
                        edge.target_id if edge.source_id == node_id 
                        else edge.source_id
                    )
                    if neighbor_id not in visited:
                        new_frontier.add(neighbor_id)
            
            frontier = new_frontier
            if len(visited) >= max_nodes:
                break
        
        # Build subgraph
        subgraph = FraudGraph()
        
        for node_id in visited:
            if node_id in self.nodes:
                subgraph.add_node(self.nodes[node_id])
        
        for edge in self.edges:
            if edge.source_id in visited and edge.target_id in visited:
                subgraph.add_edge(edge)
        
        return subgraph
    
    def node_count(self) -> int:
        """Get number of nodes."""
        return len(self.nodes)
    
    def edge_count(self) -> int:
        """Get number of edges."""
        return len(self.edges)
    
    def get_nodes_by_type(self, node_type: NodeType) -> List[GraphNode]:
        """Get all nodes of a specific type."""
        return [n for n in self.nodes.values() if n.node_type == node_type]
