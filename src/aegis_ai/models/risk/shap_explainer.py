"""SHAP explainability for risk models.

Provides model-agnostic and tree-native SHAP explanations.
SHAP support is non-negotiable for fraud detection models.

This module wraps SHAP to provide:
- Feature contribution explanations per prediction
- Global feature importance
- Risk factor extraction for agent output
"""

from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np


@dataclass
class SHAPExplanation:
    """SHAP explanation for a single prediction.
    
    Attributes:
        base_value: Expected model output (mean prediction)
        shap_values: SHAP values for each feature
        feature_values: Input feature values
        feature_names: Names of features
        prediction: Model prediction value
    """
    base_value: float
    shap_values: np.ndarray
    feature_values: np.ndarray
    feature_names: list[str]
    prediction: float
    
    def get_top_contributors(
        self,
        n: int = 5,
        min_contribution: float = 0.01
    ) -> list[tuple[str, float]]:
        """Get top N features contributing to the prediction.
        
        Args:
            n: Maximum number of features to return
            min_contribution: Minimum absolute SHAP value to include
            
        Returns:
            List of (feature_name, shap_value) tuples sorted by |shap_value|
        """
        # Pair features with their SHAP values
        contributions = list(zip(self.feature_names, self.shap_values))
        
        # Filter by minimum contribution
        contributions = [
            (name, val) for name, val in contributions
            if abs(val) >= min_contribution
        ]
        
        # Sort by absolute SHAP value (descending)
        contributions.sort(key=lambda x: abs(x[1]), reverse=True)
        
        return contributions[:n]
    
    def get_positive_contributors(
        self,
        n: int = 5,
        min_contribution: float = 0.01
    ) -> list[tuple[str, float]]:
        """Get features that increase the risk score.
        
        Args:
            n: Maximum number of features
            min_contribution: Minimum SHAP value
            
        Returns:
            List of (feature_name, shap_value) for risk-increasing features
        """
        contributions = [
            (name, val) for name, val in zip(self.feature_names, self.shap_values)
            if val >= min_contribution
        ]
        contributions.sort(key=lambda x: x[1], reverse=True)
        return contributions[:n]


@dataclass
class GlobalImportance:
    """Global feature importance from SHAP.
    
    Attributes:
        feature_names: Names of features
        importance_values: Mean absolute SHAP values
        importance_std: Standard deviation of SHAP values
    """
    feature_names: list[str]
    importance_values: np.ndarray
    importance_std: np.ndarray
    
    def get_ranked_features(self) -> list[tuple[str, float, float]]:
        """Get features ranked by importance.
        
        Returns:
            List of (name, mean_importance, std) tuples
        """
        ranked = list(zip(
            self.feature_names,
            self.importance_values,
            self.importance_std
        ))
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked


class SHAPExplainer:
    """SHAP-based model explainer for risk scoring models.
    
    Uses TreeExplainer for XGBoost/LightGBM (fast, exact).
    Falls back to KernelExplainer for other models.
    """
    
    def __init__(
        self,
        model: Any,
        feature_names: list[str],
        background_data: Optional[np.ndarray] = None
    ):
        """Initialize SHAP explainer.
        
        Args:
            model: Trained model (XGBoost, LightGBM, or sklearn)
            feature_names: List of feature names in order
            background_data: Background data for KernelExplainer (optional)
        """
        self.model = model
        self.feature_names = feature_names
        self.background_data = background_data
        self._explainer: Any = None
        self._is_tree_model = self._check_tree_model()
    
    def _check_tree_model(self) -> bool:
        """Check if model is a tree-based model."""
        model_type = type(self.model).__name__
        return model_type in (
            "XGBClassifier", "XGBRegressor",
            "LGBMClassifier", "LGBMRegressor",
            "GradientBoostingClassifier", "RandomForestClassifier",
        )
    
    def _get_explainer(self) -> Any:
        """Get or create SHAP explainer."""
        if self._explainer is not None:
            return self._explainer
        
        import shap
        
        if self._is_tree_model:
            # Fast, exact explanations for tree models
            self._explainer = shap.TreeExplainer(self.model)
        else:
            # Fallback for other models
            if self.background_data is None:
                raise ValueError(
                    "background_data required for non-tree models"
                )
            self._explainer = shap.KernelExplainer(
                self.model.predict_proba,
                self.background_data
            )
        
        return self._explainer
    
    def explain(self, features: np.ndarray) -> SHAPExplanation:
        """Generate SHAP explanation for a single prediction.
        
        Args:
            features: 1D array of feature values
            
        Returns:
            SHAPExplanation with feature contributions
        """
        explainer = self._get_explainer()
        
        # Reshape for single sample
        X = features.reshape(1, -1) if features.ndim == 1 else features[:1]
        
        # Get SHAP values
        shap_values = explainer.shap_values(X)
        
        # Handle multi-class output (use class 1 for binary)
        if isinstance(shap_values, list):
            shap_values = shap_values[1]  # Class 1 (fraud)
        
        # Get base value
        base_value = float(explainer.expected_value)
        if isinstance(explainer.expected_value, (list, np.ndarray)):
            base_value = float(explainer.expected_value[1])  # Class 1
        
        # Get prediction
        if hasattr(self.model, "predict_proba"):
            prediction = float(self.model.predict_proba(X)[0, 1])
        else:
            prediction = float(self.model.predict(X)[0])
        
        return SHAPExplanation(
            base_value=base_value,
            shap_values=shap_values.flatten(),
            feature_values=features.flatten(),
            feature_names=self.feature_names,
            prediction=prediction,
        )
    
    def explain_batch(self, features: np.ndarray) -> list[SHAPExplanation]:
        """Generate SHAP explanations for multiple predictions.
        
        Args:
            features: 2D array (n_samples, n_features)
            
        Returns:
            List of SHAPExplanation objects
        """
        explainer = self._get_explainer()
        
        # Get SHAP values for all samples
        shap_values = explainer.shap_values(features)
        
        # Handle multi-class output
        if isinstance(shap_values, list):
            shap_values = shap_values[1]
        
        # Get base value
        base_value = float(explainer.expected_value)
        if isinstance(explainer.expected_value, (list, np.ndarray)):
            base_value = float(explainer.expected_value[1])
        
        # Get predictions
        if hasattr(self.model, "predict_proba"):
            predictions = self.model.predict_proba(features)[:, 1]
        else:
            predictions = self.model.predict(features)
        
        # Build explanations
        explanations = []
        for i in range(len(features)):
            explanations.append(
                SHAPExplanation(
                    base_value=base_value,
                    shap_values=shap_values[i],
                    feature_values=features[i],
                    feature_names=self.feature_names,
                    prediction=float(predictions[i]),
                )
            )
        
        return explanations
    
    def global_importance(
        self,
        X: np.ndarray,
        max_samples: int = 1000
    ) -> GlobalImportance:
        """Calculate global feature importance using SHAP.
        
        Args:
            X: Feature matrix (samples to analyze)
            max_samples: Maximum samples to use
            
        Returns:
            GlobalImportance with mean absolute SHAP values
        """
        # Subsample if needed
        if len(X) > max_samples:
            indices = np.random.choice(len(X), max_samples, replace=False)
            X = X[indices]
        
        explainer = self._get_explainer()
        shap_values = explainer.shap_values(X)
        
        # Handle multi-class
        if isinstance(shap_values, list):
            shap_values = shap_values[1]
        
        # Calculate mean absolute SHAP values
        importance_values = np.abs(shap_values).mean(axis=0)
        importance_std = np.abs(shap_values).std(axis=0)
        
        return GlobalImportance(
            feature_names=self.feature_names,
            importance_values=importance_values,
            importance_std=importance_std,
        )
    
    def extract_risk_factors(
        self,
        explanation: SHAPExplanation,
        feature_to_factor_map: dict[str, str],
        n_factors: int = 5,
        min_contribution: float = 0.02
    ) -> list[str]:
        """Extract human-readable risk factors from SHAP explanation.
        
        Args:
            explanation: SHAP explanation
            feature_to_factor_map: Mapping from feature names to factor names
            n_factors: Maximum number of factors to return
            min_contribution: Minimum SHAP value to include
            
        Returns:
            List of risk factor strings
        """
        # Get positive contributors (risk-increasing features)
        contributors = explanation.get_positive_contributors(
            n=n_factors,
            min_contribution=min_contribution
        )
        
        # Map to human-readable factor names
        factors = []
        for feature_name, shap_value in contributors:
            factor_name = feature_to_factor_map.get(feature_name, feature_name)
            factors.append(factor_name)
        
        return factors
