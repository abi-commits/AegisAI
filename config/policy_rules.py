"""Policy rules and constraints for AegisAI.

These are the runtime governance rules that constrain AI behavior.
"""

# Confidence thresholds
CONFIDENCE_THRESHOLD_ALLOW: float = 0.80
CONFIDENCE_THRESHOLD_ESCALATE: float = 0.50

# Action constraints
MAX_ALLOWED_ACTIONS_PER_USER_PER_DAY: int = 5
ALLOW_PERMANENT_BLOCKS: bool = False  # AI cannot permanently block
ALLOW_TEMPORARY_BLOCKS: bool = True

# Escalation rules
DISAGREEMENT_THRESHOLD: float = 0.3  # If agents disagree > 30%, escalate
CONSECUTIVE_HIGH_RISK_ESCALATE: int = 3  # Escalate after 3 consecutive high-risk

# Human review triggers
HUMAN_REVIEW_LOW_CONFIDENCE: bool = True
HUMAN_REVIEW_HIGH_DISAGREEMENT: bool = True
HUMAN_REVIEW_POLICY_VIOLATION: bool = True

rules = {
    "version": "1.0.0",
    "last_updated": "2026-01-25",
    "constraints": {
        "confidence": {
            "min_to_allow": CONFIDENCE_THRESHOLD_ALLOW,
            "min_to_escalate": CONFIDENCE_THRESHOLD_ESCALATE,
        },
        "actions": {
            "permanent_block_allowed": ALLOW_PERMANENT_BLOCKS,
            "temporary_block_allowed": ALLOW_TEMPORARY_BLOCKS,
            "max_per_user_per_day": MAX_ALLOWED_ACTIONS_PER_USER_PER_DAY,
        },
        "escalation": {
            "disagreement_threshold": DISAGREEMENT_THRESHOLD,
            "consecutive_high_risk": CONSECUTIVE_HIGH_RISK_ESCALATE,
        },
    },
}
