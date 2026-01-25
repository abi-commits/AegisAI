"""Custom exceptions for AegisAI."""


class AegisAIException(Exception):
    """Base exception for AegisAI."""
    pass


class AgentExecutionError(AegisAIException):
    """Raised when agent execution fails."""
    pass


class DecisionError(AegisAIException):
    """Raised when decision logic fails."""
    pass


class PolicyViolationError(AegisAIException):
    """Raised when policy rules are violated."""
    pass


class ValidationError(AegisAIException):
    """Raised when data validation fails."""
    pass
