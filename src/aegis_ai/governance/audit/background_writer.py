"""Background Audit Writer - Async audit logging for high throughput."""

import atexit, logging, queue, threading
from typing import Optional

from aegis_ai.governance.audit.store import AuditStore, FileAuditStore
from aegis_ai.governance.schemas import AuditEntry
from aegis_ai.common.constants import AuditConstants

logger = logging.getLogger(__name__)


class BackgroundAuditWriter:
    """Background writer for non-blocking audit log writes."""
    
    DEFAULT_QUEUE_SIZE = AuditConstants.QUEUE_SIZE
    DEFAULT_FLUSH_TIMEOUT = AuditConstants.FLUSH_TIMEOUT_SECONDS
    
    def __init__(
        self,
        store: Optional[AuditStore] = None,
        max_queue_size: int = DEFAULT_QUEUE_SIZE,
        flush_timeout: float = DEFAULT_FLUSH_TIMEOUT,
        sync_fallback: bool = True,
    ):
        """Initialize background audit writer.
        
        Args:
            store: Audit store backend. Creates FileAuditStore if not provided.
            max_queue_size: Maximum number of entries to buffer.
            flush_timeout: Timeout for flushing queue on shutdown.
            sync_fallback: Whether to write synchronously when queue is full.
        """
        self.store = store or FileAuditStore()
        self.max_queue_size = max_queue_size
        self.flush_timeout = flush_timeout
        self.sync_fallback = sync_fallback
        
        # Bounded queue for entries
        self._queue: queue.Queue[Optional[AuditEntry]] = queue.Queue(
            maxsize=max_queue_size
        )
        
        # Shutdown coordination
        self._shutdown_event = threading.Event()
        self._writer_thread: Optional[threading.Thread] = None
        
        # Statistics
        self._entries_written = 0
        self._entries_dropped = 0
        self._sync_fallback_count = 0
        
        # Lock for stats
        self._stats_lock = threading.Lock()
        
        # Start background writer
        self._start_writer()
        
        # Register shutdown hook
        atexit.register(self.shutdown)
    
    def _start_writer(self) -> None:
        """Start the background writer thread."""
        self._writer_thread = threading.Thread(
            target=self._writer_loop,
            name="AuditWriter",
            daemon=True,
        )
        self._writer_thread.start()
        logger.info("Background audit writer started")
    
    def _writer_loop(self) -> None:
        """Background loop that writes entries from the queue."""
        while not self._shutdown_event.is_set():
            try:
                # Wait for an entry with timeout to allow shutdown check
                entry = self._queue.get(timeout=AuditConstants.QUEUE_GET_TIMEOUT)
                
                if entry is None:
                    # Shutdown signal
                    break
                
                try:
                    self.store.append_entry(entry)
                    with self._stats_lock:
                        self._entries_written += 1
                except Exception as e:
                    logger.error(f"Failed to write audit entry: {e}")
                finally:
                    self._queue.task_done()
                    
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Unexpected error in audit writer: {e}")
        
        # Drain remaining entries on shutdown
        self._drain_queue()
        logger.info("Background audit writer stopped")
    
    def _drain_queue(self) -> None:
        """Drain remaining entries from the queue."""
        drained = 0
        while True:
            try:
                entry = self._queue.get_nowait()
                if entry is not None:
                    try:
                        self.store.append_entry(entry)
                        drained += 1
                    except Exception as e:
                        logger.error(f"Failed to write audit entry during drain: {e}")
                self._queue.task_done()
            except queue.Empty:
                break
        
        if drained > 0:
            logger.info(f"Drained {drained} audit entries during shutdown")
    
    def append_entry(self, entry: AuditEntry) -> AuditEntry:
        """Append an audit entry asynchronously.
        
        Args:
            entry: The audit entry to append
            
        Returns:
            The entry (hash fields populated by store on actual write)
            
        Note:
            If queue is full and sync_fallback is True, writes synchronously.
            If queue is full and sync_fallback is False, drops the entry.
        """
        if self._shutdown_event.is_set():
            # After shutdown, write synchronously
            return self.store.append_entry(entry)
        
        try:
            self._queue.put_nowait(entry)
            return entry
        except queue.Full:
            if self.sync_fallback:
                # Write synchronously as fallback
                with self._stats_lock:
                    self._sync_fallback_count += 1
                logger.warning("Audit queue full, writing synchronously")
                return self.store.append_entry(entry)
            else:
                # Drop the entry
                with self._stats_lock:
                    self._entries_dropped += 1
                logger.error("Audit queue full, entry dropped")
                return entry
    
    def shutdown(self, timeout: Optional[float] = None) -> None:
        """Shutdown the background writer gracefully.
        
        Args:
            timeout: Maximum time to wait for queue drain. Uses default if None.
        """
        if self._shutdown_event.is_set():
            return  # Already shutdown
        
        timeout = timeout if timeout is not None else self.flush_timeout
        
        logger.info("Shutting down background audit writer...")
        self._shutdown_event.set()
        
        # Signal writer to stop
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass  # Queue is full, writer will see shutdown event
        
        # Wait for writer thread
        if self._writer_thread and self._writer_thread.is_alive():
            self._writer_thread.join(timeout=timeout)
            if self._writer_thread.is_alive():
                logger.warning("Audit writer did not stop cleanly")
        
        logger.info(
            f"Audit writer shutdown complete. "
            f"Written: {self._entries_written}, "
            f"Dropped: {self._entries_dropped}, "
            f"Sync fallbacks: {self._sync_fallback_count}"
        )
    
    def flush(self, timeout: Optional[float] = None) -> bool:
        """Wait for all pending entries to be written.
        
        Args:
            timeout: Maximum time to wait. Blocks indefinitely if None.
            
        Returns:
            True if all entries were written, False if timeout occurred.
        """
        try:
            self._queue.join()
            return True
        except Exception:
            return False
    
    def get_stats(self) -> dict:
        """Get writer statistics."""
        with self._stats_lock:
            return {
                "entries_written": self._entries_written,
                "entries_dropped": self._entries_dropped,
                "sync_fallback_count": self._sync_fallback_count,
                "queue_size": self._queue.qsize(),
                "max_queue_size": self.max_queue_size,
            }
    
    @property
    def queue_size(self) -> int:
        """Current number of entries in the queue."""
        return self._queue.qsize()
    
    @property
    def is_running(self) -> bool:
        """Whether the background writer is running."""
        return not self._shutdown_event.is_set()
