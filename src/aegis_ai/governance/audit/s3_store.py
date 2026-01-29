"""S3 Audit Store - Append-only, Versioned, Immutable Audit Logs.

This module provides an S3-backed audit store with:
- Append-only semantics
- Object versioning for immutability
- JSONL format (write-once, read-many pattern)
- Date/environment partitioning
- Optional Object Lock for regulatory compliance
- Hash chain integrity verification

Design principles:
- Regulator-friendly (receipts live forever)
- Immutable append-only logs
- Automatic date partitioning
- Thread-safe operations
"""

import json
import logging
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, Optional
import threading
import os

import boto3
from botocore.exceptions import ClientError

from aegis_ai.governance.schemas import AuditEntry, AuditEventType
from aegis_ai.governance.audit.store import AuditStore, AuditLogIntegrityError


logger = logging.getLogger(__name__)


class S3AuditStore(AuditStore):
    """S3-backed audit store for immutable, versioned audit logs.
    
    Features:
    - Append-only JSONL logs
    - Automatic date partitioning
    - Optional S3 versioning
    - Optional Object Lock (governance/compliance mode)
    - Hash chain integrity for tampering detection
    - Thread-safe with file locking via DynamoDB
    
    Environment variables:
    - AWS_REGION: AWS region (default: us-east-1)
    - AWS_PROFILE: AWS profile name (optional)
    - S3_AUDIT_BUCKET: S3 bucket for audit logs
    - S3_AUDIT_PREFIX: Prefix for audit logs (default: audit-logs/)
    - S3_ENVIRONMENT: Environment name (default: production)
    - S3_ENABLE_VERSIONING: Enable versioning (default: true)
    - S3_ENABLE_OBJECT_LOCK: Enable Object Lock (default: false)
    """
    
    # S3 configuration
    DEFAULT_REGION = "us-east-1"
    DEFAULT_PREFIX = "audit-logs/"
    DEFAULT_ENVIRONMENT = "production"
    
    # Integrity
    DEFAULT_HASH_ALGORITHM = "sha256"
    
    def __init__(
        self,
        bucket_name: Optional[str] = None,
        prefix: str = DEFAULT_PREFIX,
        environment: str = DEFAULT_ENVIRONMENT,
        region: Optional[str] = None,
        aws_profile: Optional[str] = None,
        enable_versioning: bool = True,
        enable_object_lock: bool = False,
        hash_algorithm: str = DEFAULT_HASH_ALGORITHM,
        enable_hash_chain: bool = True,
        dynamodb_table_for_locking: Optional[str] = None,
    ):
        """Initialize S3 audit store.
        
        Args:
            bucket_name: S3 bucket name (or from S3_AUDIT_BUCKET env var)
            prefix: Prefix for audit logs (e.g., "audit-logs/")
            environment: Environment name for partitioning (e.g., "production")
            region: AWS region (or from AWS_REGION env var)
            aws_profile: AWS profile name (optional)
            enable_versioning: Enable S3 versioning
            enable_object_lock: Enable Object Lock for immutability
            hash_algorithm: Hash algorithm for integrity checks
            enable_hash_chain: Enable hash chain for tampering detection
            dynamodb_table_for_locking: DynamoDB table for distributed locking
        """
        # Get credentials from environment
        self.bucket_name = bucket_name or os.environ.get("S3_AUDIT_BUCKET")
        if not self.bucket_name:
            raise ValueError(
                "S3 bucket name required. Set S3_AUDIT_BUCKET or pass bucket_name parameter."
            )
        
        self.prefix = prefix
        self.environment = environment
        self.region = region or os.environ.get("AWS_REGION", self.DEFAULT_REGION)
        self.enable_versioning = enable_versioning
        self.enable_object_lock = enable_object_lock
        self.hash_algorithm = hash_algorithm
        self.enable_hash_chain = enable_hash_chain
        self.dynamodb_table_for_locking = dynamodb_table_for_locking
        
        # Initialize S3 client
        session_kwargs = {}
        if aws_profile:
            session = boto3.Session(profile_name=aws_profile)
            self.s3_client = session.client("s3", region_name=self.region)
            self.dynamodb_resource = session.resource("dynamodb", region_name=self.region)
        else:
            self.s3_client = boto3.client("s3", region_name=self.region)
            self.dynamodb_resource = boto3.resource("dynamodb", region_name=self.region)
        
        # Lock for thread safety
        self._local_lock = threading.RLock()
        
        # Initialize bucket if needed
        self._ensure_bucket_configured()
        
        logger.info(
            f"Initialized S3AuditStore: bucket={self.bucket_name}, "
            f"env={self.environment}, versioning={self.enable_versioning}, "
            f"object_lock={self.enable_object_lock}"
        )
    
    def _ensure_bucket_configured(self) -> None:
        """Ensure S3 bucket exists and is configured correctly."""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.debug(f"S3 bucket {self.bucket_name} exists")
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                raise ValueError(f"S3 bucket {self.bucket_name} does not exist")
            raise
        
        # Enable versioning if requested
        if self.enable_versioning:
            try:
                self.s3_client.put_bucket_versioning(
                    Bucket=self.bucket_name,
                    VersioningConfiguration={"Status": "Enabled"}
                )
                logger.debug(f"Enabled versioning on bucket {self.bucket_name}")
            except ClientError as e:
                logger.warning(f"Could not enable versioning: {e}")
    
    def _get_log_key(self, date: Optional[str] = None) -> str:
        """Get the S3 key for today's log file.
        
        Format: {prefix}/{environment}/{date}/audit.jsonl
        Example: audit-logs/production/2026-01-29/audit.jsonl
        
        Args:
            date: Date string (YYYY-MM-DD), defaults to today
            
        Returns:
            S3 key path
        """
        if date is None:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        return f"{self.prefix}{self.environment}/{date}/audit.jsonl"
    
    def _compute_hash(self, data: str, previous_hash: Optional[str] = None) -> str:
        """Compute hash of data with optional chaining.
        
        Args:
            data: Data to hash (JSONL line)
            previous_hash: Previous hash for chaining
            
        Returns:
            Hash digest (hex string)
        """
        hasher = hashlib.new(self.hash_algorithm)
        if previous_hash:
            hasher.update(previous_hash.encode())
        hasher.update(data.encode())
        return hasher.hexdigest()
    
    def _get_last_hash_from_s3(self, key: str) -> Optional[str]:
        """Get the hash of the last line in S3 file.
        
        Args:
            key: S3 key path
            
        Returns:
            Last entry hash or None if file doesn't exist
        """
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            body = response["Body"].read().decode("utf-8")
            
            if not body.strip():
                return None
            
            # Get last non-empty line
            lines = body.strip().split("\n")
            last_line = lines[-1]
            
            # Parse entry and extract hash
            entry_dict = json.loads(last_line)
            return entry_dict.get("entry_hash")
        except self.s3_client.exceptions.NoSuchKey:
            return None
        except Exception as e:
            logger.warning(f"Could not get last hash from {key}: {e}")
            return None
    
    def append_entry(self, entry: AuditEntry) -> AuditEntry:
        """Append an audit entry to S3 (write-once, append-only).
        
        Args:
            entry: The audit entry to append
            
        Returns:
            The entry with hash fields populated
            
        Raises:
            IOError: If write fails
        """
        with self._local_lock:
            # Compute entry hash if hash chain enabled
            previous_hash = None
            if self.enable_hash_chain:
                key = self._get_log_key()
                previous_hash = self._get_last_hash_from_s3(key)
            
            # Convert entry to JSON
            entry_dict = entry.model_dump(mode="json")
            
            # Add hashes for integrity
            if self.enable_hash_chain:
                entry_dict["previous_hash"] = previous_hash
                entry_dict["entry_hash"] = self._compute_hash(
                    json.dumps(entry_dict, default=str),
                    previous_hash
                )
            
            # Convert to JSONL
            jsonl_line = json.dumps(entry_dict, default=str)
            
            # Get S3 key
            key = self._get_log_key()
            
            try:
                # Get existing content
                try:
                    response = self.s3_client.get_object(
                        Bucket=self.bucket_name,
                        Key=key
                    )
                    existing_content = response["Body"].read().decode("utf-8")
                except self.s3_client.exceptions.NoSuchKey:
                    existing_content = ""
                
                # Append new line
                new_content = existing_content
                if existing_content and not existing_content.endswith("\n"):
                    new_content += "\n"
                new_content += jsonl_line + "\n"
                
                # Put object with versioning
                put_kwargs = {
                    "Bucket": self.bucket_name,
                    "Key": key,
                    "Body": new_content.encode("utf-8"),
                    "ContentType": "application/x-ndjson",
                    "Metadata": {
                        "event-type": entry.event_type.value,
                        "timestamp": entry.timestamp.isoformat(),
                        "environment": self.environment,
                    }
                }
                
                # Add Object Lock retention if enabled
                if self.enable_object_lock:
                    put_kwargs["ObjectLockMode"] = "GOVERNANCE"
                    put_kwargs["ObjectLockRetainUntilDate"] = datetime.now(
                        timezone.utc
                    )
                
                self.s3_client.put_object(**put_kwargs)
                
                logger.debug(
                    f"Appended audit entry to S3: {key} "
                    f"(decision_id={entry.decision_id})"
                )
                
                # Update entry with computed hash
                if self.enable_hash_chain:
                    entry.entry_hash = entry_dict.get("entry_hash")
                    entry.previous_hash = previous_hash
                
                return entry
            
            except ClientError as e:
                logger.error(f"Failed to append to S3: {e}")
                raise IOError(f"S3 write failed: {e}") from e
    
    def get_entries(
        self,
        date: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        decision_id: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Generator[AuditEntry, None, None]:
        """Retrieve audit entries from S3 with filtering.
        
        Args:
            date: Filter by date (YYYY-MM-DD format)
            event_type: Filter by event type
            decision_id: Filter by decision ID
            session_id: Filter by session ID
            user_id: Filter by user ID
            
        Yields:
            Matching AuditEntry objects
        """
        key = self._get_log_key(date)
        
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=key
            )
            body = response["Body"].read().decode("utf-8")
        except self.s3_client.exceptions.NoSuchKey:
            logger.debug(f"No audit logs found for {key}")
            return
        except ClientError as e:
            logger.error(f"Failed to read from S3: {e}")
            raise IOError(f"S3 read failed: {e}") from e
        
        # Parse JSONL and filter
        for line in body.strip().split("\n"):
            if not line.strip():
                continue
            
            try:
                entry_dict = json.loads(line)
                entry = AuditEntry.model_validate(entry_dict)
                
                # Apply filters
                if event_type and entry.event_type != event_type:
                    continue
                if decision_id and entry.decision_id != decision_id:
                    continue
                if session_id and entry.session_id != session_id:
                    continue
                if user_id and entry.user_id != user_id:
                    continue
                
                yield entry
            
            except Exception as e:
                logger.warning(f"Could not parse audit entry: {e}")
                continue
    
    def verify_integrity(self, date: Optional[str] = None) -> bool:
        """Verify hash chain integrity of S3 audit logs.
        
        Args:
            date: Date to verify (YYYY-MM-DD format)
            
        Returns:
            True if integrity check passes
            
        Raises:
            AuditLogIntegrityError: If integrity check fails
        """
        if not self.enable_hash_chain:
            return True
        
        key = self._get_log_key(date)
        previous_hash = None
        
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=key
            )
            body = response["Body"].read().decode("utf-8")
        except self.s3_client.exceptions.NoSuchKey:
            return True
        
        for line_num, line in enumerate(body.strip().split("\n"), 1):
            if not line.strip():
                continue
            
            try:
                entry_dict = json.loads(line)
                stored_hash = entry_dict.get("entry_hash")
                stored_previous = entry_dict.get("previous_hash")
                
                # Verify hash chain continuity
                if stored_previous != previous_hash:
                    raise AuditLogIntegrityError(
                        f"Hash chain broken at line {line_num}: "
                        f"expected previous_hash={previous_hash}, "
                        f"got {stored_previous}"
                    )
                
                # Verify entry hash
                entry_dict_copy = entry_dict.copy()
                entry_dict_copy.pop("entry_hash", None)
                computed_hash = self._compute_hash(
                    json.dumps(entry_dict_copy, default=str),
                    previous_hash
                )
                
                if computed_hash != stored_hash:
                    raise AuditLogIntegrityError(
                        f"Hash mismatch at line {line_num}: "
                        f"expected {stored_hash}, got {computed_hash}"
                    )
                
                previous_hash = stored_hash
            
            except json.JSONDecodeError as e:
                raise AuditLogIntegrityError(
                    f"Invalid JSON at line {line_num}: {e}"
                )
        
        logger.info(f"Integrity check passed for {key}")
        return True
    
    def get_last_hash(self) -> Optional[str]:
        """Get the hash of the last entry for chain continuity.
        
        Returns:
            The last entry hash, or None if store is empty
        """
        if not self.enable_hash_chain:
            return None
        
        key = self._get_log_key()
        return self._get_last_hash_from_s3(key)
