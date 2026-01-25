"""Synthetic data generator for testing and demos."""

from datetime import datetime, timedelta
import random
import hashlib
from typing import List, Dict, Any


class SyntheticDataGenerator:
    """Generate synthetic login data for testing."""
    
    def __init__(self, seed: int = 42):
        random.seed(seed)
    
    def generate_login_event(self, user_id: str = None) -> Dict[str, Any]:
        """Generate a synthetic login event."""
        raise NotImplementedError
    
    def generate_user_history(self, user_id: str, num_events: int) -> List[Dict[str, Any]]:
        """Generate historical login events for a user."""
        raise NotImplementedError
