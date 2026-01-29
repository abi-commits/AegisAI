"""Feature extraction for risk scoring models.

Converts schema objects (LoginEvent, Session, Device) into
numerical feature vectors for ML model input.

Feature engineering decisions are documented for auditability.
"""

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from aegis_ai.data.schemas.login_event import LoginEvent
from aegis_ai.data.schemas.session import Session
from aegis_ai.data.schemas.device import Device


@dataclass
class FeatureConfig:
    """Configuration for feature extraction.
    
    Attributes:
        include_device_features: Include device-related features
        include_network_features: Include network/session features
        include_velocity_features: Include time/velocity features
        failed_attempts_cap: Maximum failed attempts to consider
        long_absence_hours: Threshold for "long absence" flag
        normalize_features: Whether to normalize numeric features
    """
    include_device_features: bool = True
    include_network_features: bool = True
    include_velocity_features: bool = True
    failed_attempts_cap: int = 3
    long_absence_hours: float = 720.0  # 30 days
    normalize_features: bool = False  # GBDT doesn't need normalization


# Feature name registry - defines the canonical feature order
FEATURE_NAMES = [
    # Device features
    "is_new_device",           # LoginEvent.is_new_device OR not Device.is_known
    "device_not_known",        # Explicitly from Device.is_known
    
    # Network/Location features
    "is_new_ip",               # LoginEvent.is_new_ip
    "is_new_location",         # LoginEvent.is_new_location
    "is_vpn",                  # Session.is_vpn
    "is_tor",                  # Session.is_tor
    
    # Velocity features
    "failed_attempts_before",  # Capped count
    "failed_attempts_capped",  # Binary: hit the cap?
    
    # Time features
    "time_since_last_login_hours",  # Hours (null -> -1)
    "is_long_absence",              # Binary threshold flag
    
    # Auth features
    "auth_method_password",    # One-hot encoded
    "auth_method_mfa",
    "auth_method_sso",
    "auth_method_biometric",
]


class FeatureExtractor:
    """Extract features from login context for risk scoring.
    
    Maintains consistent feature ordering and handles missing values.
    All transformations are documented and deterministic.
    """
    
    def __init__(self, config: Optional[FeatureConfig] = None):
        """Initialize feature extractor.
        
        Args:
            config: Feature extraction configuration
        """
        self.config = config or FeatureConfig()
        self._feature_names = FEATURE_NAMES.copy()
    
    @property
    def feature_names(self) -> list[str]:
        """Return ordered list of feature names."""
        return self._feature_names
    
    @property
    def n_features(self) -> int:
        """Return number of features."""
        return len(self._feature_names)
    
    def extract(
        self,
        login_event: LoginEvent,
        session: Session,
        device: Device
    ) -> np.ndarray:
        """Extract features from login context.
        
        Args:
            login_event: Login event data
            session: Session data
            device: Device data
            
        Returns:
            1D numpy array of feature values
        """
        features = []
        
        # Device features
        features.append(float(login_event.is_new_device or not device.is_known))
        features.append(float(not device.is_known))
        
        # Network/Location features
        features.append(float(login_event.is_new_ip))
        features.append(float(login_event.is_new_location))
        features.append(float(session.is_vpn))
        features.append(float(session.is_tor))
        
        # Velocity features - capped
        capped_attempts = min(
            login_event.failed_attempts_before,
            self.config.failed_attempts_cap
        )
        features.append(float(capped_attempts))
        features.append(float(login_event.failed_attempts_before >= self.config.failed_attempts_cap))
        
        # Time features
        time_since = login_event.time_since_last_login_hours
        if time_since is None:
            # Use -1 for missing (GBDT handles this well)
            features.append(-1.0)
            features.append(0.0)  # Can't determine absence
        else:
            features.append(time_since)
            features.append(float(time_since > self.config.long_absence_hours))
        
        # Auth method one-hot encoding
        auth_method = login_event.auth_method
        features.append(float(auth_method == "password"))
        features.append(float(auth_method == "mfa"))
        features.append(float(auth_method == "sso"))
        features.append(float(auth_method == "biometric"))
        
        return np.array(features, dtype=np.float32)
    
    def extract_batch(
        self,
        login_events: list[LoginEvent],
        sessions: list[Session],
        devices: list[Device]
    ) -> np.ndarray:
        """Extract features from multiple login contexts.
        
        Args:
            login_events: List of login events
            sessions: List of sessions
            devices: List of devices
            
        Returns:
            2D numpy array (n_samples, n_features)
        """
        if not (len(login_events) == len(sessions) == len(devices)):
            raise ValueError("All input lists must have the same length")
        
        return np.vstack([
            self.extract(le, s, d)
            for le, s, d in zip(login_events, sessions, devices)
        ])
    
    def feature_to_factor_name(self, feature_name: str) -> str:
        """Map feature name to human-readable risk factor name.
        
        Args:
            feature_name: Internal feature name
            
        Returns:
            Human-readable factor name for output
        """
        mapping = {
            "is_new_device": "new_device_detected",
            "device_not_known": "unknown_device",
            "is_new_ip": "login_from_new_ip",
            "is_new_location": "login_from_new_country",
            "is_vpn": "vpn_or_proxy_detected",
            "is_tor": "tor_exit_node_detected",
            "failed_attempts_before": "high_login_velocity",
            "failed_attempts_capped": "excessive_failed_attempts",
            "time_since_last_login_hours": "unusual_login_timing",
            "is_long_absence": "login_after_extended_absence",
            "auth_method_password": "password_auth",
            "auth_method_mfa": "mfa_auth",
            "auth_method_sso": "sso_auth",
            "auth_method_biometric": "biometric_auth",
        }
        return mapping.get(feature_name, feature_name)
