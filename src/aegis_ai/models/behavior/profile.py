"""Behavioral profile data structures.

Defines the rolling behavioral profile maintained per user
and session embedding vectors for distance calculation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import json
from pathlib import Path

import numpy as np


@dataclass
class ProfileConfig:
    """Configuration for behavioral profiling.
    
    Attributes:
        embedding_dim: Dimension of session embedding vectors
        max_history_sessions: Maximum sessions to keep in history
        decay_factor: Exponential decay for older sessions (0-1)
        min_sessions_for_profile: Minimum sessions before profile is valid
        update_on_predict: Whether to update profile on each prediction
    """
    embedding_dim: int = 16
    max_history_sessions: int = 100
    decay_factor: float = 0.95
    min_sessions_for_profile: int = 5
    update_on_predict: bool = False


@dataclass
class SessionEmbedding:
    """Embedding vector for a single session.
    
    Features encoded:
    - Hour of login (cyclical: sin/cos)
    - Day of week (cyclical: sin/cos)
    - Device type (one-hot: desktop/mobile/tablet)
    - Auth method (one-hot: password/mfa/sso/biometric)
    - Location (lat/lon normalized)
    - Session characteristics (VPN, Tor flags)
    - Time since last login (normalized)
    """
    vector: np.ndarray
    timestamp: datetime
    session_id: str
    
    def __post_init__(self):
        """Ensure vector is numpy array."""
        if not isinstance(self.vector, np.ndarray):
            self.vector = np.array(self.vector, dtype=np.float32)


@dataclass
class BehavioralProfile:
    """Rolling behavioral profile for a user.
    
    Maintains a centroid of historical behavior and
    covariance matrix for Mahalanobis distance.
    
    Attributes:
        user_id: User this profile belongs to
        centroid: Mean embedding vector (behavioral center)
        covariance: Covariance matrix of embeddings
        session_count: Total sessions processed
        last_updated: Timestamp of last update
        history: Recent session embeddings (for rolling updates)
    """
    user_id: str
    centroid: np.ndarray
    covariance: Optional[np.ndarray] = None
    covariance_inv: Optional[np.ndarray] = None
    session_count: int = 0
    last_updated: Optional[datetime] = None
    history: list[SessionEmbedding] = field(default_factory=list)
    config: ProfileConfig = field(default_factory=ProfileConfig)
    
    def __post_init__(self):
        """Ensure arrays are numpy arrays."""
        if not isinstance(self.centroid, np.ndarray):
            self.centroid = np.array(self.centroid, dtype=np.float32)
        if self.covariance is not None and not isinstance(self.covariance, np.ndarray):
            self.covariance = np.array(self.covariance, dtype=np.float32)
    
    @property
    def is_valid(self) -> bool:
        """Check if profile has enough data to be valid."""
        return self.session_count >= self.config.min_sessions_for_profile
    
    @property
    def has_covariance(self) -> bool:
        """Check if covariance matrix is available."""
        return self.covariance is not None and self.covariance_inv is not None
    
    def update(self, embedding: SessionEmbedding) -> None:
        """Update profile with new session embedding.
        
        Uses exponential moving average for centroid
        and rolling covariance estimation.
        
        Args:
            embedding: New session embedding
        """
        # Add to history
        self.history.append(embedding)
        
        # Trim history if needed
        if len(self.history) > self.config.max_history_sessions:
            self.history = self.history[-self.config.max_history_sessions:]
        
        # Update centroid with exponential moving average
        alpha = 1.0 / (self.session_count + 1) if self.session_count < 10 else 0.1
        self.centroid = (1 - alpha) * self.centroid + alpha * embedding.vector
        
        self.session_count += 1
        self.last_updated = embedding.timestamp
        
        # Recompute covariance if enough history
        if len(self.history) >= self.config.min_sessions_for_profile:
            self._update_covariance()
    
    def _update_covariance(self) -> None:
        """Recompute covariance matrix from history."""
        if len(self.history) < 2:
            return
        
        # Stack embeddings with decay weights
        vectors = []
        weights = []
        for i, emb in enumerate(reversed(self.history)):
            vectors.append(emb.vector)
            weights.append(self.config.decay_factor ** i)
        
        vectors = np.array(vectors)
        weights = np.array(weights)
        weights /= weights.sum()
        
        # Weighted covariance
        centered = vectors - self.centroid
        self.covariance = np.cov(centered.T, aweights=weights)
        
        # Add regularization for stability
        reg = 1e-4 * np.eye(self.covariance.shape[0])
        self.covariance += reg
        
        # Compute inverse for Mahalanobis distance
        try:
            self.covariance_inv = np.linalg.inv(self.covariance)
        except np.linalg.LinAlgError:
            # Fallback to pseudo-inverse
            self.covariance_inv = np.linalg.pinv(self.covariance)
    
    @classmethod
    def create_empty(cls, user_id: str, embedding_dim: int, config: Optional[ProfileConfig] = None) -> "BehavioralProfile":
        """Create an empty profile for a new user.
        
        Args:
            user_id: User identifier
            embedding_dim: Dimension of embeddings
            config: Profile configuration
            
        Returns:
            Empty BehavioralProfile
        """
        config = config or ProfileConfig(embedding_dim=embedding_dim)
        return cls(
            user_id=user_id,
            centroid=np.zeros(embedding_dim, dtype=np.float32),
            config=config,
        )
    
    def save(self, path: Path) -> None:
        """Save profile to disk.
        
        Args:
            path: Path to save file
        """
        data = {
            "user_id": self.user_id,
            "centroid": self.centroid.tolist(),
            "covariance": self.covariance.tolist() if self.covariance is not None else None,
            "session_count": self.session_count,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "config": {
                "embedding_dim": self.config.embedding_dim,
                "max_history_sessions": self.config.max_history_sessions,
                "decay_factor": self.config.decay_factor,
                "min_sessions_for_profile": self.config.min_sessions_for_profile,
            }
        }
        
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    
    @classmethod
    def load(cls, path: Path) -> "BehavioralProfile":
        """Load profile from disk.
        
        Args:
            path: Path to profile file
            
        Returns:
            Loaded BehavioralProfile
        """
        with open(path, "r") as f:
            data = json.load(f)
        
        config = ProfileConfig(**data.get("config", {}))
        
        profile = cls(
            user_id=data["user_id"],
            centroid=np.array(data["centroid"], dtype=np.float32),
            covariance=np.array(data["covariance"], dtype=np.float32) if data.get("covariance") else None,
            session_count=data["session_count"],
            last_updated=datetime.fromisoformat(data["last_updated"]) if data.get("last_updated") else None,
            config=config,
        )
        
        if profile.covariance is not None:
            profile._update_covariance()
        
        return profile
