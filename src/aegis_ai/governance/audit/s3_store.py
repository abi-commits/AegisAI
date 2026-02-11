"""S3-backed audit store for immutable, versioned audit logs."""

import json, logging, hashlib, uuid, threading, os
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, Optional, List

import boto3
from botocore.exceptions import ClientError

from aegis_ai.governance.schemas import AuditEntry, AuditEventType
from aegis_ai.governance.audit.store import AuditStore, AuditLogIntegrityError

logger = logging.getLogger(__name__)


class S3AuditStore(AuditStore):
    """S3-backed audit store for immutable, versioned audit logs."""
    
    DEFAULT_REGION = "us-east-1"
    DEFAULT_PREFIX = "audit-logs/"
    DEFAULT_ENVIRONMENT = "production"
    DEFAULT_HASH_ALGORITHM = "sha256"
    
    def __init__(self, bucket_name: Optional[str] = None,
                 prefix: str = DEFAULT_PREFIX, environment: str = DEFAULT_ENVIRONMENT,
                 region: Optional[str] = None, aws_profile: Optional[str] = None,
                 enable_versioning: bool = True, enable_object_lock: bool = False,
                 hash_algorithm: str = DEFAULT_HASH_ALGORITHM,
                 enable_hash_chain: bool = True,
                 dynamodb_table_for_locking: Optional[str] = None):
        self.bucket_name = bucket_name or os.environ.get("S3_AUDIT_BUCKET")
        if not self.bucket_name:
            raise ValueError("S3 bucket name required. Set S3_AUDIT_BUCKET or pass bucket_name.")
        
        self.prefix = prefix
        self.environment = environment
        self.region = region or os.environ.get("AWS_REGION", self.DEFAULT_REGION)
        self.enable_versioning = enable_versioning
        self.enable_object_lock = enable_object_lock
        self.hash_algorithm = hash_algorithm
        self.enable_hash_chain = enable_hash_chain
        self.dynamodb_table_for_locking = dynamodb_table_for_locking
        
        if aws_profile:
            session = boto3.Session(profile_name=aws_profile)
            self.s3_client = session.client("s3", region_name=self.region)
            self.dynamodb_resource = session.resource("dynamodb", region_name=self.region)
        else:
            self.s3_client = boto3.client("s3", region_name=self.region)
            self.dynamodb_resource = boto3.resource("dynamodb", region_name=self.region)
        
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
    
    def _get_partition_prefix(self, date: Optional[str] = None) -> str:
        """Get the S3 prefix for a specific date (partition).
        
        Format: {prefix}{environment}/{date}/
        Example: audit-logs/production/2026-01-29/
        """
        if date is None:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        return f"{self.prefix}{self.environment}/{date}/"
    
    def _get_unique_key(self, date: Optional[str] = None, decision_id: Optional[str] = None) -> str:
        """Get a unique S3 key for a new entry.
        
        Format: {prefix}{environment}/{date}/{timestamp}_{uuid}.json
        """
        prefix = self._get_partition_prefix(date)
        ts = int(datetime.now(timezone.utc).timestamp() * 1000)
        uid = str(uuid.uuid4())
        suffix = f"_{decision_id}" if decision_id else ""
        return f"{prefix}{ts}_{uid}{suffix}.json"
    
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
    
    def append_entry(self, entry: AuditEntry) -> AuditEntry:
        """Append an audit entry to S3 (write a new object per entry).
        
        Args:
            entry: The audit entry to append
            
        Returns:
            The entry with hash fields populated
            
        Raises:
            IOError: If write fails
        """
        # Note: In distributed mode with individual files, hash chaining is disabled 
        # or requires a different mechanism (e.g. DynamoDB sequence). 
        # For this fix, we disable strict chaining to prevent race conditions.
        previous_hash = None
        
        # Convert entry to JSON
        entry_dict = entry.model_dump(mode="json")
        
        # Add hashes for integrity (even if chain is broken, we hash the entry itself)
        if self.enable_hash_chain:
            entry_dict["previous_hash"] = previous_hash
            entry_dict["entry_hash"] = self._compute_hash(
                json.dumps(entry_dict, default=str),
                previous_hash
            )
        
        # Convert to JSON
        json_content = json.dumps(entry_dict, default=str)
        
        # Get unique S3 key
        key = self._get_unique_key(decision_id=entry.decision_id)
        
        try:
            # Put object with versioning
            put_kwargs = {
                "Bucket": self.bucket_name,
                "Key": key,
                "Body": json_content.encode("utf-8"),
                "ContentType": "application/json",
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
        prefix = self._get_partition_prefix(date)
        
        try:
            # List objects in the partition
            paginator = self.s3_client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)
            
            for page in page_iterator:
                if "Contents" not in page:
                    continue
                    
                for obj in page["Contents"]:
                    key = obj["Key"]
                    try:
                        response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
                        body = response["Body"].read().decode("utf-8")
                        
                        # Support both single JSON per file and legacy JSONL
                        lines = body.strip().split("\n")
                        for line in lines:
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
                                logger.warning(f"Could not parse content in {key}: {e}")
                                continue
                        
                    except Exception as e:
                        logger.warning(f"Could not read/parse audit entry {key}: {e}")
                        continue
                        
        except ClientError as e:
            logger.error(f"Failed to list S3 objects: {e}")
            raise IOError(f"S3 read failed: {e}") from e
    
    def verify_integrity(self, date: Optional[str] = None) -> bool:
        """Verify hash integrity of S3 audit logs.
        
        Args:
            date: Date to verify (YYYY-MM-DD format)
            
        Returns:
            True if integrity check passes
            
        Raises:
            AuditLogIntegrityError: If integrity check fails
        """
        if not self.enable_hash_chain:
            return True
        
        prefix = self._get_partition_prefix(date)
        
        try:
             # List objects in the partition
            paginator = self.s3_client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)
            
            for page in page_iterator:
                if "Contents" not in page:
                    continue
                
                for obj in page["Contents"]:
                    key = obj["Key"]
                    try:
                        response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
                        body = response["Body"].read().decode("utf-8")
                        
                        entry_dict = json.loads(body)
                        stored_hash = entry_dict.get("entry_hash")
                        stored_previous = entry_dict.get("previous_hash")
                        
                        # Verify entry hash
                        entry_dict_copy = entry_dict.copy()
                        entry_dict_copy.pop("entry_hash", None)
                        
                        computed_hash = self._compute_hash(
                            json.dumps(entry_dict_copy, default=str),
                            stored_previous
                        )
                        
                        if computed_hash != stored_hash:
                            raise AuditLogIntegrityError(
                                f"Hash mismatch in {key}: "
                                f"expected {stored_hash}, got {computed_hash}"
                            )
                            
                    except Exception as e:
                        logger.warning(f"Integrity check failed to read/parse {key}: {e}")
                        raise AuditLogIntegrityError(f"Integrity check failed for {key}: {e}")

            logger.info(f"Integrity check passed for partition {prefix}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to list S3 objects for integrity check: {e}")
            raise AuditLogIntegrityError(f"Integrity check failed: {e}")
    
    def get_last_hash(self) -> Optional[str]:
        """Get the hash of the last entry for chain continuity.
        
        Returns:
            None (Hash chaining disabled in distributed mode)
        """
        return None
