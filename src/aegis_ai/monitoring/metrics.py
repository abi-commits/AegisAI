"""Monitoring - track escalation, confidence, overrides, policy vetoes, input drift."""

import logging, os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

import boto3
from botocore.exceptions import ClientError
from aegis_ai.common.constants import MonitoringConstants

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    ESCALATION_RATE = "escalation_rate"
    OVERRIDE_RATE = "override_rate"
    POLICY_VETO_RATE = "policy_veto_rate"
    CONFIDENCE_MEAN = "confidence_mean"
    CONFIDENCE_STD = "confidence_std"
    CONFIDENCE_PERCENTILE_95 = "confidence_p95"
    INPUT_DRIFT_DETECTED = "input_drift_detected"
    DECISION_LATENCY = "decision_latency"
    AGENT_ERROR_RATE = "agent_error_rate"
    POLICY_CHECK_TIME = "policy_check_time"


@dataclass
class MetricPoint:
    metric_name: str
    value: float
    unit: str = "None"
    timestamp: Optional[datetime] = None
    dimensions: Optional[Dict[str, str]] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)


class MetricsCollector:
    """Collects and publishes metrics to CloudWatch."""
    
    DEFAULT_REGION = "us-east-1"
    DEFAULT_NAMESPACE = "AegisAI"
    
    def __init__(self, namespace: Optional[str] = None, region: Optional[str] = None,
                 aws_profile: Optional[str] = None, batch_size: int = 20):
        self.namespace = namespace or os.environ.get("CLOUDWATCH_NAMESPACE", self.DEFAULT_NAMESPACE)
        self.region = region or os.environ.get("AWS_REGION", self.DEFAULT_REGION)
        self.batch_size = batch_size
        self.metric_buffer: List[MetricPoint] = []
        
        if aws_profile:
            session = boto3.Session(profile_name=aws_profile)
            self.cloudwatch = session.client("cloudwatch", region_name=self.region)
        else:
            self.cloudwatch = boto3.client("cloudwatch", region_name=self.region)
        
        logger.info(f"Initialized MetricsCollector: namespace={self.namespace}")
    
    def record_metric(self, metric: MetricPoint) -> None:
        """Record a metric point.
        
        Buffers metrics for batch publishing.
        
        Args:
            metric: MetricPoint to record
        """
        self.metric_buffer.append(metric)
        
        # Auto-flush if buffer full
        if len(self.metric_buffer) >= self.batch_size:
            self.flush()
    
    def record_decision(
        self,
        decision_id: str,
        action: str,
        confidence: float,
        latency_ms: float,
        was_escalated: bool = False,
        policy_vetoed: bool = False,
    ) -> None:
        """Record metrics for a decision.
        
        Args:
            decision_id: Decision ID
            action: Action taken (ALLOW/BLOCK/CHALLENGE)
            confidence: Confidence score
            latency_ms: Decision latency in milliseconds
            was_escalated: Whether decision was escalated
            policy_vetoed: Whether policy vetoed decision
        """
        # Track escalation
        if was_escalated:
            self.record_metric(MetricPoint(
                metric_name=MetricType.ESCALATION_RATE.value,
                value=1.0,
                unit="Count",
                dimensions={"decision_type": "escalated"},
            ))
        
        # Track policy veto
        if policy_vetoed:
            self.record_metric(MetricPoint(
                metric_name=MetricType.POLICY_VETO_RATE.value,
                value=1.0,
                unit="Count",
                dimensions={"veto_type": "policy"},
            ))
        
        # Track confidence
        self.record_metric(MetricPoint(
            metric_name="confidence_score",
            value=confidence,
            unit="None",
            dimensions={"action": action},
        ))
        
        # Track latency
        self.record_metric(MetricPoint(
            metric_name=MetricType.DECISION_LATENCY.value,
            value=latency_ms,
            unit="Milliseconds",
        ))
    
    def record_override(
        self,
        original_action: str,
        new_action: str,
        reviewer_role: str,
    ) -> None:
        """Record a human override.
        
        Args:
            original_action: Original AI action
            new_action: New action after override
            reviewer_role: Role of reviewer
        """
        self.record_metric(MetricPoint(
            metric_name=MetricType.OVERRIDE_RATE.value,
            value=1.0,
            unit="Count",
            dimensions={
                "reviewer_role": reviewer_role,
                "original_action": original_action,
                "new_action": new_action,
            },
        ))
    
    def record_agent_error(
        self,
        agent_name: str,
        error_type: str,
    ) -> None:
        """Record agent error.
        
        Args:
            agent_name: Name of agent that errored
            error_type: Type of error
        """
        self.record_metric(MetricPoint(
            metric_name=MetricType.AGENT_ERROR_RATE.value,
            value=1.0,
            unit="Count",
            dimensions={
                "agent": agent_name,
                "error_type": error_type,
            },
        ))
    
    def record_confidence_distribution(
        self,
        values: List[float],
    ) -> None:
        """Record confidence distribution metrics.
        
        Args:
            values: List of confidence scores
        """
        if not values:
            return
        
        import statistics
        
        mean_conf = statistics.mean(values)
        stdev_conf = statistics.stdev(values) if len(values) > 1 else 0.0
        p95_conf = sorted(values)[int(len(values) * 0.95)] if values else 0.0
        
        self.record_metric(MetricPoint(
            metric_name=MetricType.CONFIDENCE_MEAN.value,
            value=mean_conf,
            unit="None",
        ))
        
        self.record_metric(MetricPoint(
            metric_name=MetricType.CONFIDENCE_STD.value,
            value=stdev_conf,
            unit="None",
        ))
        
        self.record_metric(MetricPoint(
            metric_name=MetricType.CONFIDENCE_PERCENTILE_95.value,
            value=p95_conf,
            unit="None",
        ))
    
    def record_input_drift(
        self,
        drift_detected: bool,
        drift_magnitude: float = 0.0,
        affected_features: Optional[List[str]] = None,
    ) -> None:
        """Record input data drift detection.
        
        Args:
            drift_detected: Whether drift was detected
            drift_magnitude: Magnitude of drift (0-1)
            affected_features: List of affected feature names
        """
        self.record_metric(MetricPoint(
            metric_name=MetricType.INPUT_DRIFT_DETECTED.value,
            value=1.0 if drift_detected else 0.0,
            unit="Count",
            dimensions={
                "magnitude": "high" if drift_magnitude > 0.7 else "medium" if drift_magnitude > 0.3 else "low",
                "feature_count": str(len(affected_features or [])),
            },
        ))
    
    def flush(self) -> None:
        """Flush buffered metrics to CloudWatch.
        
        Raises:
            IOError: If CloudWatch write fails
        """
        if not self.metric_buffer:
            return
        
        try:
            # Batch metrics for CloudWatch
            metric_data = []
            for metric in self.metric_buffer:
                metric_dict = {
                    "MetricName": metric.metric_name,
                    "Value": metric.value,
                    "Unit": metric.unit,
                    "Timestamp": metric.timestamp,
                }
                
                if metric.dimensions:
                    metric_dict["Dimensions"] = [
                        {"Name": k, "Value": str(v)}
                        for k, v in metric.dimensions.items()
                    ]
                
                metric_data.append(metric_dict)
            
            # CloudWatch allows max 20 metrics per request
            for i in range(0, len(metric_data), 20):
                batch = metric_data[i:i+20]
                self.cloudwatch.put_metric_data(
                    Namespace=self.namespace,
                    MetricData=batch,
                )
            
            logger.debug(f"Published {len(self.metric_buffer)} metrics to CloudWatch")
            self.metric_buffer.clear()
        
        except ClientError as e:
            logger.error(f"Failed to publish metrics: {e}")
            raise IOError(f"CloudWatch write failed: {e}") from e
    
    def shutdown(self) -> None:
        """Flush remaining metrics on shutdown."""
        self.flush()


class AlertingThresholds:
    """Thresholds for alerting on anomalies."""
    
    ESCALATION_RATE_WARNING = MonitoringConstants.ESCALATION_RATE_WARNING
    ESCALATION_RATE_CRITICAL = MonitoringConstants.ESCALATION_RATE_CRITICAL
    OVERRIDE_RATE_WARNING = MonitoringConstants.OVERRIDE_RATE_WARNING
    OVERRIDE_RATE_CRITICAL = MonitoringConstants.OVERRIDE_RATE_CRITICAL
    POLICY_VETO_RATE_WARNING = 0.08
    POLICY_VETO_RATE_CRITICAL = 0.20
    CONFIDENCE_MEAN_WARNING = 0.50
    CONFIDENCE_STD_WARNING = 0.30
    CONFIDENCE_MEAN_ANOMALY_THRESHOLD = MonitoringConstants.CONFIDENCE_MEAN_ANOMALY
    CONFIDENCE_MIN_ANOMALY = MonitoringConstants.CONFIDENCE_MIN_ANOMALY
    CONFIDENCE_MAX_ANOMALY = MonitoringConstants.CONFIDENCE_MAX_ANOMALY
    DRIFT_MAGNITUDE_WARNING = 0.5
    AGENT_ERROR_RATE_WARNING = 0.01
    AGENT_ERROR_RATE_CRITICAL = 0.05
    DECISION_LATENCY_WARNING = MonitoringConstants.DECISION_LATENCY_WARNING_MS
    DECISION_LATENCY_CRITICAL = MonitoringConstants.DECISION_LATENCY_CRITICAL_MS


class AnomalyDetector:
    """Detects anomalies in system behavior."""
    
    @staticmethod
    def is_escalation_spike(current_rate: float, historical_mean: float) -> bool:
        """Detect if escalation rate has spiked.
        
        Args:
            current_rate: Current escalation rate
            historical_mean: Historical average
            
        Returns:
            True if spike detected
        """
        # Spike if 3x above historical average
        return current_rate > historical_mean * 3
    
    @staticmethod
    def is_confidence_anomaly(confidence: float) -> bool:
        """Detect if confidence is anomalously low/high.
        
        Args:
            confidence: Confidence score
            
        Returns:
            True if anomalous
        """
        # Anomalous if extremely low or high
        return confidence < 0.3 or confidence > 0.99
    
    @staticmethod
    def is_latency_anomaly(latency_ms: float, p95_latency: float) -> bool:
        """Detect if latency is anomalously high.
        
        Args:
            latency_ms: Decision latency
            p95_latency: 95th percentile latency
            
        Returns:
            True if anomalous
        """
        # Anomalous if > 2x p95
        return latency_ms > p95_latency * 2
