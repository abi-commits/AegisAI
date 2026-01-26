"""Network & Evidence Agent - surfaces relational risk via shared infrastructure.

Suspicion by association: points to evidence without concluding.
Uses shared IP counts, device reuse, and known risky clusters.

Phase 4: GNN-based network risk scoring with GraphSAGE embeddings.
Falls back to heuristic if model unavailable.

This agent never concludes, it only points.
This agent thinks. It does not act.
"""

from typing import Optional, List, Dict, Tuple

import numpy as np

from src.aegis_ai.data.schemas.session import Session
from src.aegis_ai.data.schemas.device import Device
from src.aegis_ai.agents.network.schema import NetworkOutput
from src.aegis_ai.models.graph.builder import GraphBuilder
from src.aegis_ai.models.graph.schema import NodeType


class NetworkAgent:
    """Network & Evidence Agent - Suspicion by Association.
    
    Owns the user-device-IP graph and computes network risk signals.
    
    Responsibilities:
    - Identify shared infrastructure patterns
    - Surface evidence of network-based risk
    - Flag known risky clusters
    - Use GNN embeddings for graph-based risk (Phase 4)
    
    Constraints:
    - Evidence only, no verdicts
    - No fraud conclusions
    - No side effects
    - No logging decisions
    - No raising actions
    """
    
    # Risk weights for graph signals
    RISK_WEIGHTS = {
        "shared_ip_per_account": 0.08,
        "shared_device_per_account": 0.12,
        "vpn_ip": 0.10,
        "tor_ip": 0.25,
        "high_degree_device": 0.15,
    }
    
    # Thresholds
    MAX_SHARED_ACCOUNTS = 5
    HIGH_DEGREE_THRESHOLD = 10
    
    def __init__(self, use_gnn_model: bool = True, fallback_to_heuristic: bool = True):
        """Initialize Network Agent.
        
        Args:
            use_gnn_model: Whether to use GNN for embeddings
            fallback_to_heuristic: Fall back if GNN fails
        """
        self._graph_builder = GraphBuilder()
        self._use_gnn_model = use_gnn_model
        self._fallback_to_heuristic = fallback_to_heuristic
        
        # Lazy-loaded GNN model
        self._gnn_model: Optional[object] = None
        self._model_initialized = False
        
        # Cache for user risk labels (for risk propagation)
        self._user_risk_labels: Dict[str, float] = {}
    
    def _init_gnn_model(self) -> bool:
        """Initialize GNN model lazily.
        
        Returns:
            True if model initialized successfully
        """
        if self._model_initialized:
            return self._gnn_model is not None
        
        self._model_initialized = True
        
        if not self._use_gnn_model:
            return False
        
        try:
            from src.aegis_ai.models.graph.sage_model import GraphSAGEModel
            self._gnn_model = GraphSAGEModel()
            return True
        except Exception:
            self._gnn_model = None
            return False
    
    def analyze(
        self,
        session: Session,
        device: Device,
        network_context: dict | None = None,
        user_id: Optional[str] = None,
    ) -> NetworkOutput:
        """Analyze network evidence and return risk signals.
        
        Uses GNN-based scoring if available, falls back to heuristic.
        
        Args:
            session: Validated Session schema object
            device: Validated Device schema object
            network_context: Optional dict with network intelligence
            user_id: User identifier for graph-based scoring
            
        Returns:
            NetworkOutput with network_risk_score and evidence_links
        """
        # Try GNN-based scoring first
        if self._use_gnn_model and user_id:
            try:
                return self._analyze_with_gnn(session, device, user_id)
            except Exception:
                if not self._fallback_to_heuristic:
                    raise
                # Fall through to heuristic
        
        return self._analyze_heuristic(session, device, network_context)
    
    def _analyze_with_gnn(
        self,
        session: Session,
        device: Device,
        user_id: str,
    ) -> NetworkOutput:
        """Analyze using graph structure and GNN embeddings.
        
        Args:
            session: Session data
            device: Device data
            user_id: User identifier
            
        Returns:
            NetworkOutput with risk score and evidence
        """
        # Add current event to graph
        self._graph_builder.add_simple_event(
            user_id=user_id,
            device_id=device.device_id,
            ip_address=session.ip_address,
            is_vpn=session.is_vpn,
            is_tor=session.is_tor,
        )
        
        risk_score = 0.0
        evidence: List[str] = []
        
        # 1. IP sharing analysis
        ip_risk, ip_evidence = self._analyze_ip_sharing(session.ip_address)
        risk_score += ip_risk
        evidence.extend(ip_evidence)
        
        # 2. Device sharing analysis
        device_risk, device_evidence = self._analyze_device_sharing(device.device_id)
        risk_score += device_risk
        evidence.extend(device_evidence)
        
        # 3. VPN/Tor signals
        network_risk, network_evidence = self._analyze_network_signals(session)
        risk_score += network_risk
        evidence.extend(network_evidence)
        
        # 4. Neighbor risk propagation
        neighbor_risk, neighbor_evidence = self._analyze_neighbor_risk(user_id)
        risk_score += neighbor_risk
        evidence.extend(neighbor_evidence)
        
        # 5. GNN embedding-based scoring (if available)
        if self._init_gnn_model() and self._gnn_model:
            emb_risk = self._embedding_based_score(user_id)
            # Blend embedding score with heuristic score
            risk_score = 0.7 * risk_score + 0.3 * emb_risk
        
        # Clamp to [0, 1]
        clamped_score = max(0.0, min(1.0, risk_score))
        
        return NetworkOutput(
            network_risk_score=clamped_score,
            evidence_links=evidence,
        )
    
    def _analyze_heuristic(
        self,
        session: Session,
        device: Device,
        network_context: dict | None = None,
    ) -> NetworkOutput:
        """Analyze using heuristic-based network risk scoring.
        
        Original Phase 1-3 logic.
        
        Args:
            session: Session data
            device: Device data
            network_context: Optional network intelligence dict
            
        Returns:
            NetworkOutput with heuristic-based risk score
        """
        risk_score = 0.0
        evidence: List[str] = []
        
        if network_context is None:
            network_context = {}
        
        # Shared IP analysis
        ip_shared_count = network_context.get("ip_shared_account_count", 1)
        if ip_shared_count > 1:
            additional_accounts = min(ip_shared_count - 1, self.MAX_SHARED_ACCOUNTS)
            risk_score += self.RISK_WEIGHTS["shared_ip_per_account"] * additional_accounts
            evidence.append(f"ip_shared_with_{ip_shared_count - 1}_other_accounts")
        
        # Shared device analysis
        device_shared_count = network_context.get("device_shared_account_count", 1)
        if device_shared_count > 1:
            additional_accounts = min(device_shared_count - 1, self.MAX_SHARED_ACCOUNTS)
            risk_score += self.RISK_WEIGHTS["shared_device_per_account"] * additional_accounts
            evidence.append(f"device_seen_on_{device_shared_count - 1}_other_users")
        
        # VPN/Tor detection
        if session.is_vpn:
            risk_score += self.RISK_WEIGHTS["vpn_ip"]
            evidence.append("session_via_vpn_or_proxy")
        if session.is_tor:
            risk_score += self.RISK_WEIGHTS["tor_ip"]
            evidence.append("session_via_tor_network")
        
        # Clamp score to [0, 1]
        clamped_score = max(0.0, min(1.0, risk_score))
        
        return NetworkOutput(
            network_risk_score=clamped_score,
            evidence_links=evidence,
        )
    
    def _analyze_ip_sharing(self, ip_address: str) -> Tuple[float, List[str]]:
        """Analyze IP sharing patterns.
        
        Args:
            ip_address: IP to analyze
            
        Returns:
            Tuple of (risk_score, evidence_list)
        """
        risk = 0.0
        evidence = []
        
        account_count = self._graph_builder.get_ip_account_count(ip_address)
        
        if account_count > 1:
            other_accounts = account_count - 1
            capped = min(other_accounts, self.MAX_SHARED_ACCOUNTS)
            risk = self.RISK_WEIGHTS["shared_ip_per_account"] * capped
            evidence.append(f"ip_shared_with_{other_accounts}_other_accounts")
        
        return risk, evidence
    
    def _analyze_device_sharing(self, device_id: str) -> Tuple[float, List[str]]:
        """Analyze device sharing patterns.
        
        Args:
            device_id: Device to analyze
            
        Returns:
            Tuple of (risk_score, evidence_list)
        """
        risk = 0.0
        evidence = []
        
        account_count = self._graph_builder.get_device_account_count(device_id)
        
        if account_count > 1:
            other_accounts = account_count - 1
            capped = min(other_accounts, self.MAX_SHARED_ACCOUNTS)
            risk = self.RISK_WEIGHTS["shared_device_per_account"] * capped
            evidence.append(f"device_used_by_{other_accounts}_other_users")
        
        # High-degree device (used by many accounts)
        if account_count > self.HIGH_DEGREE_THRESHOLD:
            risk += self.RISK_WEIGHTS["high_degree_device"]
            evidence.append("device_has_unusually_high_usage")
        
        return risk, evidence
    
    def _analyze_network_signals(self, session: Session) -> Tuple[float, List[str]]:
        """Analyze network signals from session.
        
        Args:
            session: Session data
            
        Returns:
            Tuple of (risk_score, evidence_list)
        """
        risk = 0.0
        evidence = []
        
        if session.is_vpn:
            risk += self.RISK_WEIGHTS["vpn_ip"]
            evidence.append("session_via_vpn_or_proxy")
        
        if session.is_tor:
            risk += self.RISK_WEIGHTS["tor_ip"]
            evidence.append("session_via_tor_network")
        
        return risk, evidence
    
    def _analyze_neighbor_risk(self, user_id: str) -> Tuple[float, List[str]]:
        """Analyze risk from neighboring nodes.
        
        Args:
            user_id: User to analyze
            
        Returns:
            Tuple of (risk_score, evidence_list)
        """
        risk = 0.0
        evidence = []
        
        graph = self._graph_builder.graph
        
        if user_id not in graph.nodes:
            return risk, evidence
        
        neighbors = graph.get_neighbors(user_id)
        
        # Check for known risky neighbors
        risky_neighbors = 0
        for neighbor in neighbors:
            neighbor_risk = self._user_risk_labels.get(neighbor.node_id, 0.0)
            if neighbor_risk > 0.5:
                risky_neighbors += 1
        
        return risk, evidence
    
    def _embedding_based_score(self, user_id: str) -> float:
        """Compute risk score from GNN embeddings.
        
        Uses embedding norm as anomaly signal.
        
        Args:
            user_id: User to score
            
        Returns:
            Risk score (0-1)
        """
        try:
            graph = self._graph_builder.graph
            embedding = self._gnn_model.get_node_embedding(graph, user_id)
            
            # Embedding norm as anomaly signal
            norm = np.linalg.norm(embedding)
            risk = min(norm / 5.0, 1.0)
            
            return risk
        except Exception:
            return 0.0
    
    def update_graph(
        self,
        user_id: str,
        device_id: str,
        ip_address: str,
        is_vpn: bool = False,
        is_tor: bool = False,
    ) -> None:
        """Add a login event to the network graph.
        
        Args:
            user_id: User identifier
            device_id: Device identifier
            ip_address: IP address
            is_vpn: Whether session was via VPN
            is_tor: Whether session was via Tor
        """
        self._graph_builder.add_simple_event(
            user_id=user_id,
            device_id=device_id,
            ip_address=ip_address,
            is_vpn=is_vpn,
            is_tor=is_tor,
        )
    
    def set_user_risk_label(self, user_id: str, risk: float) -> None:
        """Set known risk label for a user (for risk propagation).
        
        Args:
            user_id: User identifier
            risk: Risk level (0-1)
        """
        self._user_risk_labels[user_id] = risk
