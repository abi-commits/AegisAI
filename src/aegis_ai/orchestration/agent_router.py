"""Agent Router - Parallel, Blind, Fair Agent Invocation.

This module orchestrates agent execution with strict isolation.
No agent sees another agent's output during execution.

Design principles:
- Agents run in parallel (conceptually blind to each other)
- No agent can influence another's input
- All agents receive the same validated input
- Failures are isolated and tracked
"""

from dataclasses import dataclass
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.aegis_ai.orchestration.decision_context import InputContext, AgentOutputs
from src.aegis_ai.agents.detection.agent import DetectionAgent
from src.aegis_ai.agents.detection.schema import DetectionOutput
from src.aegis_ai.agents.behavior.agent import BehaviorAgent
from src.aegis_ai.agents.behavior.schema import BehavioralOutput
from src.aegis_ai.agents.network.agent import NetworkAgent
from src.aegis_ai.agents.network.schema import NetworkOutput
from src.aegis_ai.agents.confidence.agent import ConfidenceAgent
from src.aegis_ai.agents.confidence.schema import ConfidenceOutput
from src.aegis_ai.agents.explanation.agent import ExplanationAgent
from src.aegis_ai.agents.explanation.schema import ExplanationOutput


@dataclass
class AgentError:
    """Structured error from agent execution."""
    agent_name: str
    error_type: str
    error_message: str


@dataclass
class RouterResult:
    """Result of agent routing.
    
    Contains either successful outputs or error information.
    """
    success: bool
    outputs: Optional[AgentOutputs] = None
    errors: Optional[list[AgentError]] = None
    
    def __post_init__(self):
        if self.errors is None:
            object.__setattr__(self, 'errors', [])


class AgentRouter:
    """Routes input to agents and collects outputs.
    
    Execution model:
    1. Detection, Behavioral, Network agents run in parallel (independent)
    2. Confidence agent runs after (needs their outputs)
    3. Explanation agent runs last (needs confidence decision)
    
    Agents are instantiated fresh for each invocation.
    No shared state between invocations.
    """
    
    def __init__(self, max_workers: int = 3):
        """Initialize router.
        
        Args:
            max_workers: Maximum parallel agent executions
        """
        self.max_workers = max_workers
    
    def route(self, input_context: InputContext) -> RouterResult:
        """Route input through all agents and collect outputs.
        
        Args:
            input_context: Validated input context
            
        Returns:
            RouterResult with agent outputs or errors
        """
        errors: list[AgentError] = []
        
        # Phase 1: Run independent agents in parallel
        detection_output: Optional[DetectionOutput] = None
        behavioral_output: Optional[BehavioralOutput] = None
        network_output: Optional[NetworkOutput] = None
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all independent agents
            futures = {
                executor.submit(
                    self._run_detection,
                    input_context
                ): "detection",
                executor.submit(
                    self._run_behavioral,
                    input_context
                ): "behavioral",
                executor.submit(
                    self._run_network,
                    input_context
                ): "network",
            }
            
            # Collect results
            for future in as_completed(futures):
                agent_name = futures[future]
                try:
                    result = future.result()
                    if agent_name == "detection":
                        detection_output = result
                    elif agent_name == "behavioral":
                        behavioral_output = result
                    elif agent_name == "network":
                        network_output = result
                except Exception as e:
                    errors.append(AgentError(
                        agent_name=agent_name,
                        error_type=type(e).__name__,
                        error_message=str(e)
                    ))
        
        # Check for failures in phase 1
        if detection_output is None or behavioral_output is None or network_output is None:
            return RouterResult(success=False, errors=errors)
        
        # Phase 2: Run confidence agent (needs phase 1 outputs)
        try:
            confidence_output = self._run_confidence(
                detection_output,
                behavioral_output,
                network_output
            )
        except Exception as e:
            errors.append(AgentError(
                agent_name="confidence",
                error_type=type(e).__name__,
                error_message=str(e)
            ))
            return RouterResult(success=False, errors=errors)
        
        # Phase 3: Run explanation agent (needs all previous outputs)
        try:
            explanation_output = self._run_explanation(
                detection_output,
                behavioral_output,
                network_output,
                confidence_output
            )
        except Exception as e:
            errors.append(AgentError(
                agent_name="explanation",
                error_type=type(e).__name__,
                error_message=str(e)
            ))
            return RouterResult(success=False, errors=errors)
        
        # All agents succeeded
        outputs = AgentOutputs(
            detection=detection_output,
            behavioral=behavioral_output,
            network=network_output,
            confidence=confidence_output,
            explanation=explanation_output
        )
        
        return RouterResult(success=True, outputs=outputs)
    
    def _run_detection(self, input_context: InputContext) -> DetectionOutput:
        """Run detection agent with fresh instance."""
        agent = DetectionAgent()
        return agent.analyze(
            login_event=input_context.login_event,
            session=input_context.session,
            device=input_context.device
        )
    
    def _run_behavioral(self, input_context: InputContext) -> BehavioralOutput:
        """Run behavioral agent with fresh instance."""
        agent = BehaviorAgent()
        return agent.analyze(
            login_event=input_context.login_event,
            session=input_context.session,
            user=input_context.user
        )
    
    def _run_network(self, input_context: InputContext) -> NetworkOutput:
        """Run network agent with fresh instance."""
        agent = NetworkAgent()
        return agent.analyze(
            session=input_context.session,
            device=input_context.device
        )
    
    def _run_confidence(
        self,
        detection: DetectionOutput,
        behavioral: BehavioralOutput,
        network: NetworkOutput
    ) -> ConfidenceOutput:
        """Run confidence agent with fresh instance."""
        agent = ConfidenceAgent()
        return agent.evaluate(
            detection_output=detection,
            behavioral_output=behavioral,
            network_output=network
        )
    
    def _run_explanation(
        self,
        detection: DetectionOutput,
        behavioral: BehavioralOutput,
        network: NetworkOutput,
        confidence: ConfidenceOutput
    ) -> ExplanationOutput:
        """Run explanation agent with fresh instance."""
        agent = ExplanationAgent()
        return agent.generate(
            detection_output=detection,
            behavioral_output=behavioral,
            network_output=network,
            confidence_output=confidence
        )
