"""Configuration constants for behavioral model.

Centralizes thresholds and embedding-related constants so they
can be tuned or overridden in one place.
"""
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class BehaviorConfig:
    # Embedding
    embedding_dim: int = 16
    device_types: Dict[str, int] = field(default_factory=lambda: {"desktop": 0, "mobile": 1, "tablet": 2})
    auth_methods: Dict[str, int] = field(default_factory=lambda: {"password": 0, "mfa": 1, "sso": 2, "biometric": 3})
    default_device: str = "desktop"
    hours_in_day: int = 24
    days_in_week: int = 7
    location_norm_lat: float = 90.0
    location_norm_lon: float = 180.0
    time_norm_div: float = 7.0  # divisor used to normalize log(time_since_last)
    unknown_time_value: float = 0.5

    # Distance thresholds
    cosine_threshold_low: float = 0.1
    cosine_threshold_high: float = 0.5
    mahal_threshold_low: float = 2.0
    mahal_threshold_high: float = 4.0
    euclidean_threshold_low: float = 1.0
    euclidean_threshold_high: float = 3.0

    # Numerical guards
    epsilon: float = 1e-10
    covariance_regularization: float = 1e-4

    # Normalization weights
    norm_low_weight: float = 0.3
    norm_high_weight: float = 0.7

    # Deviation detection cutoffs
    anomaly_low: float = 0.3
    time_diff_thresh: float = 0.5
    day_diff_thresh: float = 0.5
    device_diff_thresh: float = 0.5
    auth_diff_thresh: float = 0.5
    loc_diff_thresh: float = 0.3
    vpn_thresh: float = 0.5
    tor_thresh: float = 0.5
    gap_thresh: float = 0.5
    fallback_anomaly: float = 0.5
