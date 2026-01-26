"""GBDT-based risk scoring model.

Implements XGBoost and LightGBM models for fraud risk scoring.
Replaces heuristic logic with calibrated ML predictions.

Key design decisions:
- Binary classification with probability output
- Optional isotonic calibration for probability estimates
- SHAP support is mandatory (via tree explainer)
- Fallback to heuristic on model failure
"""

from pathlib import Path
from typing import Any, Optional
import json
import pickle

import numpy as np

from src.aegis_ai.models.risk.base import (
    RiskModel,
    RiskModelConfig,
    RiskPrediction,
    ModelType,
)


class GBDTRiskModel(RiskModel):
    """Gradient Boosted Decision Tree risk scoring model.
    
    Supports both XGBoost and LightGBM backends.
    Outputs calibrated probabilities in [0, 1] range.
    """
    
    # Default hyperparameters (tuned for fraud detection)
    DEFAULT_XGBOOST_PARAMS = {
        "objective": "binary:logistic",
        "eval_metric": "auc",
        "max_depth": 6,
        "learning_rate": 0.1,
        "n_estimators": 100,
        "min_child_weight": 1,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "reg_alpha": 0.1,
        "reg_lambda": 1.0,
        "random_state": 42,
    }
    
    DEFAULT_LIGHTGBM_PARAMS = {
        "objective": "binary",
        "metric": "auc",
        "boosting_type": "gbdt",
        "max_depth": 6,
        "learning_rate": 0.1,
        "n_estimators": 100,
        "min_child_samples": 20,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "reg_alpha": 0.1,
        "reg_lambda": 1.0,
        "random_state": 42,
        "verbose": -1,
    }
    
    def __init__(
        self,
        config: RiskModelConfig,
        model_params: Optional[dict] = None
    ):
        """Initialize GBDT risk model.
        
        Args:
            config: Model configuration
            model_params: Optional custom model parameters
        """
        super().__init__(config)
        self.model_params = model_params or self._get_default_params()
        self._calibrator: Optional[Any] = None
    
    def _get_default_params(self) -> dict:
        """Get default parameters based on model type."""
        if self.config.model_type == ModelType.XGBOOST:
            return self.DEFAULT_XGBOOST_PARAMS.copy()
        else:
            return self.DEFAULT_LIGHTGBM_PARAMS.copy()
    
    def _create_model(self) -> Any:
        """Create underlying model instance."""
        if self.config.model_type == ModelType.XGBOOST:
            import xgboost as xgb
            return xgb.XGBClassifier(**self.model_params)
        else:
            import lightgbm as lgb
            return lgb.LGBMClassifier(**self.model_params)
    
    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        eval_set: Optional[tuple[np.ndarray, np.ndarray]] = None
    ) -> "GBDTRiskModel":
        """Train the GBDT model.
        
        Args:
            X: Feature matrix (n_samples, n_features)
            y: Binary labels (0 = legitimate, 1 = fraud)
            eval_set: Optional validation set (X_val, y_val)
            
        Returns:
            Self for method chaining
        """
        self._model = self._create_model()
        
        fit_kwargs = {}
        if eval_set is not None:
            X_val, y_val = eval_set
            fit_kwargs["eval_set"] = [(X_val, y_val)]
        
        self._model.fit(X, y, **fit_kwargs)
        self._is_fitted = True
        
        return self
    
    def fit_with_calibration(
        self,
        X: np.ndarray,
        y: np.ndarray,
        X_calib: np.ndarray,
        y_calib: np.ndarray,
        eval_set: Optional[tuple[np.ndarray, np.ndarray]] = None
    ) -> "GBDTRiskModel":
        """Train model and fit calibrator.
        
        Args:
            X: Training features
            y: Training labels
            X_calib: Calibration features (held-out set)
            y_calib: Calibration labels
            eval_set: Optional validation set
            
        Returns:
            Self for method chaining
        """
        from sklearn.isotonic import IsotonicRegression
        
        # First fit the model
        self.fit(X, y, eval_set)
        
        # Get raw predictions on calibration set
        raw_probs = self._model.predict_proba(X_calib)[:, 1]
        
        # Fit isotonic calibrator
        self._calibrator = IsotonicRegression(
            y_min=0.0,
            y_max=1.0,
            out_of_bounds='clip'
        )
        self._calibrator.fit(raw_probs, y_calib)
        
        return self
    
    def predict(self, features: np.ndarray) -> RiskPrediction:
        """Predict risk score for a single sample.
        
        Args:
            features: 1D array of feature values
            
        Returns:
            RiskPrediction with raw and calibrated scores
        """
        if not self._is_fitted:
            raise RuntimeError("Model must be fitted before prediction")
        
        # Reshape for single sample prediction
        X = features.reshape(1, -1) if features.ndim == 1 else features[:1]
        
        # Get raw probability from model
        raw_prob = float(self._model.predict_proba(X)[0, 1])
        
        # Apply calibration if available
        if self._calibrator is not None and self.config.calibration_enabled:
            calibrated_prob = float(self._calibrator.predict([raw_prob])[0])
        else:
            calibrated_prob = raw_prob
        
        # Clamp to bounds
        calibrated_prob = self._clamp_score(calibrated_prob)
        
        return RiskPrediction(
            raw_score=raw_prob,
            calibrated_score=calibrated_prob,
            feature_values=features,
            feature_names=self.config.feature_names,
        )
    
    def predict_batch(self, features: np.ndarray) -> list[RiskPrediction]:
        """Predict risk scores for multiple samples.
        
        Args:
            features: 2D array (n_samples, n_features)
            
        Returns:
            List of RiskPrediction objects
        """
        if not self._is_fitted:
            raise RuntimeError("Model must be fitted before prediction")
        
        # Get raw probabilities
        raw_probs = self._model.predict_proba(features)[:, 1]
        
        # Apply calibration if available
        if self._calibrator is not None and self.config.calibration_enabled:
            calibrated_probs = self._calibrator.predict(raw_probs)
        else:
            calibrated_probs = raw_probs
        
        # Build predictions
        predictions = []
        for i in range(len(features)):
            calibrated = self._clamp_score(float(calibrated_probs[i]))
            predictions.append(
                RiskPrediction(
                    raw_score=float(raw_probs[i]),
                    calibrated_score=calibrated,
                    feature_values=features[i],
                    feature_names=self.config.feature_names,
                )
            )
        
        return predictions
    
    def get_native_model(self) -> Any:
        """Get the underlying XGBoost/LightGBM model.
        
        Useful for SHAP explanations and native feature importance.
        """
        return self._model
    
    def save(self, path: Path) -> None:
        """Save model to disk.
        
        Saves model, calibrator, and config as a bundle.
        
        Args:
            path: Path to save (directory will be created)
        """
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        
        # Save model
        model_file = path / "model.pkl"
        with open(model_file, "wb") as f:
            pickle.dump(self._model, f)
        
        # Save calibrator if present
        if self._calibrator is not None:
            calib_file = path / "calibrator.pkl"
            with open(calib_file, "wb") as f:
                pickle.dump(self._calibrator, f)
        
        # Save config and metadata
        metadata = {
            "model_type": self.config.model_type.value,
            "feature_names": self.config.feature_names,
            "calibration_enabled": self.config.calibration_enabled,
            "has_calibrator": self._calibrator is not None,
            "model_params": self.model_params,
        }
        meta_file = path / "metadata.json"
        with open(meta_file, "w") as f:
            json.dump(metadata, f, indent=2)
    
    def load(self, path: Path) -> "GBDTRiskModel":
        """Load model from disk.
        
        Args:
            path: Path to model directory
            
        Returns:
            Self for method chaining
        """
        path = Path(path)
        
        # Load metadata
        meta_file = path / "metadata.json"
        with open(meta_file, "r") as f:
            metadata = json.load(f)
        
        # Update config from metadata
        self.config.model_type = ModelType(metadata["model_type"])
        self.config.feature_names = metadata["feature_names"]
        self.config.calibration_enabled = metadata["calibration_enabled"]
        self.model_params = metadata.get("model_params", self._get_default_params())
        
        # Load model
        model_file = path / "model.pkl"
        with open(model_file, "rb") as f:
            self._model = pickle.load(f)
        
        # Load calibrator if present
        if metadata.get("has_calibrator", False):
            calib_file = path / "calibrator.pkl"
            if calib_file.exists():
                with open(calib_file, "rb") as f:
                    self._calibrator = pickle.load(f)
        
        self._is_fitted = True
        return self
