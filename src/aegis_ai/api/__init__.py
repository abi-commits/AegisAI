"""API - inference service and endpoints.

Single endpoint design:
    POST /evaluate-login

Returns ONLY:
    - decision
    - confidence
    - explanation
    - escalation_flag
    - audit_id

IMPORTANT: No internal agent outputs are exposed through this API.
"""

from aegis_ai.api.gateway import app
from aegis_ai.api.schemas import (
    EvaluateLoginRequest,
    EvaluateLoginResponse,
    ErrorResponse,
)
from aegis_ai.api.service import LoginEvaluationService

__all__ = [
    "app",
    "EvaluateLoginRequest",
    "EvaluateLoginResponse",
    "ErrorResponse",
    "LoginEvaluationService",
]
