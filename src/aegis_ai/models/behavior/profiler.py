"""Behavioral profiler for session embedding and anomaly detection.

Converts login context to embeddings and manages user profiles.
This is the main interface for behavioral anomaly detection.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional, Dict
import math

import numpy as np

from src.aegis_ai.data.schemas.login_event import LoginEvent
from src.aegis_ai.data.schemas.session import Session
from src.aegis_ai.data.schemas.user import User
from src.aegis_ai.data.schemas.device import Device
from src.aegis_ai.models.behavior.profile import (
    BehavioralProfile,
    ProfileConfig,
    SessionEmbedding,
)
from src.aegis_ai.models.behavior.distance import (
    DistanceCalculator,
    DistanceMethod,
    AnomalyScore,
)
from src.aegis_ai.models.behavior.config import BehaviorConfig


class SessionEmbedder:
    """Embed login sessions into fixed-dimensional vectors.

    Embedding layout is configurable via `BehaviorConfig`.
    """

    def __init__(self, config: Optional[BehaviorConfig] = None):
        self.config = config or BehaviorConfig()
        self.embedding_dim = self.config.embedding_dim
        self.device_types = self.config.device_types
        self.auth_methods = self.config.auth_methods

    def embed(
        self,
        login_event: LoginEvent,
        session: Session,
        device: Optional[Device] = None
    ) -> SessionEmbedding:
        vector = np.zeros(self.embedding_dim, dtype=np.float32)

        # Hour of day (cyclical encoding)
        hour = session.start_time.hour
        vector[0] = math.sin(2 * math.pi * hour / self.config.hours_in_day)
        vector[1] = math.cos(2 * math.pi * hour / self.config.hours_in_day)

        # Day of week (cyclical encoding)
        day = session.start_time.weekday()
        vector[2] = math.sin(2 * math.pi * day / self.config.days_in_week)
        vector[3] = math.cos(2 * math.pi * day / self.config.days_in_week)

        # Device type (one-hot)
        if device is not None:
            device_idx = self.device_types.get(device.device_type, 0)
            vector[4 + device_idx] = 1.0
        else:
            default_idx = self.device_types.get(self.config.default_device, 0)
            vector[4 + default_idx] = 1.0

        # Auth method (one-hot)
        auth_idx = self.auth_methods.get(login_event.auth_method, 0)
        vector[7 + auth_idx] = 1.0

        # Location (normalized lat/lon)
        vector[11] = session.geo_location.latitude / self.config.location_norm_lat
        vector[12] = session.geo_location.longitude / self.config.location_norm_lon

        # Network flags
        vector[13] = 1.0 if session.is_vpn else 0.0
        vector[14] = 1.0 if session.is_tor else 0.0

        # Time since last login (log-normalized)
        if login_event.time_since_last_login_hours is not None:
            log_hours = math.log1p(login_event.time_since_last_login_hours)
            vector[15] = min(log_hours / self.config.time_norm_div, 1.0)
        else:
            vector[15] = self.config.unknown_time_value

        return SessionEmbedding(
            vector=vector,
            timestamp=session.start_time,
            session_id=session.session_id,
        )


class BehavioralProfiler:
    """Main interface for behavioral anomaly detection.
    
    Manages user profiles and computes behavioral anomaly scores.
    No fraud labels required - this is unsupervised anomaly detection.
    
    Answers: "Does this look like the same human?"
    Not: "Is this fraud?"
    """
    
    def __init__(
        self,
        config: Optional[ProfileConfig] = None,
        distance_method: DistanceMethod = DistanceMethod.COSINE,
        profile_store_path: Optional[Path] = None,
        behavior_config: Optional[BehaviorConfig] = None,
    ):
        """Initialize behavioral profiler.
        
        Args:
            config: Profile configuration
            distance_method: Method for distance calculation
            profile_store_path: Path to store/load profiles
        """
        self.config = config or ProfileConfig()
        self.distance_method = distance_method
        self.profile_store_path = profile_store_path
        self.behavior_config = behavior_config or BehaviorConfig()

        self._embedder = SessionEmbedder(self.behavior_config)
        self._calculator = DistanceCalculator(distance_method, config=self.behavior_config)
        self._profiles: Dict[str, BehavioralProfile] = {}
    
    def score_session(
        self,
        login_event: LoginEvent,
        session: Session,
        user: User,
        device: Optional[Device] = None,
        update_profile: bool = False
    ) -> AnomalyScore:
        """Score a session against the user's behavioral profile.
        
        Args:
            login_event: Login event data
            session: Session data
            user: User data
            device: Optional device data
            update_profile: Whether to update profile after scoring
            
        Returns:
            AnomalyScore with distance and normalized score
        """
        # Get or create profile
        profile = self._get_or_create_profile(user.user_id)
        
        # Embed session
        embedding = self._embedder.embed(login_event, session, device)
        
        # Compute anomaly score
        score = self._calculator.compute_distance(
            embedding, profile, self.distance_method
        )
        
        # Update profile if requested
        if update_profile or self.config.update_on_predict:
            profile.update(embedding)
        
        return score
    
    def update_profile(
        self,
        login_event: LoginEvent,
        session: Session,
        user: User,
        device: Optional[Device] = None
    ) -> None:
        """Update user's profile with new session (no scoring).
        
        Use this for building profiles from historical data.
        
        Args:
            login_event: Login event data
            session: Session data
            user: User data
            device: Optional device data
        """
        profile = self._get_or_create_profile(user.user_id)
        embedding = self._embedder.embed(login_event, session, device)
        profile.update(embedding)
    
    def get_match_score(
        self,
        login_event: LoginEvent,
        session: Session,
        user: User,
        device: Optional[Device] = None
    ) -> tuple[float, list[str]]:
        """Get behavioral match score and deviation summary.
        
        Convenience method that returns the format expected by BehaviorAgent.
        Match score = 1 - anomaly_score (higher = more similar to baseline)
        
        Args:
            login_event: Login event data
            session: Session data
            user: User data
            device: Optional device data
            
        Returns:
            Tuple of (match_score, deviation_summary)
        """
        anomaly = self.score_session(login_event, session, user, device)
        
        # Convert anomaly score to match score
        # anomaly_score: 0 = identical, 1 = very different
        # match_score: 1 = identical, 0 = very different
        match_score = 1.0 - anomaly.normalized_score
        
        return match_score, anomaly.deviation_factors
    
    def _get_or_create_profile(self, user_id: str) -> BehavioralProfile:
        """Get existing profile or create new one.
        
        Args:
            user_id: User identifier
            
        Returns:
            BehavioralProfile for the user
        """
        if user_id not in self._profiles:
            # Try to load from disk
            if self.profile_store_path is not None:
                profile_path = self.profile_store_path / f"{user_id}.json"
                if profile_path.exists():
                    self._profiles[user_id] = BehavioralProfile.load(profile_path)
                    return self._profiles[user_id]
            
            # Create new profile
            self._profiles[user_id] = BehavioralProfile.create_empty(
                user_id=user_id,
                embedding_dim=self._embedder.embedding_dim,
                config=self.config,
            )
        
        return self._profiles[user_id]
    
    def save_profiles(self, path: Optional[Path] = None) -> None:
        """Save all profiles to disk.
        
        Args:
            path: Directory to save profiles (uses profile_store_path if None)
        """
        path = path or self.profile_store_path
        if path is None:
            raise ValueError("No path specified for saving profiles")
        
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        
        for user_id, profile in self._profiles.items():
            profile.save(path / f"{user_id}.json")
    
    def load_profiles(self, path: Optional[Path] = None) -> int:
        """Load all profiles from disk.
        
        Args:
            path: Directory to load profiles from
            
        Returns:
            Number of profiles loaded
        """
        path = path or self.profile_store_path
        if path is None:
            raise ValueError("No path specified for loading profiles")
        
        path = Path(path)
        if not path.exists():
            return 0
        
        count = 0
        for profile_file in path.glob("*.json"):
            try:
                profile = BehavioralProfile.load(profile_file)
                self._profiles[profile.user_id] = profile
                count += 1
            except Exception:
                pass  # Skip invalid profiles
        
        return count
    
    def get_profile_stats(self, user_id: str) -> dict:
        """Get statistics about a user's profile.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary with profile statistics
        """
        if user_id not in self._profiles:
            return {"exists": False}
        
        profile = self._profiles[user_id]
        return {
            "exists": True,
            "is_valid": profile.is_valid,
            "session_count": profile.session_count,
            "last_updated": profile.last_updated.isoformat() if profile.last_updated else None,
            "has_covariance": profile.has_covariance,
            "history_size": len(profile.history),
        }
