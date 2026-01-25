"""Detection Agent - identifies anomalous login behavior.

Uses native tree-based models (XGBoost/LightGBM) with built-in explainability.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any
from src.aegis_ai.models.explainability import RiskFactor


@dataclass
class DetectionOutput:
    """Output from Detection Agent."""
    risk_signal_score: float  # 0.0 to 1.0
    risk_factors: List[RiskFactor]
    feature_importance: Dict[str, float]  # Top features from model
    explanation: str = ""
    

class DetectionAgent:
    """Detection Agent Contract.
    
    Input: LoginEvent + session features
    Output: risk_signal_score, risk_factors, feature_importance
    Constraint: Cannot block or decide
    
    Uses native tree explainability (no external dependencies needed).
    """
    
    def __init__(self, model=None, explainer=None):
        """
        Initialize Detection Agent.
        
        Args:
            model: XGBoost or LightGBM model for risk scoring
            explainer: TreeExplainer instance for native explanations
        """
        self.model = model
        self.explainer = explainer
    
    def analyze(self, login_event: dict, session_features: dict) -> DetectionOutput:
        """
        Analyze login event and return risk signals with native explanations.
        
        Args:
            login_event: LoginEvent data
            session_features: Processed session features (as dict or array)
            
        Returns:
            DetectionOutput with risk score, factors, and importances
        """
        raise NotImplementedError
    
    def _extract_risk_factors(
        self,
        feature_importance: Dict[str, float],
        threshold: float = 0.05
    ) -> List[RiskFactor]:
        """
        Extract risk factors from model feature importance.
        
        Maps top features to RiskFactor enum based on feature names.
        
        Args:
            feature_importance: Dict of feature names to importance scores
            threshold: Minimum importance to include
            
        Returns:
            List of RiskFactor enums sorted by importance
        """
        # Feature name to RiskFactor mapping
        feature_to_factor = {
            'is_new_device': RiskFactor.NEW_DEVICE,
            'location_distance': RiskFactor.UNUSUAL_LOCATION,
            'login_velocity': RiskFactor.HIGH_LOGIN_VELOCITY,
            'failed_attempts': RiskFactor.FAILED_ATTEMPTS,
            'impossible_travel': RiskFactor.IMPOSSIBLE_TRAVEL,
            'is_new_ip': RiskFactor.NEW_IP,
            'behavior_deviation': RiskFactor.BEHAVIOR_DEVIATION,
            'network_risk': RiskFactor.NETWORK_ANOMALY,
            'unusual_time': RiskFactor.TIME_ANOMALY,
            'device_mismatch': RiskFactor.DEVICE_MISMATCH,
        }
        
        factors = []
        for feature, importance in sorted(
            feature_importance.items(),
            key=lambda x: x[1],
            reverse=True
        ):
            if importance >= threshold:
                if feature in feature_to_factor:
                    factors.append(feature_to_factor[feature])
        
        return factors
