"""Governance - Policy Enforcement, Audit, and Human Override.

This package makes AegisAI safe to deploy, not just smart.

Components:
- PolicyEngine: Evaluates and enforces runtime constraints (ZERO ML)
- AuditLogger: Immutable JSONL logging of all decisions
- HumanOverrideHandler: Captures human interventions with full audit trail
- Schemas: Type definitions for governance data structures

Design principles:
- Policies are checked BEFORE actions
- Violations produce HARD STOPS
- Policies are versioned
- All decisions produce immutable audit entries
- Human overrides preserve AI decisions and require reasons
- No model can bypass governance
"""

from aegis_ai.governance.audit.logger import (
    AuditLogger,
    AuditLogIntegrityError,
)
from aegis_ai.governance.policies.engine import (
    PolicyEngine,
    PolicyViolationError,
)
from aegis_ai.governance.override import (
    HumanOverrideHandler,
    HumanOverrideError,
)
from aegis_ai.governance.schemas import (
    AuditEntry,
    AuditEventType,
    HumanOverride,
    OverrideType,
    PolicyCheckResult,
    PolicyDecision,
    PolicyRules,
    PolicyViolation,
    PolicyViolationType,
)

__all__ = [
    # Core components
    "AuditLogger",
    "PolicyEngine",
    "HumanOverrideHandler",
    # Exceptions
    "AuditLogIntegrityError",
    "PolicyViolationError",
    "HumanOverrideError",
    # Schemas
    "AuditEntry",
    "AuditEventType",
    "HumanOverride",
    "OverrideType",
    "PolicyCheckResult",
    "PolicyDecision",
    "PolicyRules",
    "PolicyViolation",
    "PolicyViolationType",
]

