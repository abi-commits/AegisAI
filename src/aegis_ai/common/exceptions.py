"""Custom exceptions for AegisAI.

Provides a hierarchy of exceptions for different error types.
All AegisAI exceptions inherit from AegisAIException.
"""

from typing import Any, Dict, Optional


class AegisAIException(Exception):
    """Base exception for all AegisAI errors.
    
    Attributes:
        message: Human-readable error message
        code: Machine-readable error code
        details: Additional context about the error
    """
    
    def __init__(
        self,
        message: str,
        code: str = "AEGIS_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details,
        }


class ConfigurationError(AegisAIException):
    """Raised when configuration is invalid or missing."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="CONFIG_ERROR", details=details)


class ValidationError(AegisAIException):
    """Raised when input validation fails."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="VALIDATION_ERROR", details=details)


class AgentError(AegisAIException):
    """Raised when an agent fails to process input."""
    
    def __init__(
        self,
        message: str,
        agent_name: str,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        details["agent_name"] = agent_name
        super().__init__(message, code="AGENT_ERROR", details=details)


class PolicyViolationError(AegisAIException):
    """Raised when a policy constraint is violated."""
    
    def __init__(
        self,
        message: str,
        policy_name: str,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        details["policy_name"] = policy_name
        super().__init__(message, code="POLICY_VIOLATION", details=details)


class AuditError(AegisAIException):
    """Raised when audit logging fails."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="AUDIT_ERROR", details=details)


class ModelError(AegisAIException):
    """Raised when ML model inference fails."""
    
    def __init__(
        self,
        message: str,
        model_name: str,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        details["model_name"] = model_name
        super().__init__(message, code="MODEL_ERROR", details=details)


class EscalationError(AegisAIException):
    """Raised when escalation handling fails."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="ESCALATION_ERROR", details=details)
