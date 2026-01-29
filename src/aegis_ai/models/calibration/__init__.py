"""Model calibration for risk scoring.

Provides probability calibration to ensure model outputs
are well-calibrated probabilities, not just rankings.

Phase 4 additions:
- PlattCalibrator: Logistic regression-based calibration
- ConfidenceCalibrator: Disagreement-aware confidence adjustment
"""

from aegis_ai.models.calibration.isotonic import (
    IsotonicCalibrator,
    CalibrationMetrics,
    calibration_curve,
)
from aegis_ai.models.calibration.platt import PlattCalibrator
from aegis_ai.models.calibration.confidence import (
    ConfidenceCalibrator,
    CalibrationResult,
    EscalationMetrics,
)

__all__ = [
    # Isotonic calibration
    "IsotonicCalibrator",
    "CalibrationMetrics",
    "calibration_curve",
    # Platt scaling
    "PlattCalibrator",
    # Confidence calibration (Phase 4)
    "ConfidenceCalibrator",
    "CalibrationResult",
    "EscalationMetrics",
]
