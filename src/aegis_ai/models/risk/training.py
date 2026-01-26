"""Model training utilities for risk scoring.

Provides functions to train and evaluate GBDT risk models
on fraud detection datasets.
"""

from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass

import numpy as np
from sklearn.model_selection import train_test_split

from src.aegis_ai.models.risk import (
    GBDTRiskModel,
    RiskModelConfig,
    FeatureExtractor,
    FeatureConfig,
)
from src.aegis_ai.models.risk.base import ModelType
from src.aegis_ai.models.calibration import IsotonicCalibrator, CalibrationMetrics


@dataclass
class TrainingConfig:
    """Configuration for model training.
    
    Attributes:
        model_type: XGBoost or LightGBM
        test_size: Fraction of data for testing
        calibration_size: Fraction of training data for calibration
        random_state: Random seed for reproducibility
        early_stopping_rounds: Rounds for early stopping (0 to disable)
    """
    model_type: ModelType = ModelType.XGBOOST
    test_size: float = 0.2
    calibration_size: float = 0.15
    random_state: int = 42
    early_stopping_rounds: int = 10


@dataclass
class TrainingResult:
    """Result from model training.
    
    Attributes:
        model: Trained risk model
        calibrator: Fitted calibrator
        test_metrics: Metrics on test set
        calibration_metrics: Calibration quality metrics
        feature_names: List of feature names
    """
    model: GBDTRiskModel
    calibrator: IsotonicCalibrator
    test_metrics: dict
    calibration_metrics: CalibrationMetrics
    feature_names: list[str]


def train_risk_model(
    X: np.ndarray,
    y: np.ndarray,
    feature_names: list[str],
    config: Optional[TrainingConfig] = None,
    model_params: Optional[dict] = None
) -> TrainingResult:
    """Train a GBDT risk model with calibration.
    
    Args:
        X: Feature matrix (n_samples, n_features)
        y: Binary labels (0 = legitimate, 1 = fraud)
        feature_names: List of feature names
        config: Training configuration
        model_params: Optional custom model hyperparameters
        
    Returns:
        TrainingResult with trained model and metrics
    """
    config = config or TrainingConfig()
    
    # Split data: train / calibration / test
    X_train_full, X_test, y_train_full, y_test = train_test_split(
        X, y,
        test_size=config.test_size,
        random_state=config.random_state,
        stratify=y
    )
    
    X_train, X_calib, y_train, y_calib = train_test_split(
        X_train_full, y_train_full,
        test_size=config.calibration_size,
        random_state=config.random_state,
        stratify=y_train_full
    )
    
    # Create model
    model_config = RiskModelConfig(
        model_type=config.model_type,
        feature_names=feature_names,
        calibration_enabled=True,
    )
    model = GBDTRiskModel(model_config, model_params)
    
    # Train with calibration
    model.fit_with_calibration(
        X=X_train,
        y=y_train,
        X_calib=X_calib,
        y_calib=y_calib,
        eval_set=(X_test, y_test)
    )
    
    # Evaluate on test set
    from sklearn.metrics import (
        roc_auc_score,
        precision_score,
        recall_score,
        f1_score,
    )
    
    predictions = model.predict_batch(X_test)
    y_pred_prob = np.array([p.score for p in predictions])
    y_pred = (y_pred_prob >= 0.5).astype(int)
    
    test_metrics = {
        "auc_roc": roc_auc_score(y_test, y_pred_prob),
        "precision": precision_score(y_test, y_pred),
        "recall": recall_score(y_test, y_pred),
        "f1": f1_score(y_test, y_pred),
    }
    
    # Evaluate calibration
    calibrator = IsotonicCalibrator()
    calibration_metrics = calibrator.evaluate(y_pred_prob, y_test)
    
    return TrainingResult(
        model=model,
        calibrator=calibrator,
        test_metrics=test_metrics,
        calibration_metrics=calibration_metrics,
        feature_names=feature_names,
    )


def create_training_data_from_events(
    login_events: list,
    sessions: list,
    devices: list,
    labels: np.ndarray,
    feature_config: Optional[FeatureConfig] = None
) -> Tuple[np.ndarray, np.ndarray, list[str]]:
    """Create training data from schema objects.
    
    Args:
        login_events: List of LoginEvent objects
        sessions: List of Session objects
        devices: List of Device objects
        labels: Binary labels (0 = legit, 1 = fraud)
        feature_config: Optional feature extraction config
        
    Returns:
        Tuple of (X, y, feature_names)
    """
    extractor = FeatureExtractor(feature_config)
    X = extractor.extract_batch(login_events, sessions, devices)
    return X, labels, extractor.feature_names


def save_trained_model(
    result: TrainingResult,
    output_dir: Path,
    save_metrics: bool = True
) -> None:
    """Save trained model and artifacts.
    
    Args:
        result: Training result
        output_dir: Directory to save to
        save_metrics: Whether to save metrics as JSON
    """
    import json
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save model
    result.model.save(output_dir / "model")
    
    # Save calibrator
    result.calibrator.save(output_dir / "calibrator.pkl")
    
    # Save metrics
    if save_metrics:
        metrics = {
            "test_metrics": result.test_metrics,
            "calibration": {
                "brier_score": result.calibration_metrics.brier_score,
                "log_loss": result.calibration_metrics.log_loss,
                "ece": result.calibration_metrics.ece,
                "mce": result.calibration_metrics.mce,
            },
            "feature_names": result.feature_names,
        }
        with open(output_dir / "metrics.json", "w") as f:
            json.dump(metrics, f, indent=2)
