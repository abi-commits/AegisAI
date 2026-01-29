"""Unit tests for Risk Model components.

Tests for:
- Feature extraction
- GBDT model training and prediction
- SHAP explainability
- Calibration
"""

import pytest
import numpy as np
from datetime import datetime
from pathlib import Path
import tempfile

from aegis_ai.data.schemas.login_event import LoginEvent
from aegis_ai.data.schemas.session import Session, GeoLocation
from aegis_ai.data.schemas.device import Device
from aegis_ai.models.risk.feature_extractor import (
    FeatureExtractor,
    FeatureConfig,
    FEATURE_NAMES,
)
from aegis_ai.models.risk.base import RiskModelConfig, ModelType
from aegis_ai.models.risk.gbdt_model import GBDTRiskModel
from aegis_ai.models.calibration.isotonic import IsotonicCalibrator


@pytest.fixture
def sample_login_event():
    """Create a sample login event."""
    return LoginEvent(
        event_id="evt_test_001",
        session_id="sess_test_001",
        user_id="user_test",
        timestamp=datetime(2026, 1, 25, 10, 30, 0),
        success=True,
        auth_method="password",
        failed_attempts_before=2,
        time_since_last_login_hours=48.0,
        is_new_device=True,
        is_new_ip=False,
        is_new_location=True,
        is_ato=False,
    )


@pytest.fixture
def sample_session():
    """Create a sample session."""
    return Session(
        session_id="sess_test_001",
        user_id="user_test",
        device_id="dev_test_001",
        ip_address="192.168.1.100",
        geo_location=GeoLocation(
            city="New York",
            country="US",
            latitude=40.7128,
            longitude=-74.0060,
        ),
        start_time=datetime(2026, 1, 25, 10, 30, 0),
        is_vpn=True,
        is_tor=False,
    )


@pytest.fixture
def sample_device():
    """Create a sample device."""
    return Device(
        device_id="dev_test_001",
        device_type="desktop",
        os="Windows 11",
        browser="Chrome 120",
        is_known=False,
        first_seen_at=None,
    )


class TestFeatureExtractor:
    """Tests for feature extraction."""
    
    def test_feature_names_defined(self):
        """Feature names should be properly defined."""
        assert len(FEATURE_NAMES) == 14
        assert "is_new_device" in FEATURE_NAMES
        assert "is_tor" in FEATURE_NAMES
    
    def test_extract_returns_correct_shape(
        self,
        sample_login_event,
        sample_session,
        sample_device
    ):
        """Extract should return correct number of features."""
        extractor = FeatureExtractor()
        features = extractor.extract(
            sample_login_event, sample_session, sample_device
        )
        
        assert features.shape == (extractor.n_features,)
        assert features.dtype == np.float32
    
    def test_extract_device_features(
        self,
        sample_login_event,
        sample_session,
        sample_device
    ):
        """Device features should be extracted correctly."""
        extractor = FeatureExtractor()
        features = extractor.extract(
            sample_login_event, sample_session, sample_device
        )
        
        # is_new_device should be 1.0 (True)
        is_new_device_idx = extractor.feature_names.index("is_new_device")
        assert features[is_new_device_idx] == 1.0
        
        # device_not_known should be 1.0 (is_known=False)
        device_not_known_idx = extractor.feature_names.index("device_not_known")
        assert features[device_not_known_idx] == 1.0
    
    def test_extract_network_features(
        self,
        sample_login_event,
        sample_session,
        sample_device
    ):
        """Network features should be extracted correctly."""
        extractor = FeatureExtractor()
        features = extractor.extract(
            sample_login_event, sample_session, sample_device
        )
        
        # is_vpn should be 1.0
        is_vpn_idx = extractor.feature_names.index("is_vpn")
        assert features[is_vpn_idx] == 1.0
        
        # is_tor should be 0.0
        is_tor_idx = extractor.feature_names.index("is_tor")
        assert features[is_tor_idx] == 0.0
    
    def test_extract_velocity_features(
        self,
        sample_login_event,
        sample_session,
        sample_device
    ):
        """Velocity features should be extracted correctly."""
        extractor = FeatureExtractor()
        features = extractor.extract(
            sample_login_event, sample_session, sample_device
        )
        
        # failed_attempts_before should be 2.0 (capped at 3)
        failed_idx = extractor.feature_names.index("failed_attempts_before")
        assert features[failed_idx] == 2.0
    
    def test_extract_batch(
        self,
        sample_login_event,
        sample_session,
        sample_device
    ):
        """Batch extraction should work correctly."""
        extractor = FeatureExtractor()
        features = extractor.extract_batch(
            [sample_login_event, sample_login_event],
            [sample_session, sample_session],
            [sample_device, sample_device]
        )
        
        assert features.shape == (2, extractor.n_features)
    
    def test_feature_to_factor_name(self):
        """Feature names should map to human-readable factors."""
        extractor = FeatureExtractor()
        
        assert extractor.feature_to_factor_name("is_new_device") == "new_device_detected"
        assert extractor.feature_to_factor_name("is_tor") == "tor_exit_node_detected"


class TestGBDTRiskModel:
    """Tests for GBDT risk model."""
    
    @pytest.fixture
    def synthetic_data(self):
        """Create synthetic training data."""
        np.random.seed(42)
        n_samples = 500
        n_features = 14
        
        X = np.random.rand(n_samples, n_features).astype(np.float32)
        # Create labels with some structure
        y = (X[:, 0] + X[:, 1] + X[:, 2] > 1.5).astype(int)
        
        return X, y
    
    def test_model_fit(self, synthetic_data):
        """Model should fit without error."""
        X, y = synthetic_data
        
        config = RiskModelConfig(
            model_type=ModelType.XGBOOST,
            feature_names=[f"f{i}" for i in range(14)]
        )
        model = GBDTRiskModel(config)
        model.fit(X, y)
        
        assert model.is_fitted
    
    def test_model_predict(self, synthetic_data):
        """Model should predict risk scores."""
        X, y = synthetic_data
        
        config = RiskModelConfig(
            model_type=ModelType.XGBOOST,
            feature_names=[f"f{i}" for i in range(14)]
        )
        model = GBDTRiskModel(config)
        model.fit(X, y)
        
        prediction = model.predict(X[0])
        
        assert 0.0 <= prediction.score <= 1.0
        assert prediction.feature_names == config.feature_names
    
    def test_model_predict_batch(self, synthetic_data):
        """Batch prediction should work correctly."""
        X, y = synthetic_data
        
        config = RiskModelConfig(
            model_type=ModelType.XGBOOST,
            feature_names=[f"f{i}" for i in range(14)]
        )
        model = GBDTRiskModel(config)
        model.fit(X, y)
        
        predictions = model.predict_batch(X[:10])
        
        assert len(predictions) == 10
        for pred in predictions:
            assert 0.0 <= pred.score <= 1.0
    
    def test_model_save_load(self, synthetic_data):
        """Model should save and load correctly."""
        X, y = synthetic_data
        
        config = RiskModelConfig(
            model_type=ModelType.XGBOOST,
            feature_names=[f"f{i}" for i in range(14)]
        )
        model = GBDTRiskModel(config)
        model.fit(X, y)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "model"
            model.save(save_path)
            
            # Load into new instance
            loaded_config = RiskModelConfig()
            loaded_model = GBDTRiskModel(loaded_config)
            loaded_model.load(save_path)
            
            # Predictions should match
            orig_pred = model.predict(X[0])
            loaded_pred = loaded_model.predict(X[0])
            
            assert abs(orig_pred.score - loaded_pred.score) < 1e-6
    
    def test_lightgbm_model(self, synthetic_data):
        """LightGBM backend should work."""
        X, y = synthetic_data
        
        config = RiskModelConfig(
            model_type=ModelType.LIGHTGBM,
            feature_names=[f"f{i}" for i in range(14)]
        )
        model = GBDTRiskModel(config)
        model.fit(X, y)
        
        prediction = model.predict(X[0])
        assert 0.0 <= prediction.score <= 1.0


class TestIsotonicCalibrator:
    """Tests for isotonic calibration."""
    
    @pytest.fixture
    def calibration_data(self):
        """Create calibration data."""
        np.random.seed(42)
        n = 200
        
        # Simulated miscalibrated predictions
        y_true = np.random.binomial(1, 0.3, n)
        y_prob = np.clip(y_true * 0.5 + np.random.randn(n) * 0.2 + 0.2, 0, 1)
        
        return y_prob, y_true
    
    def test_calibrator_fit(self, calibration_data):
        """Calibrator should fit without error."""
        y_prob, y_true = calibration_data
        
        calibrator = IsotonicCalibrator()
        calibrator.fit(y_prob, y_true)
        
        assert calibrator.is_fitted
    
    def test_calibrator_calibrate(self, calibration_data):
        """Calibrated values should be in [0, 1]."""
        y_prob, y_true = calibration_data
        
        calibrator = IsotonicCalibrator()
        calibrator.fit(y_prob, y_true)
        
        calibrated = calibrator.calibrate(y_prob)
        
        assert all(0 <= p <= 1 for p in calibrated)
    
    def test_calibrator_evaluate(self, calibration_data):
        """Calibrator should compute metrics."""
        y_prob, y_true = calibration_data
        
        calibrator = IsotonicCalibrator()
        calibrator.fit(y_prob, y_true)
        
        metrics = calibrator.evaluate(y_prob, y_true)
        
        assert 0 <= metrics.brier_score <= 1
        assert 0 <= metrics.ece <= 1
    
    def test_calibrator_save_load(self, calibration_data):
        """Calibrator should save and load correctly."""
        y_prob, y_true = calibration_data
        
        calibrator = IsotonicCalibrator()
        calibrator.fit(y_prob, y_true)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "calibrator.pkl"
            calibrator.save(save_path)
            
            loaded = IsotonicCalibrator()
            loaded.load(save_path)
            
            # Calibrated values should match
            orig = calibrator.calibrate(y_prob)
            loaded_cal = loaded.calibrate(y_prob)
            
            np.testing.assert_array_almost_equal(orig, loaded_cal)


class TestSHAPExplainer:
    """Tests for SHAP explainability."""
    
    @pytest.fixture
    def trained_model_with_data(self):
        """Create trained model with data for SHAP."""
        np.random.seed(42)
        n_samples = 500
        n_features = 14
        feature_names = [f"feature_{i}" for i in range(n_features)]
        
        X = np.random.rand(n_samples, n_features).astype(np.float32)
        y = (X[:, 0] + X[:, 1] + X[:, 2] > 1.5).astype(int)
        
        config = RiskModelConfig(
            model_type=ModelType.XGBOOST,
            feature_names=feature_names
        )
        model = GBDTRiskModel(config)
        model.fit(X, y)
        
        return model, X, feature_names
    
    def test_shap_explainer_creation(self, trained_model_with_data):
        """SHAP explainer should be created from trained model."""
        from aegis_ai.models.risk.shap_explainer import SHAPExplainer
        
        model, X, feature_names = trained_model_with_data
        
        explainer = SHAPExplainer(
            model=model.get_native_model(),
            feature_names=feature_names
        )
        
        assert explainer.feature_names == feature_names
    
    def test_shap_explain_single(self, trained_model_with_data):
        """SHAP should explain a single prediction."""
        from aegis_ai.models.risk.shap_explainer import SHAPExplainer
        
        model, X, feature_names = trained_model_with_data
        
        explainer = SHAPExplainer(
            model=model.get_native_model(),
            feature_names=feature_names
        )
        
        explanation = explainer.explain(X[0])
        
        # SHAP values should have same length as features
        assert len(explanation.shap_values) == len(feature_names)
        assert len(explanation.feature_names) == len(feature_names)
    
    def test_shap_top_contributors(self, trained_model_with_data):
        """SHAP should identify top contributing features."""
        from aegis_ai.models.risk.shap_explainer import SHAPExplainer
        
        model, X, feature_names = trained_model_with_data
        
        explainer = SHAPExplainer(
            model=model.get_native_model(),
            feature_names=feature_names
        )
        
        explanation = explainer.explain(X[0])
        top_contributors = explanation.get_top_contributors(n=3)
        
        # Should return at most 3 contributors
        assert len(top_contributors) <= 3
        # Each should be a (name, value) tuple
        for name, value in top_contributors:
            assert isinstance(name, str)
            assert isinstance(value, (int, float, np.floating))
    
    def test_shap_global_importance(self, trained_model_with_data):
        """SHAP should compute global feature importance."""
        from aegis_ai.models.risk.shap_explainer import SHAPExplainer
        
        model, X, feature_names = trained_model_with_data
        
        explainer = SHAPExplainer(
            model=model.get_native_model(),
            feature_names=feature_names
        )
        
        importance = explainer.global_importance(X[:100])
        
        assert len(importance.feature_names) == len(feature_names)
        assert len(importance.importance_values) == len(feature_names)
        # Importance values should be non-negative
        assert all(v >= 0 for v in importance.importance_values)
    
    def test_shap_extract_risk_factors(self, trained_model_with_data):
        """SHAP should extract human-readable risk factors."""
        from aegis_ai.models.risk.shap_explainer import SHAPExplainer
        
        model, X, feature_names = trained_model_with_data
        
        explainer = SHAPExplainer(
            model=model.get_native_model(),
            feature_names=feature_names
        )
        
        explanation = explainer.explain(X[0])
        
        # Create feature to factor mapping
        feature_to_factor = {name: f"risk_{name}" for name in feature_names}
        
        factors = explainer.extract_risk_factors(
            explanation=explanation,
            feature_to_factor_map=feature_to_factor,
            n_factors=3
        )
        
        # Should return list of strings
        assert isinstance(factors, list)
        for factor in factors:
            assert isinstance(factor, str)

