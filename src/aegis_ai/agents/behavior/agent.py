"""Behavioral Consistency Agent - compares current behavior with historical patterns.

Identity continuity check: measures deviation from baseline.
Low score means different, not necessarily fraudulent.

This agent must feel reasonable, not aggressive.
This agent thinks. It does not act.
"""

from src.aegis_ai.data.schemas.login_event import LoginEvent
from src.aegis_ai.data.schemas.session import Session
from src.aegis_ai.data.schemas.user import User
from src.aegis_ai.agents.behavior.schema import BehavioralOutput


class BehaviorAgent:
    """Behavioral Consistency Agent - Identity Continuity.
    
    Responsibilities:
    - Compare current session vs historical baseline
    - Calculate distance-based behavioral scoring
    - Surface behavioral deviations
    
    Constraints:
    - No network data (isolated)
    - No fraud conclusions
    - No side effects
    - No logging decisions
    - No raising actions
    """
    
    # Deviation weights
    DEVIATION_WEIGHTS = {
        "time_anomaly": 0.25,
        "auth_method_change": 0.15,
        "location_mismatch": 0.30,
        "device_type_change": 0.15,
        "browser_change": 0.10,
        "os_change": 0.10,
    }
    
    def analyze(
        self,
        login_event: LoginEvent,
        session: Session,
        user: User,
        historical_baseline: dict | None = None
    ) -> BehavioralOutput:
        """Analyze behavioral consistency with user baseline.
        
        Args:
            login_event: Validated LoginEvent schema object
            session: Validated Session schema object
            user: Validated User schema object
            historical_baseline: Optional dict with historical patterns:
                - typical_auth_methods: list[str]
                - typical_device_types: list[str]
                - typical_browsers: list[str]
                - typical_os: list[str]
            
        Returns:
            BehavioralOutput with behavioral_match_score and deviation_summary
        """
        deviation_score = 0.0
        deviations: list[str] = []
        
        # Default baseline if none provided
        if historical_baseline is None:
            historical_baseline = {}
        
        # Time window anomaly detection
        login_hour = session.start_time.hour
        if not self._is_within_typical_hours(
            login_hour,
            user.typical_login_hour_start,
            user.typical_login_hour_end
        ):
            deviation_score += self.DEVIATION_WEIGHTS["time_anomaly"]
            deviations.append("login_time_outside_typical_window")
        
        # Location mismatch (home country/city)
        if session.geo_location.country != user.home_country:
            deviation_score += self.DEVIATION_WEIGHTS["location_mismatch"]
            deviations.append("login_from_different_country_than_home")
        elif session.geo_location.city != user.home_city:
            # Smaller penalty for different city, same country
            deviation_score += self.DEVIATION_WEIGHTS["location_mismatch"] * 0.5
            deviations.append("login_from_different_city_than_home")
        
        # Authentication method change
        typical_methods = historical_baseline.get("typical_auth_methods", [])
        if typical_methods and login_event.auth_method not in typical_methods:
            deviation_score += self.DEVIATION_WEIGHTS["auth_method_change"]
            deviations.append("different_auth_method_than_usual")
        
        # Device type change
        typical_device_types = historical_baseline.get("typical_device_types", [])
        if typical_device_types:
            # We'd need device info here - using session metadata if available
            pass  # Placeholder for device type comparison
        
        # Browser/OS changes from baseline
        typical_browsers = historical_baseline.get("typical_browsers", [])
        typical_os = historical_baseline.get("typical_os", [])
        
        # These would require device info passed in
        # For now, flag if completely new device
        if login_event.is_new_device:
            deviation_score += self.DEVIATION_WEIGHTS["browser_change"]
            deviation_score += self.DEVIATION_WEIGHTS["os_change"]
            deviations.append("new_device_environment")
        
        # Calculate match score (inverse of deviation)
        # Clamp deviation to [0, 1] first
        clamped_deviation = max(0.0, min(1.0, deviation_score))
        match_score = 1.0 - clamped_deviation
        
        return BehavioralOutput(
            behavioral_match_score=match_score,
            deviation_summary=deviations
        )
    
    def _is_within_typical_hours(
        self,
        current_hour: int,
        start_hour: int,
        end_hour: int
    ) -> bool:
        """Check if current hour is within typical login window.
        
        Handles overnight windows (e.g., 22:00 to 06:00).
        """
        if start_hour <= end_hour:
            # Normal window (e.g., 8:00 to 18:00)
            return start_hour <= current_hour <= end_hour
        else:
            # Overnight window (e.g., 22:00 to 06:00)
            return current_hour >= start_hour or current_hour <= end_hour
