"""Centralized constants for AegisAI system configuration."""


# ===== AUDIT & LOGGING =====
class AuditConstants:
    QUEUE_SIZE = 10000
    FLUSH_TIMEOUT_SECONDS = 5.0
    QUEUE_GET_TIMEOUT = 1.0
    HASH_ALGORITHM = "sha256"


# ===== MONITORING & ALERTING =====
class MonitoringConstants:
    DEFAULT_BATCH_SIZE = 20
    DECISION_LATENCY_WARNING_MS = 500
    DECISION_LATENCY_CRITICAL_MS = 2000
    
    # Escalation rate thresholds
    ESCALATION_RATE_WARNING = 0.05
    ESCALATION_RATE_CRITICAL = 0.15
    
    # Override rate thresholds
    OVERRIDE_RATE_WARNING = 0.10
    OVERRIDE_RATE_CRITICAL = 0.25
    
    # Confidence thresholds
    CONFIDENCE_MEAN_ANOMALY = 0.5
    CONFIDENCE_MIN_ANOMALY = 0.3
    CONFIDENCE_MAX_ANOMALY = 0.8


# ===== MODEL & RISK SCORING =====
class ModelConstants:
    # Confidence bounds
    CONFIDENCE_MIN = 0.0
    CONFIDENCE_MAX = 1.0
    CONFIDENCE_DECISION_THRESHOLD = 0.8
    CONFIDENCE_RISK_THRESHOLD = 0.5
    
    # Risk scoring
    SHAP_CONTRIBUTION_MIN = 0.02
    SHAP_TOP_FEATURES = 5
    
    # Graph/Network
    GRAPH_MAX_NODES = 100
    
    # Behavior profiling
    BEHAVIOR_MAX_HISTORY = 100
    BEHAVIOR_LONG_ABSENCE_HOURS = 720  # 30 days
    
    # Feature extraction
    RISK_SCORE_PROBABILITY_THRESHOLD = 0.5
    
    # Explainability
    CONFIDENCE_THRESHOLD_HIGH = 0.8


# ===== DATA & QUERY LIMITS =====
class DataConstants:
    DEFAULT_QUERY_LIMIT = 100
    PENDING_CASES_LIMIT = 50
    SHAP_MAX_SAMPLES = 1000
    DATASET_NUM_USERS = 100
    DATASET_NUM_LEGIT = 100
    LOCATION_NORMALIZATION_LON = 180.0


# ===== EMERGENCY & PERFORMANCE =====
class PerformanceConstants:
    SLOW_MODE_DELAY_MS = 500


# ===== EVALUATION =====
class EvaluationConstants:
    ESCALATION_RATE_GOOD_RANGE_MIN = 0.05
    ESCALATION_RATE_GOOD_RANGE_MAX = 0.30
    FALSE_POSITIVE_RATE_WARNING = 0.10
