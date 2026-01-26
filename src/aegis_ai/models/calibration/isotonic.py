"""Isotonic regression calibration for probability estimates.

Isotonic regression is preferred for fraud models because:
- Non-parametric: doesn't assume logistic relationship
- Monotonic: preserves ranking of predictions
- Robust: handles miscalibrated models well
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import pickle

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss, log_loss


@dataclass
class CalibrationMetrics:
    """Metrics for evaluating probability calibration.
    
    Attributes:
        brier_score: Brier score (lower is better, 0 is perfect)
        log_loss: Logarithmic loss (lower is better)
        ece: Expected Calibration Error
        mce: Maximum Calibration Error
        reliability_diagram: Tuple of (mean_predicted, fraction_positives, counts)
    """
    brier_score: float
    log_loss: float
    ece: float
    mce: float
    reliability_diagram: tuple[np.ndarray, np.ndarray, np.ndarray]


def calibration_curve(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute calibration curve (reliability diagram data).
    
    Args:
        y_true: True binary labels
        y_prob: Predicted probabilities
        n_bins: Number of bins
        
    Returns:
        Tuple of (mean_predicted_value, fraction_of_positives, bin_counts)
    """
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    bin_indices = np.digitize(y_prob, bin_boundaries[1:-1])
    
    mean_predicted = np.zeros(n_bins)
    fraction_positives = np.zeros(n_bins)
    bin_counts = np.zeros(n_bins, dtype=int)
    
    for i in range(n_bins):
        mask = bin_indices == i
        bin_counts[i] = mask.sum()
        
        if bin_counts[i] > 0:
            mean_predicted[i] = y_prob[mask].mean()
            fraction_positives[i] = y_true[mask].mean()
    
    return mean_predicted, fraction_positives, bin_counts


class IsotonicCalibrator:
    """Isotonic regression calibrator for probability estimates.
    
    Fits a non-parametric monotonic function to map raw model
    outputs to calibrated probabilities.
    """
    
    def __init__(self, clip_output: bool = True):
        """Initialize calibrator.
        
        Args:
            clip_output: Whether to clip outputs to [0, 1]
        """
        self.clip_output = clip_output
        self._calibrator: Optional[IsotonicRegression] = None
        self._is_fitted = False
    
    @property
    def is_fitted(self) -> bool:
        """Check if calibrator has been fitted."""
        return self._is_fitted
    
    def fit(
        self,
        y_prob: np.ndarray,
        y_true: np.ndarray
    ) -> "IsotonicCalibrator":
        """Fit calibrator on predictions and true labels.
        
        Args:
            y_prob: Predicted probabilities from uncalibrated model
            y_true: True binary labels
            
        Returns:
            Self for method chaining
        """
        self._calibrator = IsotonicRegression(
            y_min=0.0 if self.clip_output else None,
            y_max=1.0 if self.clip_output else None,
            out_of_bounds='clip'
        )
        self._calibrator.fit(y_prob, y_true)
        self._is_fitted = True
        return self
    
    def calibrate(self, y_prob: np.ndarray) -> np.ndarray:
        """Calibrate probability estimates.
        
        Args:
            y_prob: Uncalibrated probabilities
            
        Returns:
            Calibrated probabilities
        """
        if not self._is_fitted:
            raise RuntimeError("Calibrator must be fitted before use")
        
        calibrated = self._calibrator.predict(y_prob)
        
        if self.clip_output:
            calibrated = np.clip(calibrated, 0.0, 1.0)
        
        return calibrated
    
    def calibrate_single(self, prob: float) -> float:
        """Calibrate a single probability.
        
        Args:
            prob: Single uncalibrated probability
            
        Returns:
            Calibrated probability
        """
        return float(self.calibrate(np.array([prob]))[0])
    
    def evaluate(
        self,
        y_prob: np.ndarray,
        y_true: np.ndarray,
        n_bins: int = 10
    ) -> CalibrationMetrics:
        """Evaluate calibration quality.
        
        Args:
            y_prob: Predicted probabilities (before calibration)
            y_true: True binary labels
            n_bins: Number of bins for ECE/reliability diagram
            
        Returns:
            CalibrationMetrics with various scores
        """
        # Calibrate if fitted, otherwise evaluate raw
        if self._is_fitted:
            y_calibrated = self.calibrate(y_prob)
        else:
            y_calibrated = y_prob
        
        # Brier score
        brier = brier_score_loss(y_true, y_calibrated)
        
        # Log loss (with clipping to avoid inf)
        y_clipped = np.clip(y_calibrated, 1e-15, 1 - 1e-15)
        logloss = log_loss(y_true, y_clipped)
        
        # Calibration curve
        mean_pred, frac_pos, counts = calibration_curve(
            y_true, y_calibrated, n_bins
        )
        
        # Expected Calibration Error (ECE)
        total_samples = counts.sum()
        ece = 0.0
        mce = 0.0
        for i in range(n_bins):
            if counts[i] > 0:
                bin_error = abs(mean_pred[i] - frac_pos[i])
                ece += (counts[i] / total_samples) * bin_error
                mce = max(mce, bin_error)
        
        return CalibrationMetrics(
            brier_score=brier,
            log_loss=logloss,
            ece=ece,
            mce=mce,
            reliability_diagram=(mean_pred, frac_pos, counts),
        )
    
    def save(self, path: Path) -> None:
        """Save calibrator to disk.
        
        Args:
            path: Path to save file
        """
        if not self._is_fitted:
            raise RuntimeError("Cannot save unfitted calibrator")
        
        with open(path, "wb") as f:
            pickle.dump(self._calibrator, f)
    
    def load(self, path: Path) -> "IsotonicCalibrator":
        """Load calibrator from disk.
        
        Args:
            path: Path to saved file
            
        Returns:
            Self for method chaining
        """
        with open(path, "rb") as f:
            self._calibrator = pickle.load(f)
        self._is_fitted = True
        return self
