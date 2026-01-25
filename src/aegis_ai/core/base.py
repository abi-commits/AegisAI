"""Base agent classes and contracts."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict


class AgentContract(ABC):
    """Abstract base class for agent contracts."""
    
    @abstractmethod
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute agent logic.
        
        Args:
            input_data: Standardized input for the agent
            
        Returns:
            Agent output following the contract
        """
        pass


class Agent(AgentContract):
    """Base Agent class."""
    
    def __init__(self, name: str):
        self.name = name
    
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute agent logic."""
        raise NotImplementedError
