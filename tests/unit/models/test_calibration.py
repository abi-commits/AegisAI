"""Unit tests for Confidence Calibrator (Phase 4).

Testing discipline: Light but mandatory.
- One happy path test
- One edge case test  
- One weird but valid input test
"""

import pytest

from src.aegis_ai.models.calibration.confidence import (
    ConfidenceCalibrator,
    CalibrationResult,
    EscalationMetrics,
)


@pytest.fixture
def calibrator():
    """Create a ConfidenceCalibrator instance."""
    return ConfidenceCalibrator()


class TestConfidenceCalibratorHappyPath:
    """Happy path tests for ConfidenceCalibrator."""
    
    def test_strong_agreement_boosts_confidence(self, calibrator):
        """When agents agree strongly, confidence should be boosted."""
        result = calibrator.calibrate(
            raw_confidence=0.85,
            disagreement_score=0.05,  # Very low disagreement
            detection_factors_count=2,
            network_evidence_count=1,
            behavioral_match_score=0.9
        )
        
        assert isinstance(result, CalibrationResult)
        # Strong agreement should boost confidence
        assert result.agreement_boost > 0
        assert result.disagreement_penalty == 0.0
        assert result.calibrated_confidence > result.raw_confidence or \
               result.calibrated_confidence >= 0.85
    
    def test_high_disagreement_penalizes_confidence(self, calibrator):
        """When agents disagree, confidence should be reduced."""
        result = calibrator.calibrate(
            raw_confidence=0.80,
            disagreement_score=0.45,  # High disagreement
            detection_factors_count=1,
            network_evidence_count=0,
            behavioral_match_score=0.5
        )
        
        assert result.disagreement_penalty > 0
        assert result.calibrated_confidence < result.raw_confidence
        assert result.should_escalate is True


class TestConfidenceCalibratorEdgeCases:
    """Edge case tests for ConfidenceCalibrator."""
    
    def test_overconfidence_is_penalized(self, calibrator):
        """Overconfident models should be penalized."""
        result = calibrator.calibrate(
            raw_confidence=0.98,  # Very high confidence
            disagreement_score=0.20,  # Moderate disagreement
            detection_factors_count=3,
            network_evidence_count=2,
            behavioral_match_score=0.8
        )
        
        # Should apply overconfidence penalty
        assert result.overconfidence_penalty > 0
        assert result.calibrated_confidence < 0.98
    
    def test_missing_evidence_with_disagreement_penalizes(self, calibrator):
        """Missing evidence with disagreement should reduce confidence."""
        result = calibrator.calibrate(
            raw_confidence=0.70,
            disagreement_score=0.30,
            detection_factors_count=0,  # No detection factors
            network_evidence_count=0,  # No network evidence
            behavioral_match_score=0.3  # Low match
        )
        
        # Should have evidence and disagreement penalties
        assert result.calibrated_confidence < result.raw_confidence
        assert result.should_escalate is True


class TestConfidenceCalibratorWeirdButValid:
    """Weird but valid input tests for ConfidenceCalibrator."""
    
    def test_zero_confidence_stays_zero(self, calibrator):
        """Zero raw confidence should not go negative."""
        result = calibrator.calibrate(
            raw_confidence=0.0,
            disagreement_score=0.5,
            detection_factors_count=0,
            network_evidence_count=0,
            behavioral_match_score=0.0
        )
        
        assert result.calibrated_confidence >= 0.0
        assert result.should_escalate is True
    
    def test_perfect_confidence_with_perfect_agreement(self, calibrator):
        """Perfect confidence with perfect agreement should stay high."""
        result = calibrator.calibrate(
            raw_confidence=1.0,
            disagreement_score=0.0,  # Perfect agreement
            detection_factors_count=5,
            network_evidence_count=3,
            behavioral_match_score=1.0
        )
        
        # Should get agreement boost, minimal penalty
        assert result.agreement_boost > 0
        assert result.calibrated_confidence > 0.9
    
    def test_escalation_metrics_recording(self, calibrator):
        """Escalation metrics should track decisions correctly."""
        # Record some decisions
        for _ in range(5):
            calibrator.record_decision(escalated=True)
        for _ in range(5):
            calibrator.record_decision(escalated=False)
        
        metrics = calibrator.escalation_metrics
        assert metrics.total_decisions == 10
        assert metrics.escalations == 5
        assert metrics.overall_rate == 0.5


class TestPlattCalibrator:
    """Tests for Platt scaling calibrator."""
    
    def test_platt_calibrator_fit_and_calibrate(self):
        """Platt calibrator should fit and calibrate probabilities."""
        import numpy as np
        from src.aegis_ai.models.calibration.platt import PlattCalibrator
        
        calibrator = PlattCalibrator()
        
        # Generate synthetic data
        np.random.seed(42)
        y_prob = np.random.uniform(0, 1, 100)
        y_true = (y_prob > 0.5).astype(int)
        
        # Fit
        calibrator.fit(y_prob, y_true)
        assert calibrator.is_fitted
        
        # Calibrate
        calibrated = calibrator.calibrate(y_prob)
        assert len(calibrated) == len(y_prob)
        assert all(0 <= p <= 1 for p in calibrated)
    
    def test_platt_single_calibration(self):
        """Platt calibrator should handle single value calibration."""
        import numpy as np
        from src.aegis_ai.models.calibration.platt import PlattCalibrator
        
        calibrator = PlattCalibrator()
        
        np.random.seed(42)
        y_prob = np.random.uniform(0, 1, 100)
        y_true = (y_prob > 0.5).astype(int)
        calibrator.fit(y_prob, y_true)
        
        result = calibrator.calibrate_single(0.7)
        assert 0.0 <= result <= 1.0
