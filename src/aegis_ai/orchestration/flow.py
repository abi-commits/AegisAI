"""Decision flow - orchestrates the decision lifecycle."""

from typing import Dict, Any


class DecisionFlow:
    """Orchestrates the complete decision lifecycle.
    
    1. LoginEvent ingested
    2. Detection, Behavioral, Network agents run in parallel
    3. Signals aggregated
    4. Confidence agent evaluates uncertainty
    5. Decision fork: AI allowed -> action OR AI denied -> human review
    6. Audit log written immutably
    """
    
    def __init__(self, router, confidence_agent, explanation_agent, audit_logger, policy_engine):
        self.router = router
        self.confidence_agent = confidence_agent
        self.explanation_agent = explanation_agent
        self.audit_logger = audit_logger
        self.policy_engine = policy_engine
    
    def process(self, login_event: Dict[str, Any]) -> Dict[str, Any]:
        """Process login event through decision flow."""
        raise NotImplementedError
