"""Explanation Agent - generates action and human-readable explanation.

Uses native tree-based explainability templates (no SHAP required).
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, List, Optional
from src.aegis_ai.models.explainability import (
    RiskFactor,
    ExplanationBuilder,
)


class Action(str, Enum):
    """Available actions for risk decisions."""
    ALLOW = "allow"
    CHALLENGE = "challenge"
    BLOCK_TEMPORARY = "block_temporary"
    ESCALATE = "escalate"


@dataclass
class ExplanationOutput:
    """Output from Explanation Agent."""
    final_action: Action
    explanation_text: str
    summary: str
    risk_factors: List[RiskFactor]
    audit_entry: dict
    

class ExplanationAgent:
    """Explanation Agent Contract.
    
    Input: approved decision + evidence + risk factors
    Output: final_action, explanation_text, audit_log
    Constraint: Must obey confidence gate and policy rules
    
    Uses native tree-based explainability templates for human-readable outputs.
    """
    
    def __init__(self):
        self.builder = ExplanationBuilder()
    
    def generate(
        self,
        decision_context: Dict[str, Any],
        policy_constraints: Dict[str, Any],
        confidence: float = None
    ) -> ExplanationOutput:
        """
        Generate action and human-readable explanation.
        
        Args:
            decision_context: {
                'risk_factors': List[RiskFactor],
                'risk_score': float,
                'session_id': str,
                'user_id': str,
            }
            policy_constraints: Policy rules from PolicyEngine
            confidence: Model confidence (0.0-1.0)
            
        Returns:
            ExplanationOutput with action, explanation, and audit trail
        """
        raise NotImplementedError
    
    def _determine_action(
        self,
        risk_score: float,
        confidence: float,
        risk_factors: List[RiskFactor],
        policy_constraints: Dict[str, Any]
    ) -> Action:
        """
        Determine final action based on risk and confidence.
        
        Decision logic:
        - risk_score > 0.8 → BLOCK_TEMPORARY
        - risk_score > 0.6 → CHALLENGE
        - risk_score > 0.4 → Consider confidence
        - Otherwise → ALLOW
        """
        raise NotImplementedError
    
    def _generate_explanation(
        self,
        risk_factors: List[RiskFactor],
        factor_details: Optional[Dict[str, Dict[str, Any]]] = None,
        confidence: float = None
    ) -> str:
        """
        Generate human-readable explanation using templates.
        
        Args:
            risk_factors: List of detected risk factors in order
            factor_details: Optional details for each factor
            confidence: Model confidence score
            
        Returns:
            Human-readable explanation string
        """
        return self.builder.build_explanation(
            risk_factors=risk_factors,
            factor_details=factor_details or {},
            confidence=confidence
        )
