"""Base classes for risk scoring models.

Defines the interface that all risk models must implement.
The model replaces the score, not the decision logic.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import numpy as np


class ModelType(str, Enum):
    """Supported model types."""
    XGBOOST = "xgboost"
    LIGHTGBM = "lightgbm"


@dataclass
class RiskModelConfig:
    """Configuration for risk scoring models.
    
    Attributes:
        model_type: Type of model (xgboost or lightgbm)
        model_path: Path to saved model file (optional for training)
        feature_names: List of feature names in order
        calibration_enabled: Whether to apply calibration to outputs
        calibration_path: Path to calibration model
        fallback_to_heuristic: If True, fall back to heuristic on model failure
        score_clamp_min: Minimum score value (clamping)
        score_clamp_max: Maximum score value (clamping)
    """
    model_type: ModelType = ModelType.XGBOOST
    model_path: Optional[Path] = None
    feature_names: list[str] = field(default_factory=list)
    calibration_enabled: bool = True
    calibration_path: Optional[Path] = None
    fallback_to_heuristic: bool = True
    score_clamp_min: float = 0.0
    score_clamp_max: float = 1.0


@dataclass
class RiskPrediction:
    """Output from a risk model prediction.
    
    Attributes:
        raw_score: Raw model output (before calibration)
        calibrated_score: Calibrated probability (0-1)
        feature_values: Feature values used for prediction
        feature_names: Names of features
    """
    raw_score: float
    calibrated_score: float
    feature_values: np.ndarray
    feature_names: list[str]
    
    @property
    def score(self) -> float:
        """Return the calibrated score (the one we use)."""
        return self.calibrated_score


class RiskModel(ABC):
    """Abstract base class for risk scoring models.
    
    All risk models must implement:
    - predict(): Score a single sample
    - predict_batch(): Score multiple samples
    - save(): Persist the model
    - load(): Load a persisted model
    
    The model only provides scores - no decisions.
    """
    
    def __init__(self, config: RiskModelConfig):
        """Initialize the risk model.
        
        Args:
            config: Model configuration
        """
        self.config = config
        self._model: Any = None
        self._is_fitted = False
    
    @property
    def is_fitted(self) -> bool:
        """Check if model has been trained or loaded."""
        return self._is_fitted
    
    @abstractmethod
    def predict(self, features: np.ndarray) -> RiskPrediction:
        """Predict risk score for a single sample.
        
        Args:
            features: 1D array of feature values
            
        Returns:
            RiskPrediction with raw and calibrated scores
        """
        pass
    
    @abstractmethod
    def predict_batch(self, features: np.ndarray) -> list[RiskPrediction]:
        """Predict risk scores for multiple samples.
        
        Args:
            features: 2D array of feature values (n_samples, n_features)
            
        Returns:
            List of RiskPrediction objects
        """
        pass
    
    @abstractmethod
    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        eval_set: Optional[tuple[np.ndarray, np.ndarray]] = None
    ) -> "RiskModel":
        """Train the model on labeled data.
        
        Args:
            X: Feature matrix (n_samples, n_features)
            y: Binary labels (0 = legitimate, 1 = fraud)
            eval_set: Optional validation set (X_val, y_val)
            
        Returns:
            Self for method chaining
        """
        pass
    
    @abstractmethod
    def save(self, path: Path) -> None:
        """Save model to disk.
        
        Args:
            path: Path to save model file
        """
        pass
    
    @abstractmethod
    def load(self, path: Path) -> "RiskModel":
        """Load model from disk.
        
        Args:
            path: Path to model file
            
        Returns:
            Self for method chaining
        """
        pass
    
    def _clamp_score(self, score: float) -> float:
        """Clamp score to configured bounds.
        
        Args:
            score: Raw or calibrated score
            
        Returns:
            Clamped score within [min, max]
        """
        return max(
            self.config.score_clamp_min,
            min(self.config.score_clamp_max, score)
        )
