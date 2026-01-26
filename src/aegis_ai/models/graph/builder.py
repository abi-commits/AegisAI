"""Graph builder for constructing fraud detection graphs.

Builds and maintains the user-device-IP graph from login events.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List
import hashlib

import numpy as np

from src.aegis_ai.data.schemas.login_event import LoginEvent
from src.aegis_ai.data.schemas.session import Session
from src.aegis_ai.data.schemas.device import Device
from src.aegis_ai.data.schemas.user import User
from src.aegis_ai.models.graph.schema import (
    NodeType,
    EdgeType,
    GraphNode,
    GraphEdge,
    FraudGraph,
)


@dataclass
class NodeFeatureConfig:
    """Configuration for node feature extraction."""
    user_feature_dim: int = 8
    device_feature_dim: int = 8
    ip_feature_dim: int = 8


class GraphBuilder:
    """Build and maintain the fraud detection graph.
    
    Creates nodes and edges from login events, sessions, and devices.
    Maintains feature vectors for each node type.
    """
    
    def __init__(self, config: Optional[NodeFeatureConfig] = None):
        """Initialize graph builder.
        
        Args:
            config: Feature configuration
        """
        self.config = config or NodeFeatureConfig()
        self._graph = FraudGraph()
        
        # Statistics for normalization
        self._user_login_counts: Dict[str, int] = {}
        self._device_usage_counts: Dict[str, int] = {}
        self._ip_account_counts: Dict[str, set] = {}
    
    @property
    def graph(self) -> FraudGraph:
        """Get the current graph."""
        return self._graph
    
    def add_login_event(
        self,
        login_event: LoginEvent,
        session: Session,
        device: Device,
        user: Optional[User] = None
    ) -> None:
        """Add a login event to the graph."""
        user_id = login_event.user_id
        device_id = device.device_id
        ip_address = session.ip_address
        
        # Create/update user node
        self._add_or_update_user_node(user_id, login_event, user)
        
        # Create/update device node
        self._add_or_update_device_node(device_id, device)
        
        # Create/update IP node
        self._add_or_update_ip_node(ip_address, session, user_id)
        
        # Add edges
        self._add_edge_if_new(
            source_id=user_id,
            target_id=device_id,
            edge_type=EdgeType.USER_DEVICE,
            timestamp=session.start_time,
        )
        
        self._add_edge_if_new(
            source_id=device_id,
            target_id=ip_address,
            edge_type=EdgeType.DEVICE_IP,
            timestamp=session.start_time,
        )
        
        self._add_edge_if_new(
            source_id=user_id,
            target_id=ip_address,
            edge_type=EdgeType.USER_IP,
            timestamp=session.start_time,
        )
    
    def _add_or_update_user_node(
        self,
        user_id: str,
        login_event: LoginEvent,
        user: Optional[User]
    ) -> None:
        """Create or update a user node."""
        # Track login count
        self._user_login_counts[user_id] = self._user_login_counts.get(user_id, 0) + 1
        
        # Build features
        features = np.zeros(self.config.user_feature_dim, dtype=np.float32)
        
        # Feature 0: log of login count (normalized)
        features[0] = min(np.log1p(self._user_login_counts[user_id]) / 5.0, 1.0)
        
        # Feature 1: account age (if user provided)
        if user is not None:
            features[1] = min(user.account_age_days / 365.0, 1.0)
        
        # Feature 2: new device flag
        features[2] = 1.0 if login_event.is_new_device else 0.0
        
        # Feature 3: new IP flag
        features[3] = 1.0 if login_event.is_new_ip else 0.0
        
        # Feature 4: new location flag
        features[4] = 1.0 if login_event.is_new_location else 0.0
        
        # Feature 5: failed attempts (normalized)
        features[5] = min(login_event.failed_attempts_before / 5.0, 1.0)
        
        # Feature 6-7: reserved for future use
        
        node = GraphNode(
            node_id=user_id,
            node_type=NodeType.USER,
            features=features,
            metadata={"last_login": login_event.timestamp.isoformat()},
        )
        self._graph.add_node(node)
    
    def _add_or_update_device_node(
        self,
        device_id: str,
        device: Device
    ) -> None:
        """Create or update a device node."""
        # Track usage count
        self._device_usage_counts[device_id] = self._device_usage_counts.get(device_id, 0) + 1
        
        features = np.zeros(self.config.device_feature_dim, dtype=np.float32)
        
        # Feature 0: device type (one-hot-ish)
        device_types = {"desktop": 0.0, "mobile": 0.5, "tablet": 1.0}
        features[0] = device_types.get(device.device_type, 0.5)
        
        # Feature 1: is known device
        features[1] = 1.0 if device.is_known else 0.0
        
        # Feature 2: log of usage count
        features[2] = min(np.log1p(self._device_usage_counts[device_id]) / 5.0, 1.0)
        
        # Feature 3-7: reserved
        
        node = GraphNode(
            node_id=device_id,
            node_type=NodeType.DEVICE,
            features=features,
            metadata={
                "os": device.os,
                "browser": device.browser,
            },
        )
        self._graph.add_node(node)
    
    def _add_or_update_ip_node(
        self,
        ip_address: str,
        session: Session,
        user_id: str
    ) -> None:
        """Create or update an IP node."""
        # Track accounts using this IP
        if ip_address not in self._ip_account_counts:
            self._ip_account_counts[ip_address] = set()
        self._ip_account_counts[ip_address].add(user_id)
        
        features = np.zeros(self.config.ip_feature_dim, dtype=np.float32)
        
        # Feature 0: number of accounts sharing this IP (normalized)
        num_accounts = len(self._ip_account_counts[ip_address])
        features[0] = min(num_accounts / 10.0, 1.0)
        
        # Feature 1: is VPN
        features[1] = 1.0 if session.is_vpn else 0.0
        
        # Feature 2: is Tor
        features[2] = 1.0 if session.is_tor else 0.0
        
        # Feature 3: latitude (normalized)
        features[3] = session.geo_location.latitude / 90.0
        
        # Feature 4: longitude (normalized)
        features[4] = session.geo_location.longitude / 180.0
        
        # Feature 5-7: reserved
        
        node = GraphNode(
            node_id=ip_address,
            node_type=NodeType.IP,
            features=features,
            metadata={
                "country": session.geo_location.country,
                "city": session.geo_location.city,
                "account_count": num_accounts,
            },
        )
        self._graph.add_node(node)
    
    def _add_edge_if_new(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType,
        timestamp: datetime
    ) -> None:
        """Add an edge if it doesn't exist, otherwise update weight."""
        # Check if edge already exists
        for edge in self._graph.get_edges_for_node(source_id):
            if (edge.source_id == source_id and edge.target_id == target_id and
                edge.edge_type == edge_type):
                # Update weight (increment connection count)
                edge.weight += 1.0
                edge.timestamp = timestamp
                return
            if (edge.source_id == target_id and edge.target_id == source_id and
                edge.edge_type == edge_type):
                edge.weight += 1.0
                edge.timestamp = timestamp
                return
        
        # Add new edge
        self._graph.add_edge(GraphEdge(
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            weight=1.0,
            timestamp=timestamp,
        ))
    
    def get_local_subgraph(
        self,
        user_id: str,
        k_hops: int = 2,
        max_nodes: int = 50
    ) -> FraudGraph:
        """Get local subgraph around a user.
        
        Args:
            user_id: User to center on
            k_hops: Number of hops to include
            max_nodes: Maximum nodes
            
        Returns:
            Local subgraph
        """
        return self._graph.get_k_hop_subgraph(
            center_node_id=user_id,
            k=k_hops,
            max_nodes=max_nodes,
        )
    
    def get_ip_account_count(self, ip_address: str) -> int:
        """Get number of accounts using an IP."""
        return len(self._ip_account_counts.get(ip_address, set()))
    
    def get_device_account_count(self, device_id: str) -> int:
        """Get number of accounts using a device."""
        # Count unique users connected to this device
        users = set()
        for edge in self._graph.get_edges_for_node(device_id):
            if edge.edge_type == EdgeType.USER_DEVICE:
                if edge.source_id.startswith("user"):
                    users.add(edge.source_id)
                elif edge.target_id.startswith("user"):
                    users.add(edge.target_id)
        return len(users)
    
    def add_simple_event(
        self,
        user_id: str,
        device_id: str,
        ip_address: str,
        is_vpn: bool = False,
        is_tor: bool = False,
    ) -> None:
        """Add a login event using simple parameters.
        Simpler alternative to add_login_event() when full
        """
        from datetime import datetime
        
        # Create/update user node with minimal features
        self._user_login_counts[user_id] = self._user_login_counts.get(user_id, 0) + 1
        features = np.zeros(self.config.user_feature_dim, dtype=np.float32)
        features[0] = min(np.log1p(self._user_login_counts[user_id]) / 5.0, 1.0)
        
        user_node = GraphNode(
            node_id=user_id,
            node_type=NodeType.USER,
            features=features,
            metadata={"last_login": datetime.now().isoformat()},
        )
        self._graph.add_node(user_node)
        
        # Create/update device node with minimal features
        self._device_usage_counts[device_id] = self._device_usage_counts.get(device_id, 0) + 1
        device_features = np.zeros(self.config.device_feature_dim, dtype=np.float32)
        device_features[2] = min(np.log1p(self._device_usage_counts[device_id]) / 5.0, 1.0)
        
        device_node = GraphNode(
            node_id=device_id,
            node_type=NodeType.DEVICE,
            features=device_features,
            metadata={},
        )
        self._graph.add_node(device_node)
        
        # Create/update IP node
        if ip_address not in self._ip_account_counts:
            self._ip_account_counts[ip_address] = set()
        self._ip_account_counts[ip_address].add(user_id)
        
        ip_features = np.zeros(self.config.ip_feature_dim, dtype=np.float32)
        ip_features[0] = min(len(self._ip_account_counts[ip_address]) / 10.0, 1.0)
        ip_features[1] = 1.0 if is_vpn else 0.0
        ip_features[2] = 1.0 if is_tor else 0.0
        
        ip_node = GraphNode(
            node_id=ip_address,
            node_type=NodeType.IP,
            features=ip_features,
            metadata={"is_vpn": is_vpn, "is_tor": is_tor},
        )
        self._graph.add_node(ip_node)
        
        # Add edges
        now = datetime.now()
        self._add_edge_if_new(user_id, device_id, EdgeType.USER_DEVICE, now)
        self._add_edge_if_new(device_id, ip_address, EdgeType.DEVICE_IP, now)
        self._add_edge_if_new(user_id, ip_address, EdgeType.USER_IP, now)
