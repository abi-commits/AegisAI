"""Unit tests for Network Agent.

Testing discipline: Light but mandatory.
- One happy path test
- One edge case test  
- One weird but valid input test
"""

import pytest
from datetime import datetime

from aegis_ai.agents.network.agent import NetworkAgent
from aegis_ai.agents.network.schema import NetworkOutput
from aegis_ai.data.schemas.session import Session, GeoLocation
from aegis_ai.data.schemas.device import Device


@pytest.fixture
def network_agent():
    """Create a NetworkAgent instance in heuristic mode."""
    return NetworkAgent(use_gnn_model=False)


@pytest.fixture
def clean_session():
    """Session with no network risk signals."""
    return Session(
        session_id="sess_clean_001",
        user_id="user_clean",
        device_id="dev_clean_001",
        ip_address="192.168.1.100",
        geo_location=GeoLocation(
            city="New York",
            country="US",
            latitude=40.7128,
            longitude=-74.0060,
        ),
        start_time=datetime(2026, 1, 25, 10, 0, 0),
        is_vpn=False,
        is_tor=False,
    )


@pytest.fixture
def clean_device():
    """Device with no sharing concerns."""
    return Device(
        device_id="dev_clean_001",
        device_type="desktop",
        os="Windows 11",
        browser="Chrome 120",
        is_known=True,
    )


@pytest.fixture
def clean_network_context():
    """Network context with no risk signals."""
    return {
        "ip_shared_account_count": 1,  # Only this user
        "device_shared_account_count": 1,  # Only this user
        "is_datacenter_ip": False,
        "is_known_proxy_range": False,
        "is_in_risky_cluster": False,
    }


class TestNetworkAgentHappyPath:
    """Happy path tests for NetworkAgent."""
    
    def test_clean_network_returns_low_risk(
        self,
        network_agent,
        clean_session,
        clean_device,
        clean_network_context
    ):
        """Clean network should return low risk score."""
        result = network_agent.analyze(
            clean_session,
            clean_device,
            clean_network_context
        )
        
        # Verify output type
        assert isinstance(result, NetworkOutput)
        
        # Low risk for clean network
        assert result.network_risk_score == 0.0
        
        # No evidence links
        assert len(result.evidence_links) == 0
    
    def test_output_validates_via_schema(
        self,
        network_agent,
        clean_session,
        clean_device,
        clean_network_context
    ):
        """Output should validate via Pydantic schema."""
        result = network_agent.analyze(
            clean_session,
            clean_device,
            clean_network_context
        )
        
        # Convert to dict and back
        result_dict = result.model_dump()
        validated = NetworkOutput(**result_dict)
        
        assert validated.network_risk_score == result.network_risk_score


class TestNetworkAgentEdgeCases:
    """Edge case tests for NetworkAgent."""
    
    def test_maximum_network_risk_signals(self, network_agent):
        """All network risk signals should accumulate properly."""
        suspicious_session = Session(
            session_id="sess_sus",
            user_id="user_sus",
            device_id="dev_sus",
            ip_address="185.220.101.1",
            geo_location=GeoLocation(
                city="Unknown",
                country="XX",
                latitude=0.0,
                longitude=0.0,
            ),
            start_time=datetime(2026, 1, 25, 3, 0, 0),
            is_vpn=True,
            is_tor=True,
        )
        
        suspicious_device = Device(
            device_id="dev_sus",
            device_type="mobile",
            os="Android 14",
            browser="Unknown",
            is_known=False,
        )
        
        risky_network_context = {
            "ip_shared_account_count": 10,  # Many accounts share IP
            "device_shared_account_count": 5,  # Device used by multiple users
            "is_datacenter_ip": True,
            "is_known_proxy_range": True,
            "is_in_risky_cluster": True,
            "cluster_fraud_rate": 0.8,  # 80% fraud rate in cluster
        }
        
        result = network_agent.analyze(
            suspicious_session,
            suspicious_device,
            risky_network_context
        )
        
        # High risk score
        assert result.network_risk_score >= 0.7
        
        # Multiple evidence links
        assert len(result.evidence_links) >= 4
    
    def test_score_clamped_to_one(self, network_agent, clean_session, clean_device):
        """Score should never exceed 1.0 even with extreme signals."""
        extreme_context = {
            "ip_shared_account_count": 100,  # Extreme sharing
            "device_shared_account_count": 50,
            "is_datacenter_ip": True,
            "is_known_proxy_range": True,
            "is_in_risky_cluster": True,
            "cluster_fraud_rate": 1.0,  # 100% fraud cluster
        }
        
        result = network_agent.analyze(
            clean_session,
            clean_device,
            extreme_context
        )
        
        # Score clamped to 1.0
        assert result.network_risk_score == 1.0


class TestNetworkAgentWeirdButValid:
    """Weird but valid input tests."""
    
    def test_no_network_context_provided(
        self,
        network_agent,
        clean_session,
        clean_device
    ):
        """Agent should work without network context."""
        result = network_agent.analyze(
            clean_session,
            clean_device,
            network_context=None  # No context provided
        )
        
        # Should return valid output with zero risk
        assert isinstance(result, NetworkOutput)
        assert result.network_risk_score == 0.0
    
    def test_vpn_session_adds_evidence(self, network_agent, clean_device):
        """VPN session should add evidence even without network context."""
        vpn_session = Session(
            session_id="sess_vpn",
            user_id="user_vpn",
            device_id="dev_clean_001",
            ip_address="10.0.0.1",
            geo_location=GeoLocation(
                city="Unknown",
                country="US",
                latitude=40.0,
                longitude=-74.0,
            ),
            start_time=datetime(2026, 1, 25, 12, 0, 0),
            is_vpn=True,  # VPN detected
            is_tor=False,
        )
        
        result = network_agent.analyze(
            vpn_session,
            clean_device,
            network_context=None
        )
        
        # VPN should be in evidence
        assert any("vpn" in e.lower() for e in result.evidence_links)
    
    def test_single_account_ip_no_sharing_flag(
        self,
        network_agent,
        clean_session,
        clean_device
    ):
        """Single account on IP should not flag sharing."""
        single_user_context = {
            "ip_shared_account_count": 1,  # Only this user
            "device_shared_account_count": 1,
        }
        
        result = network_agent.analyze(
            clean_session,
            clean_device,
            single_user_context
        )
        
        # No sharing evidence
        sharing_evidence = [e for e in result.evidence_links if "shared" in e]
        assert len(sharing_evidence) == 0
