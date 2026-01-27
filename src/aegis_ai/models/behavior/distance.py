"""Distance calculation for behavioral anomaly detection.

Computes distance from a session embedding to the user's
historical behavioral centroid.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np

from src.aegis_ai.models.behavior.profile import BehavioralProfile, SessionEmbedding
from src.aegis_ai.models.behavior.config import BehaviorConfig


class DistanceMethod(str, Enum):
    """Distance calculation method."""
    COSINE = "cosine"
    MAHALANOBIS = "mahalanobis"
    EUCLIDEAN = "euclidean"


@dataclass
class AnomalyScore:
    """Result of anomaly scoring.
    
    Attributes:
        distance: Raw distance from centroid
        normalized_score: Normalized anomaly score (0-1)
        method: Distance method used
        percentile: Percentile rank vs historical distances (if available)
        deviation_factors: Human-readable deviation explanations
    """
    distance: float
    normalized_score: float
    method: DistanceMethod
    percentile: Optional[float] = None
    deviation_factors: list[str] = None
    
    def __post_init__(self):
        if self.deviation_factors is None:
            self.deviation_factors = []


class DistanceCalculator:
    """Calculate behavioral distance for anomaly detection.

    Computes how far a new session embedding is from
    the user's historical behavioral centroid.
    """

    def __init__(self, 
                 default_method: DistanceMethod = DistanceMethod.COSINE, 
                 config: Optional[BehaviorConfig] = None):
        """Initialize distance calculator.

        Args:
            default_method: Default distance method to use
            config: BehaviorConfig with thresholds and constants
        """
        self.default_method = default_method
        self.config = config or BehaviorConfig()
    
    def compute_distance(
        self,
        embedding: SessionEmbedding,
        profile: BehavioralProfile,
        method: Optional[DistanceMethod] = None
    ) -> AnomalyScore:
        """Compute distance from embedding to profile centroid.
        
        Args:
            embedding: Current session embedding
            profile: User's behavioral profile
            method: Distance method (uses default if None)
            
        Returns:
            AnomalyScore with distance and normalized score
        """
        method = method or self.default_method
        
        # Handle invalid profiles (new users get benefit of the doubt)
        # normalized_score is ANOMALY score: 0 = normal, 1 = anomalous
        # For new users with no baseline, assume they are normal (low anomaly)
        if not profile.is_valid:
            return AnomalyScore(
                distance=0.0,
                normalized_score=0.10,  # Low anomaly = normal (benefit of doubt)
                method=method,
                deviation_factors=["new_user_no_baseline"]
            )
        
        # Compute distance based on method
        if method == DistanceMethod.COSINE:
            distance = self._cosine_distance(embedding.vector, profile.centroid)
            normalized = self._normalize_cosine(distance)
        elif method == DistanceMethod.MAHALANOBIS:
            if profile.has_covariance:
                distance = self._mahalanobis_distance(
                    embedding.vector, profile.centroid, profile.covariance_inv
                )
                normalized = self._normalize_mahalanobis(distance)
            else:
                # Fall back to Euclidean if no covariance
                distance = self._euclidean_distance(embedding.vector, profile.centroid)
                normalized = self._normalize_euclidean(distance)
                method = DistanceMethod.EUCLIDEAN
        else:  # EUCLIDEAN
            distance = self._euclidean_distance(embedding.vector, profile.centroid)
            normalized = self._normalize_euclidean(distance)
        
        # Generate deviation factors
        deviation_factors = self._identify_deviations(
            embedding.vector, profile.centroid, normalized
        )
        
        return AnomalyScore(
            distance=distance,
            normalized_score=normalized,
            method=method,
            deviation_factors=deviation_factors
        )
    
    def _cosine_distance(self, a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine distance (1 - cosine similarity).
        
        Returns value in [0, 2], where 0 = identical, 2 = opposite.
        """
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        
        if norm_a < self.config.epsilon or norm_b < self.config.epsilon:
            return 1.0  # Undefined, return neutral
        
        similarity = np.dot(a, b) / (norm_a * norm_b)
        return 1.0 - similarity
    
    def _euclidean_distance(self, a: np.ndarray, b: np.ndarray) -> float:
        """Compute Euclidean distance."""
        return float(np.linalg.norm(a - b))
    
    def _mahalanobis_distance(
        self,
        x: np.ndarray,
        mu: np.ndarray,
        cov_inv: np.ndarray
    ) -> float:
        """Compute Mahalanobis distance.
        
        D = sqrt((x - mu)^T * Σ^{-1} * (x - mu))
        """
        diff = x - mu
        return float(np.sqrt(diff.T @ cov_inv @ diff))
    
    def _normalize_cosine(self, distance: float) -> float:
        """Normalize cosine distance to [0, 1] anomaly score."""
        low = self.config.cosine_threshold_low
        high = self.config.cosine_threshold_high
        low_w = self.config.norm_low_weight
        high_w = self.config.norm_high_weight

        if distance <= low:
            return distance / low * low_w
        elif distance >= high:
            return 1.0
        else:
            # Linear interpolation in the middle range
            ratio = (distance - low) / (high - low)
            return low_w + ratio * high_w
    
    def _normalize_euclidean(self, distance: float) -> float:
        """Normalize Euclidean distance to [0, 1] anomaly score."""
        low = self.config.euclidean_threshold_low
        high = self.config.euclidean_threshold_high
        low_w = self.config.norm_low_weight
        high_w = self.config.norm_high_weight

        if distance <= low:
            return distance / low * low_w
        elif distance >= high:
            return 1.0
        else:
            ratio = (distance - low) / (high - low)
            return low_w + ratio * high_w
    
    def _normalize_mahalanobis(self, distance: float) -> float:
        """Normalize Mahalanobis distance to [0, 1] anomaly score."""
        low = self.config.mahal_threshold_low
        high = self.config.mahal_threshold_high
        low_w = self.config.norm_low_weight
        high_w = self.config.norm_high_weight

        if distance <= low:
            return distance / low * low_w
        elif distance >= high:
            return 1.0
        else:
            ratio = (distance - low) / (high - low)
            return low_w + ratio * high_w
    
    def _identify_deviations(
        self,
        current: np.ndarray,
        centroid: np.ndarray,
        anomaly_score: float
    ) -> list[str]:
        """Identify which features deviate most from baseline.
        
        Args:
            current: Current session embedding
            centroid: Profile centroid
            anomaly_score: Overall anomaly score
            
        Returns:
            List of human-readable deviation explanations
        """
        deviations = []
        
        if anomaly_score < self.config.anomaly_low:
            return []  # No significant deviations
        
        # Compare feature-wise differences
        diff = np.abs(current - centroid)
        
        # Feature indices (matching SessionEmbedder)
        # 0-1: hour sin/cos, 2-3: day sin/cos
        # 4-6: device type, 7-10: auth method
        # 11-12: lat/lon, 13-14: VPN/Tor, 15: time since last
        
        # Time deviation (combine hour features)
        time_diff = np.sqrt(diff[0]**2 + diff[1]**2)
        if time_diff > self.config.time_diff_thresh:
            deviations.append("login_time_differs_from_usual")
        
        # Day of week deviation
        day_diff = np.sqrt(diff[2]**2 + diff[3]**2)
        if day_diff > self.config.day_diff_thresh:
            deviations.append("login_day_differs_from_usual")
        
        # Device type deviation
        device_diff = np.max(diff[4:7])
        if device_diff > self.config.device_diff_thresh:
            deviations.append("different_device_type_than_usual")
        
        # Auth method deviation
        auth_diff = np.max(diff[7:11])
        if auth_diff > self.config.auth_diff_thresh:
            deviations.append("different_auth_method_than_usual")
        
        # Location deviation
        loc_diff = np.sqrt(diff[11]**2 + diff[12]**2)
        if loc_diff > self.config.loc_diff_thresh:
            deviations.append("login_location_differs_from_usual")
        
        # VPN/Tor deviation
        if diff[13] > self.config.vpn_thresh:
            deviations.append("unusual_vpn_usage")
        if diff[14] > self.config.tor_thresh:
            deviations.append("unusual_tor_usage")
        
        # Time since last login deviation
        if diff[15] > self.config.gap_thresh:
            deviations.append("unusual_gap_between_logins")
        
        # If high anomaly but no specific deviations identified
        if not deviations and anomaly_score >= self.config.fallback_anomaly:
            deviations.append("overall_behavioral_pattern_differs_significantly")
        
        return deviations
