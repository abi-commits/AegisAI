"""Detection Agent - identifies anomalous login behavior.

Paranoid by design: flags risk signals without making decisions.
Rules-only logic, no ML dependencies.

This agent thinks. It does not act.
"""

from src.aegis_ai.data.schemas.login_event import LoginEvent
from src.aegis_ai.data.schemas.session import Session
from src.aegis_ai.data.schemas.device import Device
from src.aegis_ai.agents.detection.schema import DetectionOutput


class DetectionAgent:
    """Detection Agent - Paranoid by Design.
    
    Responsibilities:
    - Identify risk signals from login events
    - Flag anomalous patterns
    - Return structured risk assessment
    
    Constraints:
    - No blocking decisions
    - No confidence claims
    - No side effects
    - No logging decisions
    - No raising actions
    """
    
    # Risk weights for different signals
    RISK_WEIGHTS = {
        "new_device": 0.25,
        "new_ip": 0.15,
        "new_location": 0.30,
        "failed_attempts": 0.10,  # per attempt, capped
        "vpn_detected": 0.10,
        "tor_detected": 0.35,
        "long_time_since_login": 0.10,
    }
    
    # Thresholds
    FAILED_ATTEMPTS_CAP = 3  # Max contribution from failed attempts
    LONG_ABSENCE_HOURS = 720  # 30 days
    
    def analyze(
        self,
        login_event: LoginEvent,
        session: Session,
        device: Device
    ) -> DetectionOutput:
        """Analyze login event and return risk signals.
        
        Args:
            login_event: Validated LoginEvent schema object
            session: Validated Session schema object
            device: Validated Device schema object
            
        Returns:
            DetectionOutput with risk_signal_score and risk_factors
        """
        risk_score = 0.0
        risk_factors: list[str] = []
        
        # New device detection
        if login_event.is_new_device or not device.is_known:
            risk_score += self.RISK_WEIGHTS["new_device"]
            risk_factors.append("new_device_detected")
        
        # New IP detection
        if login_event.is_new_ip:
            risk_score += self.RISK_WEIGHTS["new_ip"]
            risk_factors.append("login_from_new_ip")
        
        # New location detection (highest weight)
        if login_event.is_new_location:
            risk_score += self.RISK_WEIGHTS["new_location"]
            risk_factors.append("login_from_new_country")
        
        # Failed attempts velocity
        if login_event.failed_attempts_before > 0:
            capped_attempts = min(
                login_event.failed_attempts_before,
                self.FAILED_ATTEMPTS_CAP
            )
            risk_score += self.RISK_WEIGHTS["failed_attempts"] * capped_attempts
            risk_factors.append(
                f"high_login_velocity_{login_event.failed_attempts_before}_failed_attempts"
            )
        
        # VPN detection
        if session.is_vpn:
            risk_score += self.RISK_WEIGHTS["vpn_detected"]
            risk_factors.append("vpn_or_proxy_detected")
        
        # Tor detection (high risk)
        if session.is_tor:
            risk_score += self.RISK_WEIGHTS["tor_detected"]
            risk_factors.append("tor_exit_node_detected")
        
        # Long absence
        if login_event.time_since_last_login_hours is not None:
            if login_event.time_since_last_login_hours > self.LONG_ABSENCE_HOURS:
                risk_score += self.RISK_WEIGHTS["long_time_since_login"]
                risk_factors.append("login_after_extended_absence")
        
        # Clamp score to [0, 1]
        clamped_score = max(0.0, min(1.0, risk_score))
        
        return DetectionOutput(
            risk_signal_score=clamped_score,
            risk_factors=risk_factors
        )
