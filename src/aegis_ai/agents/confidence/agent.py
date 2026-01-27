"""Confidence Agent - The Gatekeeper.

Phase 4 Upgrades:
- Platt scaling / isotonic regression for calibration
- Disagreement-aware penalty
- Distrust overconfident models
- Reduce certainty when agents disagree
- Escalate more, not less
- Recalibrate if escalation rate drops sharply
"""

from typing import Literal, Optional
from src.aegis_ai.agents.detection.schema import DetectionOutput
from src.aegis_ai.agents.behavior.schema import BehavioralOutput
from src.aegis_ai.agents.network.schema import NetworkOutput
from src.aegis_ai.agents.confidence.schema import ConfidenceOutput, CalibrationInfo
from src.aegis_ai.models.calibration import ConfidenceCalibrator


class ConfidenceAgent:
    """Confidence Agent - The Gatekeeper."""
    
    # Thresholds for decision permission (BALANCED)
    HIGH_CONFIDENCE_THRESHOLD = 0.65  # Above this = AI_ALLOWED (was 0.75)
    LOW_DISAGREEMENT_THRESHOLD = 0.35  # Below this = agents agree (was 0.30)
    
    # Penalties - More balanced for legitimate cases
    MISSING_EVIDENCE_PENALTY = 0.10  # Reduced from 0.20
    HIGH_DISAGREEMENT_PENALTY = 0.20  # Reduced from 0.30
    
    # Overconfidence thresholds
    OVERCONFIDENCE_THRESHOLD = 0.95
    OVERCONFIDENCE_PENALTY_RATE = 0.30
    
    def __init__(
        self,
        calibrator: Optional["ConfidenceCalibrator"] = None,
        use_calibration: bool = True
    ):
        """Initialize Confidence Agent.
        """
        self._calibrator = calibrator
        self._use_calibration = use_calibration    
    
    def evaluate(
        self,
        detection_output: DetectionOutput,
        behavioral_output: BehavioralOutput,
        network_output: NetworkOutput
    ) -> ConfidenceOutput:
        """Evaluate whether AI is allowed to decide.
        Returns:
            ConfidenceOutput with final_confidence, decision_permission, 
            disagreement_score, and calibration info
        """
        # Collect scores from all agents
        scores = [
            detection_output.risk_signal_score,
            1.0 - behavioral_output.behavioral_match_score,  # Invert: low match = high risk
            network_output.network_risk_score
        ]
        
        # Calculate disagreement as variance-based metric
        disagreement_score = self._calculate_disagreement(scores)
        
        # Calculate raw confidence before calibration
        raw_confidence = self._calculate_raw_confidence(
            detection_output=detection_output,
            behavioral_output=behavioral_output,
            network_output=network_output,
            disagreement_score=disagreement_score
        )
        
        # Apply calibration if available
        calibration_info = None
        escalation_reason = None
        
        if self._use_calibration and self._calibrator is not None:
            calibration_result = self._calibrator.calibrate(
                raw_confidence=raw_confidence,
                disagreement_score=disagreement_score,
                detection_factors_count=len(detection_output.risk_factors),
                network_evidence_count=len(network_output.evidence_links),
                behavioral_match_score=behavioral_output.behavioral_match_score
            )
            
            final_confidence = calibration_result.calibrated_confidence
            
            calibration_info = CalibrationInfo(
                raw_confidence=calibration_result.raw_confidence,
                overconfidence_penalty=calibration_result.overconfidence_penalty,
                disagreement_penalty=calibration_result.disagreement_penalty,
                agreement_boost=calibration_result.agreement_boost,
                evidence_penalty=calibration_result.evidence_penalty,
                escalation_boost=calibration_result.escalation_boost
            )
            
            # Determine escalation reason
            if calibration_result.should_escalate:
                if calibration_result.disagreement_penalty > 0.1:
                    escalation_reason = "HIGH_DISAGREEMENT"
                elif calibration_result.overconfidence_penalty > 0.05:
                    escalation_reason = "OVERCONFIDENCE_DETECTED"
                elif calibration_result.evidence_penalty > 0.1:
                    escalation_reason = "INSUFFICIENT_EVIDENCE"
                else:
                    escalation_reason = "LOW_CONFIDENCE"
        else:
            final_confidence = raw_confidence
        
        # Check for CLEAR-CUT fraud: Detection + Behavioral agree on high risk
        # Even if Network has no data, we can be confident in obvious fraud
        is_clear_cut_fraud = self._is_clear_cut_fraud(
            detection_output, behavioral_output, network_output
        )
        
        # Determine decision permission (CONSERVATIVE, but pragmatic for clear fraud)
        decision_permission: Literal["AI_ALLOWED", "HUMAN_REQUIRED"]
        
        if is_clear_cut_fraud:
            # Clear-cut fraud: AI can decide even with lower confidence
            decision_permission = "AI_ALLOWED"
        elif final_confidence >= self.HIGH_CONFIDENCE_THRESHOLD:
            if disagreement_score < self.LOW_DISAGREEMENT_THRESHOLD:
                decision_permission = "AI_ALLOWED"
            else:
                # High confidence but high disagreement = need human
                decision_permission = "HUMAN_REQUIRED"
                if escalation_reason is None:
                    escalation_reason = "HIGH_DISAGREEMENT"
        else:
            # Low confidence = need human
            decision_permission = "HUMAN_REQUIRED"
            if escalation_reason is None:
                escalation_reason = "LOW_CONFIDENCE"
        
        # Record decision for escalation rate monitoring
        if self._calibrator is not None:
            self._calibrator.record_decision(
                escalated=(decision_permission == "HUMAN_REQUIRED")
            )
        
        return ConfidenceOutput(
            final_confidence=final_confidence,
            decision_permission=decision_permission,
            disagreement_score=disagreement_score,
            calibration_info=calibration_info,
            escalation_reason=escalation_reason
        )
    
    def _calculate_raw_confidence(
        self,
        detection_output: DetectionOutput,
        behavioral_output: BehavioralOutput,
        network_output: NetworkOutput,
        disagreement_score: float
    ) -> float:
        """Calculate raw confidence before calibration.
        
        Confidence reflects how certain we are about the risk assessment,
        not the risk level itself. High confidence means agents agree
        and we have good evidence. Low confidence means uncertainty.
        """
        # Base confidence starts high and gets penalized for problems
        base_confidence = 0.90
        
        # Reduce confidence based on disagreement
        disagreement_penalty = disagreement_score * 0.4
        
        # Penalize only when we have high risk but weak evidence
        evidence_penalty = 0.0
        
        # High risk + no factors = suspicious, reduce confidence
        if detection_output.risk_signal_score > 0.5 and len(detection_output.risk_factors) == 0:
            evidence_penalty += self.MISSING_EVIDENCE_PENALTY
        
        # High network risk + no evidence = suspicious, reduce confidence
        if network_output.network_risk_score > 0.5 and len(network_output.evidence_links) == 0:
            evidence_penalty += self.MISSING_EVIDENCE_PENALTY
        
        # High disagreement gets extra penalty
        if disagreement_score > self.LOW_DISAGREEMENT_THRESHOLD:
            evidence_penalty += self.HIGH_DISAGREEMENT_PENALTY
        
        # BOOST confidence when everything looks clean and consistent
        # Low risk + high behavioral match + agents agree = high confidence
        agreement_boost = 0.0
        if (detection_output.risk_signal_score < 0.3 and 
            behavioral_output.behavioral_match_score > 0.7 and
            network_output.network_risk_score < 0.3 and
            disagreement_score < 0.2):
            agreement_boost = 0.10  # Boost for clean cases
        
        # Calculate raw confidence
        raw_confidence = base_confidence - disagreement_penalty - evidence_penalty + agreement_boost
        raw_confidence = max(0.0, min(1.0, raw_confidence))
        
        return raw_confidence
    
    def _is_clear_cut_fraud(
        self,
        detection: DetectionOutput,
        behavioral: BehavioralOutput,
        network: NetworkOutput
    ) -> bool:
        """Check if this is a clear-cut fraud case.
        
        Clear-cut fraud means:
        - Detection has very high risk (>= 0.95) with strong signals
        - Behavioral shows significant deviations (match < 0.4)
        - Multiple risk factors present
        
        Network agent missing data should NOT block obvious fraud decisions.
        """
        # Detection must be very confident
        if detection.risk_signal_score < 0.95:
            return False
        
        # Behavioral must show deviation (low match = suspicious)
        if behavioral.behavioral_match_score > 0.40:
            return False
        
        # Must have multiple risk factors (not just one signal)
        if len(detection.risk_factors) < 3:
            return False
        
        # Must have behavioral deviations detected
        if not behavioral.deviation_summary or len(behavioral.deviation_summary) < 2:
            return False
        
        return True
    
    def _calculate_disagreement(self, scores: list[float]) -> float:
        """Calculate disagreement score between agent outputs.
        """
        if len(scores) < 2:
            return 0.0
        
        mean = sum(scores) / len(scores)
        variance = sum((s - mean) ** 2 for s in scores) / len(scores)
        std_dev = variance ** 0.5
        
        # Normalize to 0-1 range
        # Max possible std_dev for 0-1 values is 0.5 (all at 0 and 1)
        max_std_dev = 0.5
        normalized_disagreement = min(1.0, std_dev / max_std_dev)
        
        return normalized_disagreement    
    
    @property
    def recalibration_needed(self) -> bool:
        """Check if recalibration is needed."""
        if self._calibrator is None:
            return False
        return self._calibrator.recalibration_needed
