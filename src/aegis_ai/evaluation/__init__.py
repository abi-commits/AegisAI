"""Evaluation - metrics and analysis.

Track what matters:
- False positive rate
- Escalation rate  
- Human override rate
- Confidence calibration error
- Policy violation count
"""

from aegis_ai.evaluation.metrics import EvaluationMetrics
from aegis_ai.evaluation.runner import (
    EvaluationRunner,
    run_standard_evaluation,
    run_quick_evaluation,
)

__all__ = [
    "EvaluationMetrics",
    "EvaluationRunner", 
    "run_standard_evaluation",
    "run_quick_evaluation",
]
