"""Login Evaluation Service - Core business logic for login evaluation.

This service orchestrates the decision flow and audit logging,
providing a clean interface for the API layer.

Design principles:
- Clean separation between API and domain logic
- Configurable audit logging (sync or background)
- Graceful error handling with audit trail
- No internal details exposed through responses
"""

import logging
import os
from typing import Optional
from uuid import uuid4

from aegis_ai.api.schemas import (
    EvaluateLoginRequest,
    EvaluateLoginResponse,
)
from aegis_ai.data.schemas.login_event import LoginEvent
from aegis_ai.data.schemas.session import Session, GeoLocation
from aegis_ai.data.schemas.device import Device
from aegis_ai.data.schemas.user import User
from aegis_ai.orchestration.decision_context import InputContext
from aegis_ai.orchestration.decision_flow import DecisionFlow
from aegis_ai.governance.audit import AuditLogger
from aegis_ai.governance.schemas import AuditEntry


logger = logging.getLogger(__name__)


class LoginEvaluationService:
    """Service for evaluating login attempts.
    
    Orchestrates:
    1. Input transformation from API schema to domain models
    2. Decision flow execution
    3. Audit logging
    4. Response transformation (hiding internal details)
    
    Error Handling:
    - All evaluation paths produce a valid response
    - Agent failures result in escalation, not errors
    - Audit logging failures are logged but don't fail the request
    """
    
    POLICY_VERSION = os.environ.get("AEGIS_POLICY_VERSION", "1.0.0")
    
    def __init__(
        self,
        decision_flow: Optional[DecisionFlow] = None,
        audit_logger: Optional[AuditLogger] = None,
        use_background_audit: bool = False,
    ):
        """Initialize the service.
        
        Args:
            decision_flow: Decision flow orchestrator. Created if not provided.
            audit_logger: Audit logger. Created if not provided.
            use_background_audit: Whether to use background audit writing.
        """
        self.decision_flow = decision_flow or DecisionFlow()
        self.audit_logger = audit_logger or AuditLogger(
            use_background_writer=use_background_audit
        )
    
    def shutdown(self) -> None:
        """Shutdown the service and flush pending audit writes."""
        if self.audit_logger is not None:
            self.audit_logger.shutdown()
            logger.info("LoginEvaluationService audit logger shutdown complete")
    
    def evaluate(self, request: EvaluateLoginRequest) -> EvaluateLoginResponse:
        """Evaluate a login attempt.
        
        Args:
            request: The login evaluation request
            
        Returns:
            EvaluateLoginResponse with decision, confidence, explanation,
            escalation_flag, and audit_id. No internal agent outputs exposed.
            
        Note:
            This method never raises exceptions for normal operation.
            Agent failures are handled gracefully as escalations.
        """
        # Transform API request to domain models
        input_context = self._transform_to_input_context(request)
        
        # Execute decision flow (handles agent failures internally)
        decision_context = self.decision_flow.process(input_context)
        
        # Get the final decision
        decision = decision_context.final_decision
        if decision is None:
            # Should never happen with proper DecisionFlow, but handle defensively
            logger.error("Decision flow completed without a decision")
            # Create a fallback escalation response
            return self._create_fallback_escalation(input_context)
        
        # Determine escalation flag
        escalation_flag = (
            decision.action == "ESCALATE" or 
            decision.decided_by == "HUMAN_REQUIRED"
        )
        
        # Log to audit (with full internal details for compliance)
        try:
            audit_entry = self._log_to_audit(decision_context)
            audit_id = audit_entry.entry_id
        except Exception as e:
            # Audit failure should not fail the request
            logger.error(f"Failed to write audit entry: {e}")
            audit_id = f"aud_failed_{uuid4().hex[:8]}"
        
        # Return sanitized response (NO internal agent outputs)
        return EvaluateLoginResponse(
            decision=decision.action,
            confidence=decision.confidence_score,
            explanation=decision.explanation,
            escalation_flag=escalation_flag,
            audit_id=audit_id,
        )
    
    def _create_fallback_escalation(
        self, input_context: InputContext
    ) -> EvaluateLoginResponse:
        """Create a fallback escalation response when decision flow fails unexpectedly."""
        fallback_audit_id = f"aud_fallback_{uuid4().hex[:8]}"
        
        # Try to log the fallback
        try:
            entry = self.audit_logger.log_escalation(
                decision_id=f"dec_fallback_{uuid4().hex[:8]}",
                session_id=input_context.session.session_id,
                user_id=input_context.user.user_id,
                escalation_reason="SYSTEM_FALLBACK",
                confidence_score=0.0,
                policy_version=self.POLICY_VERSION,
                metadata={"fallback": True},
            )
            fallback_audit_id = entry.entry_id
        except Exception as e:
            logger.error(f"Failed to log fallback escalation: {e}")
        
        return EvaluateLoginResponse(
            decision="ESCALATE",
            confidence=0.0,
            explanation="System escalation: Unable to process request. Human review required.",
            escalation_flag=True,
            audit_id=fallback_audit_id,
        )
    
    def _transform_to_input_context(
        self, request: EvaluateLoginRequest
    ) -> InputContext:
        """Transform API request to domain InputContext.
        
        Args:
            request: The API request
            
        Returns:
            InputContext with validated domain models
        """
        # Transform GeoLocation
        geo = GeoLocation(
            city=request.session.geo_location.city,
            country=request.session.geo_location.country,
            latitude=request.session.geo_location.latitude,
            longitude=request.session.geo_location.longitude,
        )
        
        # Transform Session
        session = Session(
            session_id=request.session.session_id,
            user_id=request.user.user_id,
            device_id=request.session.device_id,
            ip_address=request.session.ip_address,
            geo_location=geo,
            start_time=request.session.start_time,
            is_vpn=request.session.is_vpn,
            is_tor=request.session.is_tor,
        )
        
        # Transform Device
        device = Device(
            device_id=request.device.device_id,
            device_type=request.device.device_type,
            os=request.device.os,
            browser=request.device.browser,
            is_known=request.device.is_known,
            first_seen_at=request.device.first_seen_at,
        )
        
        # Transform User
        user = User(
            user_id=request.user.user_id,
            account_age_days=request.user.account_age_days,
            home_country=request.user.home_country,
            home_city=request.user.home_city,
            typical_login_hour_start=request.user.typical_login_hour_start,
            typical_login_hour_end=request.user.typical_login_hour_end,
        )
        
        # Transform LoginEvent
        login_event = LoginEvent(
            event_id=request.login_event.event_id,
            session_id=request.session.session_id,
            user_id=request.user.user_id,
            timestamp=request.login_event.timestamp,
            success=request.login_event.success,
            auth_method=request.login_event.auth_method,
            failed_attempts_before=request.login_event.failed_attempts_before,
            time_since_last_login_hours=request.login_event.time_since_last_login_hours,
            is_new_device=request.login_event.is_new_device,
            is_new_ip=request.login_event.is_new_ip,
            is_new_location=request.login_event.is_new_location,
        )
        
        return InputContext(
            login_event=login_event,
            session=session,
            device=device,
            user=user,
        )
    
    def _log_to_audit(self, decision_context) -> "AuditEntry":
        """Log decision to audit trail.
        
        Internal agent outputs are logged for compliance and debugging,
        but never exposed through the API response.
        
        Args:
            decision_context: The complete decision context
            
        Returns:
            The created audit entry
        """
        decision = decision_context.final_decision
        agent_outputs = decision_context.agent_outputs
        
        # Prepare agent outputs for audit (internal use only)
        agent_outputs_dict = None
        if agent_outputs is not None:
            agent_outputs_dict = {
                "detection": {
                    "risk_signal_score": agent_outputs.detection.risk_signal_score,
                    "risk_factors": agent_outputs.detection.risk_factors,
                },
                "behavioral": {
                    "behavioral_match_score": agent_outputs.behavioral.behavioral_match_score,
                    "deviation_summary": agent_outputs.behavioral.deviation_summary,
                },
                "network": {
                    "network_risk_score": agent_outputs.network.network_risk_score,
                    "evidence_links": agent_outputs.network.evidence_links,
                },
                "confidence": {
                    "final_confidence": agent_outputs.confidence.final_confidence,
                    "disagreement_score": agent_outputs.confidence.disagreement_score,
                    "decision_permission": agent_outputs.confidence.decision_permission,
                },
                "explanation": {
                    "recommended_action": agent_outputs.explanation.recommended_action,
                },
            }
        
        # Log to audit
        audit_entry = self.audit_logger.log_decision(
            decision_id=decision.decision_id,
            session_id=decision.session_id,
            user_id=decision.user_id,
            action=decision.action,
            confidence_score=decision.confidence_score,
            decided_by=decision.decided_by,
            policy_version=self.POLICY_VERSION,
            agent_outputs=agent_outputs_dict,
            metadata={
                "detection_score": decision.detection_score,
                "behavioral_score": decision.behavioral_score,
                "network_score": decision.network_score,
                "disagreement_score": decision.disagreement_score,
            },
        )
        
        return audit_entry
