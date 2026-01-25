"""Network & Evidence Agent - surfaces relational risk via shared infrastructure.

Suspicion by association: points to evidence without concluding.
Uses shared IP counts, device reuse, and known risky clusters.

This agent never concludes, it only points.
This agent thinks. It does not act.
"""

from src.aegis_ai.data.schemas.session import Session
from src.aegis_ai.data.schemas.device import Device
from src.aegis_ai.agents.network.schema import NetworkOutput


class NetworkAgent:
    """Network & Evidence Agent - Suspicion by Association.
    
    Responsibilities:
    - Identify shared infrastructure patterns
    - Surface evidence of network-based risk
    - Flag known risky clusters
    
    Constraints:
    - Evidence only, no verdicts
    - No fraud conclusions
    - No side effects
    - No logging decisions
    - No raising actions
    """
    
    # Risk weights for network signals
    RISK_WEIGHTS = {
        "shared_ip": 0.08,  # per additional account, capped
        "shared_device": 0.12,  # per additional account, capped
        "known_proxy_range": 0.20,
        "datacenter_ip": 0.15,
        "risky_cluster": 0.30,
    }
    
    # Caps for accumulating risks
    MAX_SHARED_IP_ACCOUNTS = 5
    MAX_SHARED_DEVICE_ACCOUNTS = 3
    
    def analyze(
        self,
        session: Session,
        device: Device,
        network_context: dict | None = None
    ) -> NetworkOutput:
        """Analyze network evidence and return risk signals.
        
        Args:
            session: Validated Session schema object
            device: Validated Device schema object
            network_context: Optional dict with network intelligence:
                - ip_shared_account_count: int (accounts sharing this IP)
                - device_shared_account_count: int (accounts using this device)
                - is_datacenter_ip: bool
                - is_known_proxy_range: bool
                - is_in_risky_cluster: bool
                - cluster_fraud_rate: float (0-1)
            
        Returns:
            NetworkOutput with network_risk_score and evidence_links
        """
        risk_score = 0.0
        evidence: list[str] = []
        
        # Default context if none provided
        if network_context is None:
            network_context = {}
        
        # Shared IP analysis
        ip_shared_count = network_context.get("ip_shared_account_count", 1)
        if ip_shared_count > 1:
            additional_accounts = min(
                ip_shared_count - 1,
                self.MAX_SHARED_IP_ACCOUNTS
            )
            risk_score += self.RISK_WEIGHTS["shared_ip"] * additional_accounts
            evidence.append(f"ip_shared_with_{ip_shared_count - 1}_other_accounts")
        
        # Shared device analysis
        device_shared_count = network_context.get("device_shared_account_count", 1)
        if device_shared_count > 1:
            additional_accounts = min(
                device_shared_count - 1,
                self.MAX_SHARED_DEVICE_ACCOUNTS
            )
            risk_score += self.RISK_WEIGHTS["shared_device"] * additional_accounts
            evidence.append(f"device_seen_on_{device_shared_count - 1}_other_users")
        
        # Known proxy range
        if network_context.get("is_known_proxy_range", False):
            risk_score += self.RISK_WEIGHTS["known_proxy_range"]
            evidence.append("ip_in_known_proxy_range")
        
        # Datacenter IP (hosting providers, cloud IPs)
        if network_context.get("is_datacenter_ip", False):
            risk_score += self.RISK_WEIGHTS["datacenter_ip"]
            evidence.append("ip_from_datacenter_or_hosting_provider")
        
        # Risky cluster membership
        if network_context.get("is_in_risky_cluster", False):
            cluster_fraud_rate = network_context.get("cluster_fraud_rate", 0.0)
            # Scale risk by cluster fraud rate
            cluster_risk = self.RISK_WEIGHTS["risky_cluster"] * cluster_fraud_rate
            risk_score += cluster_risk
            evidence.append(
                f"ip_device_combination_in_cluster_with_{cluster_fraud_rate:.0%}_fraud_rate"
            )
        
        # VPN/Tor detection from session (additional network signal)
        if session.is_vpn:
            evidence.append("session_via_vpn_or_proxy")
        if session.is_tor:
            evidence.append("session_via_tor_network")
        
        # Clamp score to [0, 1]
        clamped_score = max(0.0, min(1.0, risk_score))
        
        return NetworkOutput(
            network_risk_score=clamped_score,
            evidence_links=evidence
        )
