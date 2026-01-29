"""Agent Router - Parallel, Blind, Fair Agent Invocation."""

import atexit
import logging
from dataclasses import dataclass
from typing import Callable, Optional, Protocol
from concurrent.futures import ThreadPoolExecutor, as_completed

from aegis_ai.orchestration.decision_context import InputContext, AgentOutputs
from aegis_ai.agents.detection.agent import DetectionAgent
from aegis_ai.agents.detection.schema import DetectionOutput
from aegis_ai.agents.behavior.agent import BehaviorAgent
from aegis_ai.agents.behavior.schema import BehavioralOutput
from aegis_ai.agents.network.agent import NetworkAgent
from aegis_ai.agents.network.schema import NetworkOutput
from aegis_ai.agents.confidence.agent import ConfidenceAgent
from aegis_ai.agents.confidence.schema import ConfidenceOutput
from aegis_ai.agents.explanation.agent import ExplanationAgent
from aegis_ai.agents.explanation.schema import ExplanationOutput


logger = logging.getLogger(__name__)


# Type aliases for agent factories
DetectionAgentFactory = Callable[[], DetectionAgent]
BehaviorAgentFactory = Callable[[], BehaviorAgent]
NetworkAgentFactory = Callable[[], NetworkAgent]
ConfidenceAgentFactory = Callable[[], ConfidenceAgent]
ExplanationAgentFactory = Callable[[], ExplanationAgent]


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


# Module-level shared executor for performance
_shared_executor: Optional[ThreadPoolExecutor] = None
_executor_lock = None

def _get_shared_executor(max_workers: int = 3) -> ThreadPoolExecutor:
    """Get or create the shared thread pool executor.
    
    Reuses a module-level executor to avoid thread creation overhead per request.
    """
    global _shared_executor
    
    if _shared_executor is None:
        _shared_executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="AgentWorker"
        )
        atexit.register(_shutdown_shared_executor)
        logger.info(f"Created shared agent executor with {max_workers} workers")
    
    return _shared_executor


def _shutdown_shared_executor() -> None:
    """Shutdown the shared executor on process exit."""
    global _shared_executor
    if _shared_executor is not None:
        _shared_executor.shutdown(wait=True, cancel_futures=False)
        logger.info("Shared agent executor shutdown complete")
        _shared_executor = None


class AgentRouter:
    """Routes input to agents and collects outputs.
    
    Execution model:
    1. Detection, Behavioral, Network agents run in parallel (independent)
    2. Confidence agent runs after (needs their outputs)
    3. Explanation agent runs last (needs confidence decision)
    
    Features:
    - Reuses a shared thread pool executor for performance
    - Injectable agent factories for testing
    - Structured error collection
    """
    
    def __init__(
        self,
        max_workers: int = 3,
        executor: Optional[ThreadPoolExecutor] = None,
        detection_factory: Optional[DetectionAgentFactory] = None,
        behavior_factory: Optional[BehaviorAgentFactory] = None,
        network_factory: Optional[NetworkAgentFactory] = None,
        confidence_factory: Optional[ConfidenceAgentFactory] = None,
        explanation_factory: Optional[ExplanationAgentFactory] = None,
    ):
        """Initialize router.
        
        Args:
            max_workers: Maximum parallel agent executions (if using shared executor)
            executor: Custom executor. Uses shared executor if not provided.
            detection_factory: Factory for DetectionAgent. Uses default if not provided.
            behavior_factory: Factory for BehaviorAgent. Uses default if not provided.
            network_factory: Factory for NetworkAgent. Uses default if not provided.
            confidence_factory: Factory for ConfidenceAgent. Uses default if not provided.
            explanation_factory: Factory for ExplanationAgent. Uses default if not provided.
        """
        self.max_workers = max_workers
        self._executor = executor
        
        # Agent factories (allow injection for testing)
        self._detection_factory = detection_factory or DetectionAgent
        self._behavior_factory = behavior_factory or BehaviorAgent
        self._network_factory = network_factory or NetworkAgent
        self._confidence_factory = confidence_factory or ConfidenceAgent
        self._explanation_factory = explanation_factory or ExplanationAgent
    
    def _get_executor(self) -> ThreadPoolExecutor:
        """Get the executor to use for parallel agent execution."""
        if self._executor is not None:
            return self._executor
        return _get_shared_executor(self.max_workers)
    
    def route(self, input_context: InputContext) -> RouterResult:
        """Route input through all agents and collect outputs.
        
        Args:
            input_context: Validated input context
            
        Returns:
            RouterResult with agent outputs or errors
        """
        errors: list[AgentError] = []
        executor = self._get_executor()
        
        # Phase 1: Run independent agents in parallel
        detection_output: Optional[DetectionOutput] = None
        behavioral_output: Optional[BehavioralOutput] = None
        network_output: Optional[NetworkOutput] = None
        
        # Submit all independent agents to the shared executor
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
                logger.warning(
                    f"Agent {agent_name} failed: {type(e).__name__}: {e}"
                )
                errors.append(AgentError(
                    agent_name=agent_name,
                    error_type=type(e).__name__,
                    error_message=str(e)
                ))
        
        # Check for failures in phase 1
        if detection_output is None or behavioral_output is None or network_output is None:
            logger.error(
                f"Phase 1 agent failures: {[e.agent_name for e in errors]}"
            )
            return RouterResult(success=False, errors=errors)
        
        # Phase 2: Run confidence agent (needs phase 1 outputs)
        try:
            confidence_output = self._run_confidence(
                detection_output,
                behavioral_output,
                network_output
            )
        except Exception as e:
            logger.warning(f"Confidence agent failed: {type(e).__name__}: {e}")
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
            logger.warning(f"Explanation agent failed: {type(e).__name__}: {e}")
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
        """Run detection agent using factory."""
        agent = self._detection_factory()
        return agent.analyze(
            login_event=input_context.login_event,
            session=input_context.session,
            device=input_context.device
        )
    
    def _run_behavioral(self, input_context: InputContext) -> BehavioralOutput:
        """Run behavioral agent using factory."""
        agent = self._behavior_factory()
        return agent.analyze(
            login_event=input_context.login_event,
            session=input_context.session,
            user=input_context.user
        )
    
    def _run_network(self, input_context: InputContext) -> NetworkOutput:
        """Run network agent using factory."""
        agent = self._network_factory()
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
        """Run confidence agent using factory."""
        agent = self._confidence_factory()
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
        """Run explanation agent using factory."""
        agent = self._explanation_factory()
        return agent.generate(
            detection_output=detection,
            behavioral_output=behavioral,
            network_output=network,
            confidence_output=confidence
        )


def shutdown_executor() -> None:
    """Explicitly shutdown the shared executor.
    
    Call this during application shutdown for clean termination.
    """
    _shutdown_shared_executor()
