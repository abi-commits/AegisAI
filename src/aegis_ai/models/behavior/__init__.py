"""Behavioral profiling models.

Profile-based anomaly detection that measures distance
from a user's historical behavioral centroid.

Key insight: No fraud labels required.
This answers: "Does this look like the same human?"
"""

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
from src.aegis_ai.models.behavior.profiler import BehavioralProfiler

__all__ = [
    "BehavioralProfile",
    "ProfileConfig",
    "SessionEmbedding",
    "DistanceCalculator",
    "DistanceMethod",
    "AnomalyScore",
    "BehavioralProfiler",
]
