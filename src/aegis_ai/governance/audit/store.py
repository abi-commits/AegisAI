"""Audit Store - Abstraction for audit log persistence.

This module provides an interface for audit log storage backends,
decoupling audit logic from specific persistence mechanisms.

Design principles:
- Protocol-based interface for testability and extensibility
- Support for file, database, or remote storage backends
- Thread-safe operations
- Atomic writes with integrity verification
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, List, Optional, Protocol
import hashlib
import json
import os
import threading
import fcntl

from aegis_ai.governance.schemas import AuditEntry, AuditEventType


class AuditLogIntegrityError(Exception):
    """Raised when audit log integrity check fails."""
    pass


class AuditStore(ABC):
    """Abstract base class for audit log storage backends.
    
    Implementations must provide thread-safe, append-only storage
    with optional hash chain integrity.
    """
    
    @abstractmethod
    def append_entry(self, entry: AuditEntry) -> AuditEntry:
        """Append an audit entry to the store.
        
        Args:
            entry: The audit entry to append
            
        Returns:
            The entry with hash chain fields populated
            
        Raises:
            IOError: If write fails
        """
        pass
    
    @abstractmethod
    def get_entries(
        self,
        date: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        decision_id: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Generator[AuditEntry, None, None]:
        """Retrieve audit entries with optional filtering.
        
        Args:
            date: Filter by date (YYYY-MM-DD format)
            event_type: Filter by event type
            decision_id: Filter by decision ID
            session_id: Filter by session ID
            user_id: Filter by user ID
            
        Yields:
            Matching AuditEntry objects
        """
        pass
    
    @abstractmethod
    def verify_integrity(self, date: Optional[str] = None) -> bool:
        """Verify hash chain integrity of stored entries.
        
        Args:
            date: Date to verify (YYYY-MM-DD format), or None for current
            
        Returns:
            True if integrity check passes
            
        Raises:
            AuditLogIntegrityError: If integrity check fails
        """
        pass
    
    @abstractmethod
    def get_last_hash(self) -> Optional[str]:
        """Get the hash of the last entry for chain continuity.
        
        Returns:
            The last entry hash, or None if store is empty
        """
        pass


class FileAuditStore(AuditStore):
    """File-based audit store with JSONL format and hash chain integrity.
    
    Features:
    - Append-only JSONL files with daily rotation
    - Hash chain for tamper detection
    - Atomic writes with file locking
    - Sidecar metadata for fast startup
    """
    
    DEFAULT_LOG_DIR = Path(__file__).parent.parent.parent.parent.parent / "logs" / "audit"
    METADATA_SUFFIX = ".meta"
    
    def __init__(
        self,
        log_dir: Optional[str] = None,
        log_filename_pattern: str = "aegis_audit_{date}.jsonl",
        enable_hash_chain: bool = True,
        hash_algorithm: str = "sha256",
        fsync_on_write: bool = False,
    ):
        """Initialize file audit store.
        
        Args:
            log_dir: Directory for audit logs. Uses default if not provided.
            log_filename_pattern: Pattern for log filename. {date} is replaced.
            enable_hash_chain: Whether to enable hash chain integrity.
            hash_algorithm: Hash algorithm for integrity checks.
            fsync_on_write: Whether to fsync after each write (slower but safer).
        """
        self.log_dir = Path(log_dir) if log_dir else self.DEFAULT_LOG_DIR
        self.log_filename_pattern = log_filename_pattern
        self.enable_hash_chain = enable_hash_chain
        self.hash_algorithm = hash_algorithm
        self.fsync_on_write = fsync_on_write
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Cache last hash for chain continuity
        self._last_hash: Optional[str] = None
        
        # Ensure log directory exists with secure permissions
        self.log_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.log_dir, 0o700)
        except OSError:
            pass  # May fail on some systems; proceed anyway
        
        # Initialize hash chain from metadata or existing logs
        if self.enable_hash_chain:
            self._last_hash = self._load_last_hash()
    
    def _get_current_log_path(self) -> Path:
        """Get path to current day's log file."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        filename = self.log_filename_pattern.replace("{date}", today)
        return self.log_dir / filename
    
    def _get_metadata_path(self) -> Path:
        """Get path to current day's metadata file."""
        log_path = self._get_current_log_path()
        return log_path.with_suffix(log_path.suffix + self.METADATA_SUFFIX)
    
    def _load_last_hash(self) -> Optional[str]:
        """Load last hash from metadata file or scan log."""
        meta_path = self._get_metadata_path()
        
        # Try metadata file first (fast path)
        if meta_path.exists():
            try:
                with open(meta_path, "r") as f:
                    meta = json.load(f)
                    return meta.get("last_hash")
            except (json.JSONDecodeError, IOError):
                pass
        
        # Fall back to scanning log file
        return self._scan_log_for_last_hash()
    
    def _scan_log_for_last_hash(self) -> Optional[str]:
        """Read the last hash from the current log file."""
        log_path = self._get_current_log_path()
        
        if not log_path.exists():
            return None
        
        last_hash = None
        try:
            with open(log_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        entry = json.loads(line)
                        last_hash = entry.get("entry_hash")
        except (json.JSONDecodeError, IOError):
            return None
        
        return last_hash
    
    def _save_metadata(self, last_hash: str, entry_count: int) -> None:
        """Save metadata to sidecar file for fast startup."""
        meta_path = self._get_metadata_path()
        meta = {
            "last_hash": last_hash,
            "entry_count": entry_count,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            with open(meta_path, "w") as f:
                json.dump(meta, f)
        except IOError:
            pass  # Metadata is optional; continue without it
    
    def _compute_hash(self, content: str) -> str:
        """Compute hash of content using configured algorithm."""
        hasher = hashlib.new(self.hash_algorithm)
        hasher.update(content.encode("utf-8"))
        return hasher.hexdigest()
    
    def _serialize_for_hash(self, entry_dict: dict) -> str:
        """Serialize entry dict canonically for hash computation.
        
        Uses explicit datetime formatting to ensure deterministic hashing.
        """
        def serialize_value(v):
            if isinstance(v, datetime):
                return v.isoformat()
            return v
        
        # Deep copy with datetime serialization
        def deep_serialize(obj):
            if isinstance(obj, dict):
                return {k: deep_serialize(v) for k, v in sorted(obj.items())}
            elif isinstance(obj, list):
                return [deep_serialize(item) for item in obj]
            else:
                return serialize_value(obj)
        
        serialized = deep_serialize(entry_dict)
        return json.dumps(serialized, sort_keys=True, ensure_ascii=False)
    
    def _create_hash_chain_entry(self, entry: AuditEntry) -> AuditEntry:
        """Add hash chain fields to entry."""
        if not self.enable_hash_chain:
            return entry
        
        # Create a copy with previous hash
        entry_dict = entry.model_dump(mode="json")
        entry_dict["previous_hash"] = self._last_hash
        entry_dict["entry_hash"] = None
        
        # Compute hash of entry content
        content_to_hash = self._serialize_for_hash(entry_dict)
        entry_hash = self._compute_hash(content_to_hash)
        
        entry_dict["entry_hash"] = entry_hash
        
        return AuditEntry.model_validate(entry_dict)
    
    def append_entry(self, entry: AuditEntry) -> AuditEntry:
        """Append entry to log file with atomic write and file locking."""
        with self._lock:
            # Add hash chain
            entry = self._create_hash_chain_entry(entry)
            
            # Get current log file
            log_path = self._get_current_log_path()
            
            # Append with file locking for cross-process safety
            fd = os.open(
                str(log_path),
                os.O_WRONLY | os.O_CREAT | os.O_APPEND,
                0o600  # Secure file permissions
            )
            try:
                # Acquire exclusive lock
                fcntl.flock(fd, fcntl.LOCK_EX)
                try:
                    line = entry.to_jsonl() + "\n"
                    os.write(fd, line.encode("utf-8"))
                    
                    if self.fsync_on_write:
                        os.fsync(fd)
                finally:
                    fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)
            
            # Update last hash for chain continuity
            if self.enable_hash_chain and entry.entry_hash:
                self._last_hash = entry.entry_hash
                self._save_metadata(entry.entry_hash, -1)  # -1 = unknown count
            
            return entry
    
    def get_entries(
        self,
        date: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        decision_id: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Generator[AuditEntry, None, None]:
        """Retrieve audit entries with optional filtering."""
        if date is None:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        filename = self.log_filename_pattern.replace("{date}", date)
        log_path = self.log_dir / filename
        
        if not log_path.exists():
            return
        
        with open(log_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    entry = AuditEntry.from_jsonl(line)
                    
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
                except (json.JSONDecodeError, ValueError) as e:
                    # Log warning but continue processing
                    import logging
                    logging.getLogger(__name__).warning(
                        f"Skipped malformed audit entry: {e}"
                    )
                    continue
    
    def verify_integrity(self, date: Optional[str] = None) -> bool:
        """Verify hash chain integrity of log file."""
        if not self.enable_hash_chain:
            return True
        
        if date is None:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        filename = self.log_filename_pattern.replace("{date}", date)
        log_path = self.log_dir / filename
        
        if not log_path.exists():
            return True  # Empty log is valid
        
        previous_hash = None
        line_number = 0
        
        with open(log_path, "r") as f:
            for line in f:
                line_number += 1
                line = line.strip()
                if not line:
                    continue
                
                try:
                    entry_dict = json.loads(line)
                    
                    # Check previous hash matches
                    if entry_dict.get("previous_hash") != previous_hash:
                        raise AuditLogIntegrityError(
                            f"Hash chain broken at line {line_number}. "
                            f"Expected previous_hash={previous_hash}, "
                            f"got {entry_dict.get('previous_hash')}"
                        )
                    
                    # Verify entry hash
                    stored_hash = entry_dict.get("entry_hash")
                    entry_dict["entry_hash"] = None
                    content_to_hash = self._serialize_for_hash(entry_dict)
                    computed_hash = self._compute_hash(content_to_hash)
                    
                    if computed_hash != stored_hash:
                        raise AuditLogIntegrityError(
                            f"Entry hash mismatch at line {line_number}. "
                            f"Entry may have been tampered with."
                        )
                    
                    previous_hash = stored_hash
                    
                except json.JSONDecodeError as e:
                    raise AuditLogIntegrityError(
                        f"Malformed JSON at line {line_number}: {e}"
                    )
        
        return True
    
    def get_last_hash(self) -> Optional[str]:
        """Get the hash of the last entry."""
        return self._last_hash
    
    def get_log_files(self) -> List[Path]:
        """Get list of all audit log files."""
        return sorted(self.log_dir.glob("*.jsonl"))
    
    def get_entry_count(self, date: Optional[str] = None) -> int:
        """Get count of entries in log file."""
        if date is None:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        filename = self.log_filename_pattern.replace("{date}", date)
        log_path = self.log_dir / filename
        
        if not log_path.exists():
            return 0
        
        count = 0
        with open(log_path, "r") as f:
            for line in f:
                if line.strip():
                    count += 1
        
        return count
