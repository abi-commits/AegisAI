"""Confidence Calibrator - Adult Upgrade for Confidence Agent.

This is the most important calibration work.

Key principles:
- Distrust overconfident models
- Reduce certainty when agents disagree
- Escalate more, not less
- Recalibrate if escalation rate drops sharply

No model should claim 95%+ confidence without exceptional evidence.
Disagreement between agents is a signal, not noise.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Literal, TYPE_CHECKING
import pickle

import numpy as np

if TYPE_CHECKING:
    from aegis_ai.models.calibration.isotonic import IsotonicCalibrator
    from aegis_ai.models.calibration.platt import PlattCalibrator


@dataclass
class CalibrationResult:
    """Result of confidence calibration.
    
    Attributes:
        raw_confidence: Original confidence before calibration
        calibrated_confidence: Confidence after calibration
        overconfidence_penalty: Penalty applied for overconfidence
        disagreement_penalty: Penalty applied for agent disagreement
        agreement_boost: Boost applied for strong agent agreement
        evidence_penalty: Penalty for missing evidence
        escalation_boost: Boost applied to increase escalation rate
        should_escalate: Whether the result suggests escalation
    """
    raw_confidence: float
    calibrated_confidence: float
    overconfidence_penalty: float = 0.0
    disagreement_penalty: float = 0.0
    agreement_boost: float = 0.0
    evidence_penalty: float = 0.0
    escalation_boost: float = 0.0
    should_escalate: bool = False


@dataclass  
class EscalationMetrics:
    """Metrics for monitoring escalation rate.
    
    Used to detect if escalation rate drops sharply,
    which triggers recalibration.
    """
    total_decisions: int = 0
    escalations: int = 0
    recent_decisions: int = 0
    recent_escalations: int = 0
    
    @property
    def overall_rate(self) -> float:
        """Overall escalation rate."""
        if self.total_decisions == 0:
            return 0.0
        return self.escalations / self.total_decisions
    
    @property
    def recent_rate(self) -> float:
        """Recent escalation rate (for drift detection)."""
        if self.recent_decisions == 0:
            return 0.0
        return self.recent_escalations / self.recent_decisions
    
    def record(self, escalated: bool) -> None:
        """Record a decision."""
        self.total_decisions += 1
        self.recent_decisions += 1
        if escalated:
            self.escalations += 1
            self.recent_escalations += 1
    
    def reset_recent(self) -> None:
        """Reset recent window for new period."""
        self.recent_decisions = 0
        self.recent_escalations = 0


class ConfidenceCalibrator:
    """Calibrates confidence scores with disagreement awareness.
    
    This calibrator is paranoid by design:
    - Overconfident scores get penalized
    - Disagreement between agents increases uncertainty
    - Missing evidence increases uncertainty
    - Escalation is preferred over false certainty
    
    Key thresholds are conservative:
    - Any confidence > 0.90 is suspect without strong agreement
    - Disagreement > 0.25 triggers uncertainty boost
    - Missing evidence adds cumulative penalties
    
    But when agents AGREE strongly (disagreement < 0.15), we trust them more.
    """
    
    # Overconfidence thresholds - be suspicious of high confidence
    OVERCONFIDENCE_THRESHOLD = 0.92
    OVERCONFIDENCE_PENALTY_RATE = 0.4  # How much to penalize
    
    # Disagreement thresholds
    STRONG_AGREEMENT = 0.15  # Below this = strong agreement, trust more
    DISAGREEMENT_WARNING = 0.25  # Start mild penalty
    DISAGREEMENT_CRITICAL = 0.40  # Strong penalty
    
    # Escalation parameters
    MIN_ESCALATION_RATE = 0.15  # Below this = recalibrate
    ESCALATION_BOOST_THRESHOLD = 0.65  # Below this confidence = boost escalation
    
    # Evidence penalties (reduced when agents agree)
    MISSING_DETECTION_FACTORS_PENALTY = 0.08
    MISSING_NETWORK_EVIDENCE_PENALTY = 0.05
    WEAK_BEHAVIORAL_MATCH_PENALTY = 0.06
    
    def __init__(
        self,
        isotonic_calibrator: Optional["IsotonicCalibrator"] = None,
        platt_calibrator: Optional["PlattCalibrator"] = None,
        use_isotonic: bool = True
    ):
        """Initialize confidence calibrator.
        
        Args:
            isotonic_calibrator: Pre-fitted isotonic calibrator (optional)
            platt_calibrator: Pre-fitted Platt calibrator (optional)
            use_isotonic: If True use isotonic, else Platt (when both provided)
        """
        self._isotonic = isotonic_calibrator
        self._platt = platt_calibrator
        self._use_isotonic = use_isotonic
        self._escalation_metrics = EscalationMetrics()
        self._recalibration_needed = False
    
    @property
    def escalation_metrics(self) -> EscalationMetrics:
        """Get current escalation metrics."""
        return self._escalation_metrics
    
    @property
    def recalibration_needed(self) -> bool:
        """Check if recalibration is needed due to low escalation rate."""
        return self._recalibration_needed
    
    def calibrate(
        self,
        raw_confidence: float,
        disagreement_score: float,
        detection_factors_count: int,
        network_evidence_count: int,
        behavioral_match_score: float
    ) -> CalibrationResult:
        """Calibrate a confidence score with full context.
        
        This is the main calibration method. It applies:
        1. Base calibration (isotonic or Platt)
        2. Overconfidence penalty
        3. Disagreement penalty
        4. Evidence penalties
        5. Escalation boost if needed
        
        Args:
            raw_confidence: Original confidence from agent
            disagreement_score: Disagreement between agents (0-1)
            detection_factors_count: Number of detected risk factors
            network_evidence_count: Number of network evidence links
            behavioral_match_score: Behavioral match score (0-1)
            
        Returns:
            CalibrationResult with all adjustments
        """
        # Start with raw confidence
        calibrated = raw_confidence
        
        # Track penalties
        overconfidence_penalty = 0.0
        disagreement_penalty = 0.0
        evidence_penalty = 0.0
        escalation_boost = 0.0
        
        # Step 1: Apply base calibration if available
        if self._isotonic is not None and self._use_isotonic:
            if self._isotonic.is_fitted:
                calibrated = self._isotonic.calibrate_single(calibrated)
        elif self._platt is not None:
            if self._platt.is_fitted:
                calibrated = self._platt.calibrate_single(calibrated)
        
        # Step 2: Overconfidence penalty
        # Distrust models that claim very high confidence
        # BUT: if there's strong agreement, trust it more
        if calibrated > self.OVERCONFIDENCE_THRESHOLD:
            # Penalty increases with confidence
            excess = calibrated - self.OVERCONFIDENCE_THRESHOLD
            overconfidence_penalty = excess * self.OVERCONFIDENCE_PENALTY_RATE
            
            # Stronger penalty if there's any disagreement
            if disagreement_score > self.STRONG_AGREEMENT:
                overconfidence_penalty *= (1.0 + disagreement_score)
            else:
                # Strong agreement - reduce overconfidence penalty
                overconfidence_penalty *= 0.3
            
            calibrated -= overconfidence_penalty
        
        # Step 3: Disagreement penalty OR agreement boost
        # Reduce certainty when agents disagree
        # BUT: reward strong agreement
        agreement_boost = 0.0
        
        if disagreement_score >= self.DISAGREEMENT_CRITICAL:
            # Strong penalty for high disagreement
            disagreement_penalty = 0.20 + (disagreement_score - self.DISAGREEMENT_CRITICAL) * 0.4
        elif disagreement_score >= self.DISAGREEMENT_WARNING:
            # Mild penalty for moderate disagreement
            disagreement_penalty = (disagreement_score - self.DISAGREEMENT_WARNING) * 0.4
        elif disagreement_score < self.STRONG_AGREEMENT:
            # Strong agreement = confidence boost (separate from penalty)
            agreement_boost = 0.05  # Small boost for strong agreement
        
        calibrated = calibrated - disagreement_penalty + agreement_boost
        
        # Step 4: Evidence penalties
        # Missing evidence = less confidence
        # BUT: reduced impact when agents agree strongly
        
        evidence_multiplier = 1.0
        if disagreement_score < self.STRONG_AGREEMENT:
            evidence_multiplier = 0.5  # Reduce evidence penalty when agents agree
        
        # No detection factors but model thinks there's risk
        if detection_factors_count == 0 and raw_confidence < 0.7:
            # High risk but no factors = suspicious model
            evidence_penalty += self.MISSING_DETECTION_FACTORS_PENALTY * evidence_multiplier
        
        # No network evidence - only penalize if there's disagreement
        if network_evidence_count == 0 and disagreement_score >= self.DISAGREEMENT_WARNING:
            evidence_penalty += self.MISSING_NETWORK_EVIDENCE_PENALTY * evidence_multiplier
        
        # Weak behavioral match should reduce confidence in "allow" decisions
        # Only if there's also some disagreement
        if behavioral_match_score < 0.5 and raw_confidence > 0.7 and disagreement_score >= self.STRONG_AGREEMENT:
            evidence_penalty += self.WEAK_BEHAVIORAL_MATCH_PENALTY * evidence_multiplier
        
        calibrated -= evidence_penalty
        
        # Step 5: Escalation boost
        # If confidence is below threshold AND there's disagreement, boost escalation
        # BUT: if agents strongly agree, don't over-escalate
        if calibrated < self.ESCALATION_BOOST_THRESHOLD and disagreement_score >= self.DISAGREEMENT_WARNING:
            escalation_boost = (self.ESCALATION_BOOST_THRESHOLD - calibrated) * 0.15
            calibrated -= escalation_boost  # Further reduce to trigger escalation
        
        # Clamp to valid range
        calibrated = max(0.0, min(1.0, calibrated))
        
        # Determine if should escalate (conservative threshold)
        should_escalate = calibrated < 0.75 or disagreement_score > 0.30
        
        return CalibrationResult(
            raw_confidence=raw_confidence,
            calibrated_confidence=calibrated,
            overconfidence_penalty=overconfidence_penalty,
            disagreement_penalty=disagreement_penalty,
            agreement_boost=agreement_boost,
            evidence_penalty=evidence_penalty,
            escalation_boost=escalation_boost,
            should_escalate=should_escalate
        )
    
    def record_decision(
        self,
        escalated: bool,
        window_size: int = 100
    ) -> None:
        """Record a decision for escalation rate monitoring.
        
        Args:
            escalated: Whether this decision was escalated
            window_size: Window size for recent rate calculation
        """
        self._escalation_metrics.record(escalated)
        
        # Check if escalation rate dropped
        if self._escalation_metrics.recent_decisions >= window_size:
            if self._escalation_metrics.recent_rate < self.MIN_ESCALATION_RATE:
                self._recalibration_needed = True
            self._escalation_metrics.reset_recent()
    
    
    def reset_recalibration_flag(self) -> None:
        """Reset recalibration flag after recalibration is done."""
        self._recalibration_needed = False
    
    def save(self, path: Path) -> None:
        """Save calibrator state to disk."""
        state = {
            'escalation_metrics': self._escalation_metrics,
            'recalibration_needed': self._recalibration_needed,
        }
        with open(path, 'wb') as f:
            pickle.dump(state, f)
    
    def load(self, path: Path) -> "ConfidenceCalibrator":
        """Load calibrator state from disk."""
        with open(path, 'rb') as f:
            state = pickle.load(f)
        self._escalation_metrics = state['escalation_metrics']
        self._recalibration_needed = state['recalibration_needed']
        return self
