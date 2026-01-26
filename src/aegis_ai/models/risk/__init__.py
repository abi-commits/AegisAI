"""Risk scoring models for detection.

ML-based risk scoring that replaces heuristic logic while
maintaining the same inputs, outputs, and decision boundaries.
"""

from src.aegis_ai.models.risk.base import RiskModel, RiskModelConfig, RiskPrediction, ModelType
from src.aegis_ai.models.risk.feature_extractor import FeatureExtractor, FeatureConfig, FEATURE_NAMES
from src.aegis_ai.models.risk.gbdt_model import GBDTRiskModel
from src.aegis_ai.models.risk.shap_explainer import SHAPExplainer, SHAPExplanation, GlobalImportance

__all__ = [
    "RiskModel",
    "RiskModelConfig",
    "RiskPrediction",
    "ModelType",
    "FeatureExtractor",
    "FeatureConfig",
    "FEATURE_NAMES",
    "GBDTRiskModel",
    "SHAPExplainer",
    "SHAPExplanation",
    "GlobalImportance",
]
