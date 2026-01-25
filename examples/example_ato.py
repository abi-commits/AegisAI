"""Example: End-to-end ATO detection scenario."""

from datetime import datetime
from src.aegis_ai.core.types import LoginEvent, DecisionAction
from src.aegis_ai.common.logging import get_logger

logger = get_logger(__name__)


def example_ato_scenario():
    """
    Example scenario: Account takeover attempt.
    
    1. User login from unusual location
    2. Detection agent flags anomaly
    3. Confidence agent evaluates uncertainty
    4. Explanation agent determines action
    5. Audit logged
    """
    
    # Create example login event
    event = LoginEvent(
        event_id="event_123",
        user_id="user_456",
        session_id="sess_789",
        device_id="dev_012",
        ip_address="192.168.1.100",
        geo_location="New York, USA",
        timestamp=datetime.utcnow(),
        success=False,
        additional_context={
            "failed_attempts": 3,
            "travel_flag": True,
        }
    )
    
    logger.info(f"Processing login event: {event.event_id}")
    
    # This is where the orchestration flow would:
    # 1. Run detection, behavior, network agents in parallel
    # 2. Aggregate signals
    # 3. Gate with confidence agent
    # 4. Generate decision with explanation agent
    # 5. Enforce policies
    # 6. Log to audit trail
    
    return event


if __name__ == "__main__":
    event = example_ato_scenario()
    print(f"Event processed: {event}")
