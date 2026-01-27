"""Audit module - Immutable logging for all decisions.

Provides append-only JSONL logging with hash chain integrity verification.
"""

from src.aegis_ai.governance.audit.logger import (
    AuditLogger,
    AuditLogIntegrityError,
)

__all__ = [
    "AuditLogger",
    "AuditLogIntegrityError",
]
