"""Behavioral Consistency Agent - compares current behavior with historical patterns.

Identity continuity check: measures deviation from baseline.
Low score means different, not necessarily fraudulent.

Phase 4: Profile-based anomaly detection.
- Session embedding vectors
- Distance from historical centroid (Cosine/Mahalanobis)
- No fraud labels required

This agent answers: "Does this look like the same human?"
Not: "Is this fraud?"

This agent must feel reasonable, not aggressive.
This agent thinks. It does not act.
"""

from pathlib import Path
from typing import Optional, Any

from src.aegis_ai.data.schemas.login_event import LoginEvent
from src.aegis_ai.data.schemas.session import Session
from src.aegis_ai.data.schemas.user import User
from src.aegis_ai.data.schemas.device import Device
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
    
    ML Integration (Phase 4):
    - Profile-based anomaly detection using embeddings
    - Cosine/Mahalanobis distance from behavioral centroid
    - Falls back to heuristic if profiler unavailable
    """
    
    # Deviation weights for heuristic fallback
    DEVIATION_WEIGHTS = {
        "time_anomaly": 0.25,
        "auth_method_change": 0.15,
        "location_mismatch": 0.30,
        "device_type_change": 0.15,
        "browser_change": 0.10,
        "os_change": 0.10,
    }
    
    def __init__(
        self,
        profile_store_path: Optional[Path] = None,
        use_ml_model: bool = True,
        fallback_to_heuristic: bool = True,
        update_profiles: bool = False
    ):
        """Initialize Behavior Agent.
        
        Args:
            profile_store_path: Path to user profile storage
            use_ml_model: Whether to use profile-based scoring
            fallback_to_heuristic: Fall back to heuristic on model failure
            update_profiles: Whether to update profiles on each analysis
        """
        self._profile_store_path = profile_store_path
        self._use_ml_model = use_ml_model
        self._fallback_to_heuristic = fallback_to_heuristic
        self._update_profiles = update_profiles
        
        # Lazy-loaded ML components
        self._profiler: Optional[Any] = None
        self._ml_initialized = False
    
    def _init_ml_components(self) -> bool:
        """Initialize ML components lazily.
        
        Returns:
            True if ML components initialized successfully
        """
        if self._ml_initialized:
            return self._profiler is not None
        
        self._ml_initialized = True
        
        if not self._use_ml_model:
            return False
        
        try:
            from src.aegis_ai.models.behavior import (
                BehavioralProfiler,
                DistanceMethod,
            )
            
            self._profiler = BehavioralProfiler(
                distance_method=DistanceMethod.COSINE,
                profile_store_path=self._profile_store_path,
            )
            
            # Load existing profiles if path provided
            if self._profile_store_path is not None:
                self._profiler.load_profiles()
            
            return True
            
        except Exception as e:
            self._profiler = None
            return False
    
    def analyze(
        self,
        login_event: LoginEvent,
        session: Session,
        user: User,
        device: Optional[Device] = None,
        historical_baseline: dict | None = None
    ) -> BehavioralOutput:
        """Analyze behavioral consistency with user baseline.
        
        Uses profile-based model if available, falls back to heuristic.
        
        Args:
            login_event: Validated LoginEvent schema object
            session: Validated Session schema object
            user: Validated User schema object
            device: Optional Device schema object
            historical_baseline: Optional dict with historical patterns
            
        Returns:
            BehavioralOutput with behavioral_match_score and deviation_summary
        """
        # Try profile-based scoring first
        if self._use_ml_model and self._init_ml_components():
            try:
                return self._analyze_with_profiler(
                    login_event, session, user, device
                )
            except Exception:
                if not self._fallback_to_heuristic:
                    raise
        
        # Heuristic fallback
        return self._analyze_heuristic(
            login_event, session, user, device, historical_baseline
        )
    
    def _analyze_with_profiler(
        self,
        login_event: LoginEvent,
        session: Session,
        user: User,
        device: Optional[Device]
    ) -> BehavioralOutput:
        """Analyze using profile-based anomaly detection.
        
        Args:
            login_event: Login event data
            session: Session data
            user: User data
            device: Optional device data
            
        Returns:
            BehavioralOutput with profile-based scoring
        """
        match_score, deviation_summary = self._profiler.get_match_score(
            login_event=login_event,
            session=session,
            user=user,
            device=device,
        )
        
        # Update profile if configured
        if self._update_profiles:
            self._profiler.update_profile(login_event, session, user, device)
        
        return BehavioralOutput(
            behavioral_match_score=match_score,
            deviation_summary=deviation_summary
        )
    
    def _analyze_heuristic(
        self,
        login_event: LoginEvent,
        session: Session,
        user: User,
        device: Optional[Device],
        historical_baseline: dict | None = None
    ) -> BehavioralOutput:
        """Analyze using rule-based heuristics.
        
        Original Phase 3 logic preserved for fallback.
        
        Args:
            login_event: Login event data
            session: Session data
            user: User data
            device: Optional device data
            historical_baseline: Optional historical patterns
            
        Returns:
            BehavioralOutput with heuristic-based scoring
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
        
        # Device type change (if device provided)
        if device is not None:
            typical_device_types = historical_baseline.get("typical_device_types", [])
            if typical_device_types and device.device_type not in typical_device_types:
                deviation_score += self.DEVIATION_WEIGHTS["device_type_change"]
                deviations.append("different_device_type_than_usual")
        
        # New device environment
        if login_event.is_new_device:
            deviation_score += self.DEVIATION_WEIGHTS["browser_change"]
            deviation_score += self.DEVIATION_WEIGHTS["os_change"]
            deviations.append("new_device_environment")
        
        # Calculate match score (inverse of deviation)
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
            return start_hour <= current_hour <= end_hour
        else:
            return current_hour >= start_hour or current_hour <= end_hour
    
    def update_user_profile(
        self,
        login_event: LoginEvent,
        session: Session,
        user: User,
        device: Optional[Device] = None
    ) -> None:
        """Manually update a user's behavioral profile.
        
        Use for building profiles from historical data.
        
        Args:
            login_event: Login event data
            session: Session data
            user: User data
            device: Optional device data
        """
        if self._init_ml_components():
            self._profiler.update_profile(login_event, session, user, device)
    
    def save_profiles(self) -> None:
        """Save all behavioral profiles to disk."""
        if self._profiler is not None:
            self._profiler.save_profiles()
