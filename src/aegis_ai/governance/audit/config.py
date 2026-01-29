"""Audit Layer Configuration and Initialization.

Provides factory methods and configuration for audit stores (S3, DynamoDB).
Supports multiple storage backends for different audit data types.

Environment variables:
- AUDIT_STORAGE_TYPE: "s3" (default), "file", or "dynamodb"
- S3_AUDIT_BUCKET: S3 bucket for audit logs
- DYNAMODB_METADATA_TABLE: DynamoDB table for metadata
- AWS_REGION: AWS region
- AWS_PROFILE: AWS profile name
"""

import logging
import os
from typing import Optional

from aegis_ai.governance.audit.store import AuditStore, FileAuditStore
from aegis_ai.governance.audit.logger import AuditLogger


logger = logging.getLogger(__name__)


class AuditConfig:
    """Configuration for audit layer."""
    
    # Storage backend options
    STORAGE_FILE = "file"
    STORAGE_S3 = "s3"
    STORAGE_DYNAMODB = "dynamodb"
    
    def __init__(self):
        """Initialize audit configuration from environment."""
        self.storage_type = os.environ.get("AUDIT_STORAGE_TYPE", self.STORAGE_S3)
        self.s3_bucket = os.environ.get("S3_AUDIT_BUCKET")
        self.s3_prefix = os.environ.get("S3_AUDIT_PREFIX", "audit-logs/")
        self.s3_environment = os.environ.get("S3_ENVIRONMENT", "production")
        self.dynamodb_table = os.environ.get("DYNAMODB_METADATA_TABLE")
        self.aws_region = os.environ.get("AWS_REGION", "us-east-1")
        self.aws_profile = os.environ.get("AWS_PROFILE")
        self.log_dir = os.environ.get("AUDIT_LOG_DIR", "./logs/audit")
        self.enable_hash_chain = os.environ.get("ENABLE_HASH_CHAIN", "true").lower() == "true"
        self.enable_versioning = os.environ.get("ENABLE_S3_VERSIONING", "true").lower() == "true"
        self.enable_object_lock = os.environ.get("ENABLE_S3_OBJECT_LOCK", "false").lower() == "true"
        self.use_background_writer = os.environ.get("USE_BACKGROUND_WRITER", "false").lower() == "true"


def create_audit_store(
    storage_type: Optional[str] = None,
    **kwargs
) -> AuditStore:
    """Factory method to create audit store based on configuration.
    
    Args:
        storage_type: "s3", "file", or "dynamodb"
        **kwargs: Additional arguments for store initialization
        
    Returns:
        Configured AuditStore instance
    """
    config = AuditConfig()
    storage_type = storage_type or config.storage_type
    
    if storage_type == config.STORAGE_S3:
        # Import here to avoid hard dependency on boto3
        try:
            from aegis_ai.governance.audit.s3_store import S3AuditStore
            
            return S3AuditStore(
                bucket_name=config.s3_bucket or kwargs.get("bucket_name"),
                prefix=config.s3_prefix,
                environment=config.s3_environment,
                region=config.aws_region,
                aws_profile=config.aws_profile,
                enable_versioning=config.enable_versioning,
                enable_object_lock=config.enable_object_lock,
                enable_hash_chain=config.enable_hash_chain,
                **kwargs
            )
        except ImportError as e:
            logger.error(f"boto3 not installed, cannot use S3 storage: {e}")
            logger.warning("Falling back to file-based storage")
            return create_audit_store(storage_type=config.STORAGE_FILE, **kwargs)
    
    elif storage_type == config.STORAGE_FILE:
        return FileAuditStore(
            log_dir=config.log_dir or kwargs.get("log_dir"),
            log_filename_pattern=kwargs.get("log_filename_pattern", "aegis_audit_{date}.jsonl"),
            enable_hash_chain=config.enable_hash_chain,
            **kwargs
        )
    
    else:
        raise ValueError(f"Unknown storage type: {storage_type}")


def create_audit_logger(
    storage_type: Optional[str] = None,
    use_background_writer: Optional[bool] = None,
    **kwargs
) -> AuditLogger:
    """Factory method to create audit logger with configured backend.
    
    Args:
        storage_type: "s3" or "file" (default: from environment)
        use_background_writer: Whether to use background writing
        **kwargs: Additional arguments for store initialization
        
    Returns:
        Configured AuditLogger instance
    """
    config = AuditConfig()
    use_background_writer = use_background_writer or config.use_background_writer
    
    store = create_audit_store(storage_type=storage_type, **kwargs)
    
    return AuditLogger(
        store=store,
        use_background_writer=use_background_writer,
    )


def create_dynamodb_metadata_store():
    """Factory method to create DynamoDB metadata store.
    
    Returns:
        Configured DynamoDBOperationalMetadata instance
        
    Raises:
        ImportError: If boto3 not installed
        ValueError: If DYNAMODB_METADATA_TABLE not set
    """
    try:
        from aegis_ai.governance.audit.dynamodb_metadata import DynamoDBOperationalMetadata
    except ImportError as e:
        raise ImportError(f"boto3 not installed, cannot use DynamoDB: {e}") from e
    
    config = AuditConfig()
    
    return DynamoDBOperationalMetadata(
        table_name=config.dynamodb_table,
        region=config.aws_region,
        aws_profile=config.aws_profile,
    )


# Re-export for convenience
__all__ = [
    "AuditConfig",
    "create_audit_store",
    "create_audit_logger",
    "create_dynamodb_metadata_store",
]
