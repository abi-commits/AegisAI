"""Native tree-based explainability using XGBoost/LightGBM.

This module extracts feature importance and decision paths from tree models
without external dependencies like SHAP. Perfect for regulatory compliance.
"""

from dataclasses import dataclass
from typing import Dict, List, Any, Tuple
import numpy as np


@dataclass
class FeatureImportance:
    """Feature importance from tree model."""
    feature_name: str
    importance_score: float
    importance_type: str  # 'gain', 'cover', 'frequency'
    

@dataclass
class DecisionPath:
    """Decision path for a single prediction."""
    features_used: List[str]
    feature_contributions: Dict[str, float]
    leaf_value: float
    

class TreeExplainer:
    """Extracts native tree-based explanations from XGBoost/LightGBM models."""
    
    def __init__(self, model, feature_names: List[str]):
        """
        Initialize tree explainer.
        
        Args:
            model: XGBoost or LightGBM model
            feature_names: List of feature names in order
        """
        self.model = model
        self.feature_names = feature_names
    
    def get_feature_importance(
        self,
        importance_type: str = 'gain'
    ) -> List[FeatureImportance]:
        """
        Extract feature importance from model.
        
        Args:
            importance_type: 'gain' (default), 'cover', or 'frequency'
            
        Returns:
            Sorted list of FeatureImportance objects
        """
        raise NotImplementedError
    
    def get_decision_path(
        self,
        sample: np.ndarray,
        sample_id: int = 0
    ) -> DecisionPath:
        """
        Extract decision path for a single sample.
        
        Args:
            sample: Input features (1D or 2D array)
            sample_id: Which sample if 2D array
            
        Returns:
            DecisionPath with features and contributions
        """
        raise NotImplementedError
    
    def get_top_factors(self, n_factors: int = 5) -> List[str]:
        """Get top N feature importance factors."""
        raise NotImplementedError


class XGBoostExplainer(TreeExplainer):
    """Explainer for XGBoost models."""
    
    def get_feature_importance(
        self,
        importance_type: str = 'gain'
    ) -> List[FeatureImportance]:
        """Extract XGBoost feature importance."""
        # XGBoost's get_score() returns feature importances
        scores = self.model.get_booster().get_score(importance_type=importance_type)
        
        importances = []
        for feature, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
            importances.append(
                FeatureImportance(
                    feature_name=feature,
                    importance_score=float(score),
                    importance_type=importance_type
                )
            )
        return importances


class LightGBMExplainer(TreeExplainer):
    """Explainer for LightGBM models."""
    
    def get_feature_importance(
        self,
        importance_type: str = 'gain'
    ) -> List[FeatureImportance]:
        """Extract LightGBM feature importance."""
        # LightGBM's feature_importance() method
        importances_array = self.model.feature_importance(importance_type=importance_type)
        
        importances = []
        for idx, score in enumerate(importances_array):
            if idx < len(self.feature_names):
                importances.append(
                    FeatureImportance(
                        feature_name=self.feature_names[idx],
                        importance_score=float(score),
                        importance_type=importance_type
                    )
                )
        
        # Sort by importance
        importances.sort(key=lambda x: x.importance_score, reverse=True)
        return importances
