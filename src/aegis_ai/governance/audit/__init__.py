"""Audit module - Immutable logging for all decisions.

Provides append-only JSONL logging with hash chain integrity verification.
Supports multiple backends: File (local), S3 (cloud), DynamoDB (metadata).

Components:
- AuditLogger: High-level facade for audit logging
- AuditStore: Abstract base class for storage backends
- FileAuditStore: File-based storage with hash chain integrity
- S3AuditStore: S3-backed immutable append-only logs
- DynamoDBOperationalMetadata: Fast operational metadata lookups
- UnifiedAuditTrail: End-to-end audit trail (S3 + DynamoDB)
- BackgroundAuditWriter: Async writer for high throughput
"""

from aegis_ai.governance.audit.store import (
    AuditStore,
    FileAuditStore,
    AuditLogIntegrityError,
)
from aegis_ai.governance.audit.logger import AuditLogger
from aegis_ai.governance.audit.background_writer import BackgroundAuditWriter
from aegis_ai.governance.audit.config import (
    AuditConfig,
    create_audit_store,
    create_audit_logger,
    create_dynamodb_metadata_store,
)

__all__ = [
    "AuditLogger",
    "AuditStore",
    "FileAuditStore",
    "AuditLogIntegrityError",
    "BackgroundAuditWriter",
    "AuditConfig",
    "create_audit_store",
    "create_audit_logger",
    "create_dynamodb_metadata_store",
]
