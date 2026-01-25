"""Agent router - orchestrates parallel agent execution."""

from typing import Dict, Any, List
from dataclasses import dataclass


@dataclass
class RouterConfig:
    """Router configuration."""
    parallel_execution: bool = True
    timeout_seconds: float = 30.0


class AgentRouter:
    """Routes decisions through all agents in parallel."""
    
    def __init__(self, config: RouterConfig = None):
        self.config = config or RouterConfig()
        self.agents = {}
    
    def register_agent(self, agent_name: str, agent):
        """Register an agent."""
        self.agents[agent_name] = agent
    
    def route(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Route through all registered agents."""
        raise NotImplementedError
