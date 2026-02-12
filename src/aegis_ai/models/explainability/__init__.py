"""Explainability module - feature attribution without SHAP."""

from aegis_ai.models.explainability.tree_explainer import (
    TreeExplainer,
    XGBoostExplainer,
    LightGBMExplainer,
    FeatureImportance,
    DecisionPath,
)
from aegis_ai.models.explainability.templates import (
    RiskFactor,
    ExplanationTemplate,
    ExplanationBuilder,
    EXPLANATION_TEMPLATES,
)

__all__ = [
    "TreeExplainer",
    "XGBoostExplainer",
    "LightGBMExplainer",
    "FeatureImportance",
    "DecisionPath",
    "RiskFactor",
    "ExplanationTemplate",
    "ExplanationBuilder",
    "EXPLANATION_TEMPLATES",
]
