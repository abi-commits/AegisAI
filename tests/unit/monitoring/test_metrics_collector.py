"""Tests for Monitoring Layer (Layer 7)."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from statistics import mean, stdev

from aegis_ai.monitoring.metrics import (
    MetricType,
    MetricPoint,
    MetricsCollector,
    AlertingThresholds,
    AnomalyDetector,
)


class TestMetricType:
    """Tests for MetricType enum."""
    
    def test_all_metric_types_exist(self):
        """Test that all metric types are defined."""
        assert MetricType.ESCALATION_RATE
        assert MetricType.OVERRIDE_RATE
        assert MetricType.POLICY_VETO_RATE
        assert MetricType.CONFIDENCE_MEAN
        assert MetricType.CONFIDENCE_STD
        assert MetricType.CONFIDENCE_P95
        assert MetricType.INPUT_DRIFT
        assert MetricType.DECISION_LATENCY
        assert MetricType.AGENT_ERROR_RATE


class TestMetricPoint:
    """Tests for MetricPoint dataclass."""
    
    def test_metric_point_creation(self):
        """Test creating a metric point."""
        point = MetricPoint(
            metric_name="escalation_rate",
            value=0.05,
            unit="Percent",
            timestamp=datetime.now(),
            dimensions={"decision_type": "fraud"},
        )
        
        assert point.metric_name == "escalation_rate"
        assert point.value == 0.05
        assert point.unit == "Percent"
        assert point.dimensions["decision_type"] == "fraud"


class TestMetricsCollector:
    """Tests for MetricsCollector."""
    
    @patch("aegis_ai.monitoring.metrics.boto3.client")
    def test_collector_initialization(self, mock_boto3_client):
        """Test initializing metrics collector."""
        mock_cloudwatch = MagicMock()
        mock_boto3_client.return_value = mock_cloudwatch
        
        collector = MetricsCollector(
            namespace="AegisAI",
            batch_size=20,
            region="us-east-1",
        )
        
        assert collector.namespace == "AegisAI"
        assert collector.batch_size == 20
    
    @patch("aegis_ai.monitoring.metrics.boto3.client")
    def test_record_metric(self, mock_boto3_client):
        """Test recording a metric."""
        mock_cloudwatch = MagicMock()
        mock_boto3_client.return_value = mock_cloudwatch
        
        collector = MetricsCollector(
            namespace="AegisAI",
            batch_size=20,
        )
        
        collector.record_metric(
            metric_name="escalation_rate",
            value=0.05,
            unit="Percent",
            dimensions={"decision_type": "fraud"},
        )
        
        assert len(collector.metrics_buffer) == 1
    
    @patch("aegis_ai.monitoring.metrics.boto3.client")
    def test_record_decision(self, mock_boto3_client):
        """Test recording a decision metric."""
        mock_cloudwatch = MagicMock()
        mock_boto3_client.return_value = mock_cloudwatch
        
        collector = MetricsCollector(namespace="AegisAI")
        
        collector.record_decision(
            decision_id="dec-123",
            decision_type="fraud",
            escalated=False,
            vetoed=False,
            confidence=0.85,
            latency_ms=150,
        )
        
        assert len(collector.metrics_buffer) > 0
    
    @patch("aegis_ai.monitoring.metrics.boto3.client")
    def test_record_override(self, mock_boto3_client):
        """Test recording an override event."""
        mock_cloudwatch = MagicMock()
        mock_boto3_client.return_value = mock_cloudwatch
        
        collector = MetricsCollector(namespace="AegisAI")
        
        collector.record_override(
            decision_id="dec-123",
            original_decision="approve",
            override_decision="reject",
            reviewer_role="supervisor",
        )
        
        assert len(collector.metrics_buffer) > 0
    
    @patch("aegis_ai.monitoring.metrics.boto3.client")
    def test_record_agent_error(self, mock_boto3_client):
        """Test recording an agent error."""
        mock_cloudwatch = MagicMock()
        mock_boto3_client.return_value = mock_cloudwatch
        
        collector = MetricsCollector(namespace="AegisAI")
        
        collector.record_agent_error(
            agent_name="detection",
            error_type="timeout",
            decision_id="dec-123",
        )
        
        assert len(collector.metrics_buffer) > 0
    
    @patch("aegis_ai.monitoring.metrics.boto3.client")
    def test_record_confidence_distribution(self, mock_boto3_client):
        """Test recording confidence distribution."""
        mock_cloudwatch = MagicMock()
        mock_boto3_client.return_value = mock_cloudwatch
        
        collector = MetricsCollector(namespace="AegisAI")
        
        scores = [0.7, 0.75, 0.8, 0.85, 0.9, 0.92, 0.95]
        collector.record_confidence_distribution(
            scores=scores,
            decision_type="fraud",
        )
        
        # Should record at least 3 metrics (mean, std, p95)
        assert len(collector.metrics_buffer) >= 3
    
    @patch("aegis_ai.monitoring.metrics.boto3.client")
    def test_record_input_drift(self, mock_boto3_client):
        """Test recording input drift."""
        mock_cloudwatch = MagicMock()
        mock_boto3_client.return_value = mock_cloudwatch
        
        collector = MetricsCollector(namespace="AegisAI")
        
        collector.record_input_drift(
            affected_features=["transaction_amount", "user_age"],
            drift_magnitude=0.25,
        )
        
        assert len(collector.metrics_buffer) > 0
    
    @patch("aegis_ai.monitoring.metrics.boto3.client")
    def test_flush(self, mock_boto3_client):
        """Test flushing metrics to CloudWatch."""
        mock_cloudwatch = MagicMock()
        mock_boto3_client.return_value = mock_cloudwatch
        
        collector = MetricsCollector(
            namespace="AegisAI",
            batch_size=5,
        )
        
        # Record multiple metrics
        for i in range(10):
            collector.record_metric(
                metric_name=f"metric_{i}",
                value=float(i),
                unit="Count",
            )
        
        # Flush
        collector.flush()
        
        # Verify CloudWatch put_metric_data was called
        assert mock_cloudwatch.put_metric_data.called
    
    @patch("aegis_ai.monitoring.metrics.boto3.client")
    def test_auto_flush_at_batch_size(self, mock_boto3_client):
        """Test auto-flush when batch size reached."""
        mock_cloudwatch = MagicMock()
        mock_boto3_client.return_value = mock_cloudwatch
        
        collector = MetricsCollector(
            namespace="AegisAI",
            batch_size=3,
        )
        
        # Record 3 metrics
        for i in range(3):
            collector.record_metric(
                metric_name=f"metric_{i}",
                value=float(i),
                unit="Count",
            )
        
        # Should have triggered auto-flush
        assert mock_cloudwatch.put_metric_data.called
    
    @patch("aegis_ai.monitoring.metrics.boto3.client")
    def test_shutdown(self, mock_boto3_client):
        """Test graceful shutdown with final flush."""
        mock_cloudwatch = MagicMock()
        mock_boto3_client.return_value = mock_cloudwatch
        
        collector = MetricsCollector(namespace="AegisAI")
        
        collector.record_metric(
            metric_name="test",
            value=1.0,
            unit="Count",
        )
        
        collector.shutdown()
        
        # Should have flushed
        assert mock_cloudwatch.put_metric_data.called
        assert len(collector.metrics_buffer) == 0


class TestAlertingThresholds:
    """Tests for AlertingThresholds."""
    
    def test_escalation_threshold_warning(self):
        """Test escalation warning threshold."""
        assert AlertingThresholds.ESCALATION_RATE_WARNING == 0.05
    
    def test_escalation_threshold_critical(self):
        """Test escalation critical threshold."""
        assert AlertingThresholds.ESCALATION_RATE_CRITICAL == 0.15
    
    def test_override_threshold_warning(self):
        """Test override warning threshold."""
        assert AlertingThresholds.OVERRIDE_RATE_WARNING == 0.10
    
    def test_override_threshold_critical(self):
        """Test override critical threshold."""
        assert AlertingThresholds.OVERRIDE_RATE_CRITICAL == 0.25
    
    def test_confidence_threshold(self):
        """Test confidence thresholds."""
        assert AlertingThresholds.CONFIDENCE_MEAN_ANOMALY_THRESHOLD == 0.5
        assert AlertingThresholds.CONFIDENCE_MIN_ANOMALY < AlertingThresholds.CONFIDENCE_MAX_ANOMALY
    
    def test_latency_thresholds(self):
        """Test latency thresholds."""
        assert AlertingThresholds.LATENCY_WARNING_MS == 500
        assert AlertingThresholds.LATENCY_CRITICAL_MS == 2000


class TestAnomalyDetector:
    """Tests for AnomalyDetector."""
    
    def test_detect_spike_above_baseline(self):
        """Test spike detection above 3x baseline."""
        baseline_values = [1.0, 1.1, 0.9, 1.0, 1.1]
        current_value = 5.0  # 5x baseline, should trigger
        
        is_anomaly = AnomalyDetector.detect_spike(
            current_value=current_value,
            baseline_values=baseline_values,
            threshold_multiplier=3,
        )
        
        assert is_anomaly is True
    
    def test_detect_spike_within_threshold(self):
        """Test spike detection within threshold."""
        baseline_values = [1.0, 1.1, 0.9, 1.0, 1.1]
        current_value = 2.0  # ~2x baseline, should not trigger
        
        is_anomaly = AnomalyDetector.detect_spike(
            current_value=current_value,
            baseline_values=baseline_values,
            threshold_multiplier=3,
        )
        
        assert is_anomaly is False
    
    def test_detect_confidence_anomaly_low(self):
        """Test confidence anomaly - too low."""
        is_anomaly = AnomalyDetector.detect_confidence_anomaly(0.2)
        assert is_anomaly is True
    
    def test_detect_confidence_anomaly_high(self):
        """Test confidence anomaly - too high."""
        is_anomaly = AnomalyDetector.detect_confidence_anomaly(0.99)
        assert is_anomaly is True
    
    def test_detect_confidence_anomaly_normal(self):
        """Test confidence anomaly - normal range."""
        is_anomaly = AnomalyDetector.detect_confidence_anomaly(0.65)
        assert is_anomaly is False
    
    def test_detect_latency_anomaly(self):
        """Test latency anomaly detection."""
        p95_baseline_ms = 200
        current_latency_ms = 500  # 2.5x baseline, should trigger
        
        is_anomaly = AnomalyDetector.detect_latency_anomaly(
            current_latency_ms=current_latency_ms,
            p95_baseline_ms=p95_baseline_ms,
        )
        
        assert is_anomaly is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
