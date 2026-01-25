"""Configuration management."""

from dataclasses import dataclass, field
from typing import Dict, Any
import os
from pathlib import Path


@dataclass
class Config:
    """Central configuration object."""
    
    # Environment
    environment: str = os.getenv("ENVIRONMENT", "development")
    debug: bool = os.getenv("DEBUG", "true").lower() == "true"
    
    # Paths
    project_root: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent.parent)
    log_dir: Path = field(default_factory=lambda: Path("./logs"))
    data_dir: Path = field(default_factory=lambda: Path("./data"))
    models_dir: Path = field(default_factory=lambda: Path("./models"))
    
    # Model settings
    model_config: Dict[str, Any] = field(default_factory=lambda: {
        "xgboost": {"max_depth": 6, "learning_rate": 0.1},
        "graph": {"embedding_dim": 32},
    })
    
    # Policy
    policy_file: str = "./config/policy_rules.yaml"
    
    # Audit
    audit_log_path: str = "./audit_logs.jsonl"
    
    # API
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    
    def __post_init__(self):
        """Create necessary directories."""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)
