"""Platt scaling calibration for probability estimates.

Platt scaling fits a logistic regression to transform raw model
outputs into well-calibrated probabilities.

Use cases:
- SVM outputs
- Any model with sigmoid-like miscalibration
- When you want smooth calibration curves
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import pickle

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss

from aegis_ai.models.calibration.isotonic import CalibrationMetrics, calibration_curve


class PlattCalibrator:
    """Platt scaling calibrator for probability estimates.
    
    Fits a logistic regression to map raw model outputs to
    calibrated probabilities. Assumes sigmoid-like miscalibration.
    """
    
    def __init__(self, clip_output: bool = True):
        """Initialize calibrator.
        
        Args:
            clip_output: Whether to clip outputs to [0, 1]
        """
        self.clip_output = clip_output
        self._calibrator: Optional[LogisticRegression] = None
        self._is_fitted = False
    
    @property
    def is_fitted(self) -> bool:
        """Check if calibrator has been fitted."""
        return self._is_fitted
    
    def fit(
        self,
        y_prob: np.ndarray,
        y_true: np.ndarray
    ) -> "PlattCalibrator":
        """Fit calibrator on predictions and true labels.
        
        Args:
            y_prob: Predicted probabilities from uncalibrated model
            y_true: True binary labels
            
        Returns:
            Self for method chaining
        """
        # Reshape for sklearn
        X = y_prob.reshape(-1, 1)
        
        self._calibrator = LogisticRegression(
            solver='lbfgs',
            max_iter=1000,
            C=1e10  # Weak regularization
        )
        self._calibrator.fit(X, y_true)
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
        
        X = y_prob.reshape(-1, 1)
        calibrated = self._calibrator.predict_proba(X)[:, 1]
        
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
    
    def load(self, path: Path) -> "PlattCalibrator":
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
