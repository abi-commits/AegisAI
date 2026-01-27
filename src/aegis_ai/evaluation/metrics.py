"""Evaluation Metrics - What Actually Matters.

Track the metrics that reflect reality, not just model accuracy:
- False positive rate (hurting legitimate users)
- Escalation rate (AI restraint working)
- Human override rate (system calibration)
- Confidence calibration error (honesty about uncertainty)
- Policy violation count (should be zero)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Literal, Optional
from datetime import datetime
import math


@dataclass
class EvaluationMetrics:
    """Container for all evaluation metrics."""
    # Ground truth tracking
    total_events: int = 0
    total_legit: int = 0
    total_ato: int = 0
    
    # Decision tracking
    true_positives: int = 0      # ATO correctly identified
    true_negatives: int = 0      # Legit correctly allowed
    false_positives: int = 0     # Legit wrongly blocked/challenged
    false_negatives: int = 0     # ATO wrongly allowed
    
    # Action distribution
    allowed_count: int = 0
    blocked_count: int = 0
    challenged_count: int = 0
    escalated_count: int = 0
    
    # Human-in-the-loop tracking
    human_required_count: int = 0  # AI refused to decide
    human_override_count: int = 0  # Human changed AI decision
    
    # Policy tracking
    policy_violation_count: int = 0  # Should be zero
    
    # Confidence calibration
    confidence_scores: List[float] = field(default_factory=list)
    calibration_bins: Dict[str, List[float]] = field(default_factory=dict)
    
    def add_result(
        self,
        is_ato: bool,
        action: Literal["ALLOW", "BLOCK", "CHALLENGE", "ESCALATE"],
        decided_by: Literal["AI", "HUMAN_REQUIRED"],
        confidence: float,
        had_policy_violation: bool = False,
        was_overridden: bool = False
    ) -> None:
        """Record a single evaluation result."""
        self.total_events += 1
        self.confidence_scores.append(confidence)
        
        # Track ground truth
        if is_ato:
            self.total_ato += 1
        else:
            self.total_legit += 1
        
        # Track actions
        if action == "ALLOW":
            self.allowed_count += 1
        elif action == "BLOCK":
            self.blocked_count += 1
        elif action == "CHALLENGE":
            self.challenged_count += 1
        elif action == "ESCALATE":
            self.escalated_count += 1
        
        # Track decision source
        if decided_by == "HUMAN_REQUIRED":
            self.human_required_count += 1
        
        # Track overrides
        if was_overridden:
            self.human_override_count += 1
        
        # Track policy violations
        if had_policy_violation:
            self.policy_violation_count += 1
        
        # Classify outcome (considering ESCALATE as "handled correctly")
        if is_ato:
            # ATO case
            if action in ["BLOCK", "CHALLENGE", "ESCALATE"]:
                self.true_positives += 1
            else:
                self.false_negatives += 1  # ATO was allowed through
        else:
            # Legitimate case
            if action == "ALLOW":
                self.true_negatives += 1
            elif action == "ESCALATE":
                # Escalation of legit is acceptable (AI being cautious)
                self.true_negatives += 1
            else:
                self.false_positives += 1  # Legit was blocked/challenged
        
        # Add to calibration bins
        bin_key = self._get_confidence_bin(confidence)
        if bin_key not in self.calibration_bins:
            self.calibration_bins[bin_key] = []
        # Store 1 for ATO, 0 for legit (for calibration calculation)
        self.calibration_bins[bin_key].append(1.0 if is_ato else 0.0)
    
    def _get_confidence_bin(self, confidence: float) -> str:
        """Get calibration bin for a confidence score."""
        if confidence < 0.2:
            return "0.0-0.2"
        elif confidence < 0.4:
            return "0.2-0.4"
        elif confidence < 0.6:
            return "0.4-0.6"
        elif confidence < 0.8:
            return "0.6-0.8"
        else:
            return "0.8-1.0"
    
    @property
    def false_positive_rate(self) -> float:
        """False positive rate = FP / (FP + TN).
        
        How often we harm legitimate users.
        """
        if self.false_positives + self.true_negatives == 0:
            return 0.0
        return self.false_positives / (self.false_positives + self.true_negatives)
    
    @property
    def false_negative_rate(self) -> float:
        """False negative rate = FN / (FN + TP).
        
        How often we miss actual fraud.
        """
        if self.false_negatives + self.true_positives == 0:
            return 0.0
        return self.false_negatives / (self.false_negatives + self.true_positives)
    
    @property
    def escalation_rate(self) -> float:
        """Escalation rate = escalated / total.
        
        How often AI exercises restraint.
        """
        if self.total_events == 0:
            return 0.0
        return self.escalated_count / self.total_events
    
    @property
    def human_override_rate(self) -> float:
        """Override rate = overrides / human_required.
        
        How often humans change AI-recommended decisions.
        """
        if self.human_required_count == 0:
            return 0.0
        return self.human_override_count / self.human_required_count
    
    @property
    def confidence_calibration_error(self) -> float:
        """Expected Calibration Error (ECE).
        
        Measures how well confidence predicts actual risk.
        Lower is better.
        """
        if not self.calibration_bins:
            return 0.0
        
        total_samples = sum(len(outcomes) for outcomes in self.calibration_bins.values())
        if total_samples == 0:
            return 0.0
        
        ece = 0.0
        bin_midpoints = {
            "0.0-0.2": 0.1,
            "0.2-0.4": 0.3,
            "0.4-0.6": 0.5,
            "0.6-0.8": 0.7,
            "0.8-1.0": 0.9,
        }
        
        for bin_key, outcomes in self.calibration_bins.items():
            if not outcomes:
                continue
            
            bin_size = len(outcomes)
            avg_confidence = bin_midpoints.get(bin_key, 0.5)
            actual_positive_rate = sum(outcomes) / bin_size
            
            # Add weighted absolute difference
            ece += (bin_size / total_samples) * abs(avg_confidence - actual_positive_rate)
        
        return ece
    
    @property
    def accuracy(self) -> float:
        """Overall accuracy (for reference only).
        
        Warning: Accuracy alone is misleading!
        """
        if self.total_events == 0:
            return 0.0
        correct = self.true_positives + self.true_negatives
        return correct / self.total_events
    
    @property
    def precision(self) -> float:
        """Precision = TP / (TP + FP).
        
        Of those we flagged as ATO, how many were correct?
        """
        if self.true_positives + self.false_positives == 0:
            return 0.0
        return self.true_positives / (self.true_positives + self.false_positives)
    
    @property
    def recall(self) -> float:
        """Recall = TP / (TP + FN).
        
        Of all actual ATOs, how many did we catch?
        """
        if self.true_positives + self.false_negatives == 0:
            return 0.0
        return self.true_positives / (self.true_positives + self.false_negatives)
    
    def summary(self) -> Dict[str, any]:
        """Generate a complete summary of all metrics."""
        return {
            "total_events": self.total_events,
            "legitimate_logins": self.total_legit,
            "ato_scenarios": self.total_ato,
            "actions": {
                "allowed": self.allowed_count,
                "blocked": self.blocked_count,
                "challenged": self.challenged_count,
                "escalated": self.escalated_count,
            },
            "classification": {
                "true_positives": self.true_positives,
                "true_negatives": self.true_negatives,
                "false_positives": self.false_positives,
                "false_negatives": self.false_negatives,
            },
            "key_metrics": {
                "false_positive_rate": round(self.false_positive_rate, 4),
                "escalation_rate": round(self.escalation_rate, 4),
                "human_override_rate": round(self.human_override_rate, 4),
                "confidence_calibration_error": round(self.confidence_calibration_error, 4),
                "policy_violation_count": self.policy_violation_count,
            },
            "reference_metrics": {
                "accuracy": round(self.accuracy, 4),
                "precision": round(self.precision, 4),
                "recall": round(self.recall, 4),
            },
        }
    
    def print_report(self) -> None:
        """Print a formatted evaluation report."""
        summary = self.summary()
        
        print("\n" + "=" * 60)
        print("           AEGISAI EVALUATION REPORT")
        print("=" * 60)
        
        print(f"\n📊 Dataset:")
        print(f"   Total events: {summary['total_events']}")
        print(f"   Legitimate:   {summary['legitimate_logins']}")
        print(f"   ATO:          {summary['ato_scenarios']}")
        
        print(f"\n🎯 Actions Taken:")
        actions = summary["actions"]
        print(f"   Allowed:    {actions['allowed']}")
        print(f"   Blocked:    {actions['blocked']}")
        print(f"   Challenged: {actions['challenged']}")
        print(f"   Escalated:  {actions['escalated']}")
        
        print(f"\n🔍 Classification:")
        clf = summary["classification"]
        print(f"   True Positives:  {clf['true_positives']} (ATO caught)")
        print(f"   True Negatives:  {clf['true_negatives']} (Legit allowed)")
        print(f"   False Positives: {clf['false_positives']} (Legit harmed)")
        print(f"   False Negatives: {clf['false_negatives']} (ATO missed)")
        
        print(f"\n⭐ KEY METRICS (What Actually Matters):")
        key = summary["key_metrics"]
        
        # False positive rate
        fpr = key["false_positive_rate"]
        fpr_color = "🟢" if fpr < 0.05 else ("🟡" if fpr < 0.10 else "🔴")
        print(f"   {fpr_color} False Positive Rate: {fpr:.2%}")
        
        # Escalation rate
        esc = key["escalation_rate"]
        esc_color = "🟢" if 0.05 <= esc <= 0.30 else "🟡"
        print(f"   {esc_color} Escalation Rate:     {esc:.2%}")
        
        # Human override rate
        override = key["human_override_rate"]
        override_color = "🟢" if override < 0.20 else ("🟡" if override < 0.40 else "🔴")
        print(f"   {override_color} Human Override Rate: {override:.2%}")
        
        # Calibration error
        cal_err = key["confidence_calibration_error"]
        cal_color = "🟢" if cal_err < 0.10 else ("🟡" if cal_err < 0.20 else "🔴")
        print(f"   {cal_color} Calibration Error:   {cal_err:.4f}")
        
        # Policy violations
        violations = key["policy_violation_count"]
        viol_color = "🟢" if violations == 0 else "🔴"
        print(f"   {viol_color} Policy Violations:   {violations}")
        
        print(f"\n📈 Reference Metrics (Not the Whole Story):")
        ref = summary["reference_metrics"]
        print(f"   Accuracy:  {ref['accuracy']:.2%}")
        print(f"   Precision: {ref['precision']:.2%}")
        print(f"   Recall:    {ref['recall']:.2%}")
        
        print("\n" + "=" * 60)
        
        # Key insight
        if violations == 0 and fpr < 0.10:
            print("✅ System operating within acceptable parameters")
        elif violations > 0:
            print("❌ CRITICAL: Policy violations detected - immediate review required")
        elif fpr >= 0.10:
            print("⚠️  High false positive rate - harming legitimate users")
        
        print("=" * 60 + "\n")
