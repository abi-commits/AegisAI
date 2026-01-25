"""Audit logger - immutable logging of all decisions."""

from datetime import datetime
from typing import Dict, Any, List
import json


class AuditLogger:
    """Records all decisions immutably in JSONL format."""
    
    def __init__(self, log_path: str = None):
        self.log_path = log_path or "./audit_logs.jsonl"
    
    def log_decision(self, decision_record: Dict[str, Any]) -> None:
        """Log a decision immutably."""
        raise NotImplementedError
    
    def get_history(self, decision_id: str = None) -> List[Dict[str, Any]]:
        """Retrieve decision history."""
        raise NotImplementedError
