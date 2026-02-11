"""Detection Agent - identifies anomalous login behavior."""

from pathlib import Path
from typing import Optional, Any

from aegis_ai.data.schemas.login_event import LoginEvent
from aegis_ai.data.schemas.session import Session
from aegis_ai.data.schemas.device import Device
from aegis_ai.agents.detection.schema import DetectionOutput
from aegis_ai.common.constants import ModelConstants


class DetectionAgent:
    """Detection Agent - Paranoid by Design."""
    
    RISK_WEIGHTS = {
        "new_device": 0.25, "new_ip": 0.15, "new_location": 0.30,
        "failed_attempts": 0.10, "vpn_detected": 0.10,
        "tor_detected": 0.35, "long_time_since_login": 0.10
    }
    
    # Thresholds
    FAILED_ATTEMPTS_CAP = 3  # Max contribution from failed attempts
    LONG_ABSENCE_HOURS = ModelConstants.BEHAVIOR_LONG_ABSENCE_HOURS
    
    def __init__(
        self,
        model_path: Optional[Path] = None,
        use_ml_model: bool = True,
        fallback_to_heuristic: bool = True
    ):
        """Initialize Detection Agent.
        
        Args:
            model_path: Path to trained risk model directory
            use_ml_model: Whether to use ML model for scoring
            fallback_to_heuristic: Fall back to heuristic on model failure
        """
        self._model_path = model_path
        self._use_ml_model = use_ml_model
        self._fallback_to_heuristic = fallback_to_heuristic
        
        # Lazy-loaded ML components
        self._risk_model: Optional[Any] = None
        self._feature_extractor: Optional[Any] = None
        self._shap_explainer: Optional[Any] = None
        self._ml_initialized = False
    
    def _init_ml_components(self) -> bool:
        """Initialize ML components lazily.
        
        Returns:
            True if ML components initialized successfully
        """
        if self._ml_initialized:
            return self._risk_model is not None
        
        self._ml_initialized = True
        
        if not self._use_ml_model or self._model_path is None:
            return False
        
        try:
            from aegis_ai.models.risk import (
                GBDTRiskModel,
                FeatureExtractor,
                SHAPExplainer,
                RiskModelConfig,
            )
            
            # Initialize feature extractor
            self._feature_extractor = FeatureExtractor()
            
            # Load risk model
            config = RiskModelConfig(
                feature_names=self._feature_extractor.feature_names
            )
            self._risk_model = GBDTRiskModel(config)
            self._risk_model.load(self._model_path)
            
            # Initialize SHAP explainer
            self._shap_explainer = SHAPExplainer(
                model=self._risk_model.get_native_model(),
                feature_names=self._feature_extractor.feature_names
            )
            
            return True
            
        except Exception as e:
            # Log error in production
            self._risk_model = None
            self._feature_extractor = None
            self._shap_explainer = None
            return False
    
    def analyze(
        self,
        login_event: LoginEvent,
        session: Session,
        device: Device
    ) -> DetectionOutput:
        """Analyze login event and return risk signals.
        
        Uses ML model if available, falls back to heuristic otherwise.
        
        Args:
            login_event: Validated LoginEvent schema object
            session: Validated Session schema object
            device: Validated Device schema object
            
        Returns:
            DetectionOutput with risk_signal_score and risk_factors
        """
        # Try ML-based scoring first
        if self._use_ml_model and self._init_ml_components():
            try:
                return self._analyze_with_model(login_event, session, device)
            except Exception:
                if not self._fallback_to_heuristic:
                    raise
                # Fall through to heuristic
        
        # Heuristic fallback
        return self._analyze_heuristic(login_event, session, device)
    
    def _analyze_with_model(
        self,
        login_event: LoginEvent,
        session: Session,
        device: Device
    ) -> DetectionOutput:
        """Analyze using ML model with SHAP explanations.
        
        Args:
            login_event: Login event data
            session: Session data
            device: Device data
            
        Returns:
            DetectionOutput with ML-based score and SHAP-derived factors
        """
        # Extract features
        features = self._feature_extractor.extract(login_event, session, device)
        
        # Get prediction
        prediction = self._risk_model.predict(features)
        
        # Get SHAP explanation for factor extraction
        explanation = self._shap_explainer.explain(features)
        
        # Extract risk factors using SHAP
        feature_to_factor = {
            name: self._feature_extractor.feature_to_factor_name(name)
            for name in self._feature_extractor.feature_names
        }
        risk_factors = self._shap_explainer.extract_risk_factors(
            explanation=explanation,
            feature_to_factor_map=feature_to_factor,
            n_factors=5,
            min_contribution=0.02
        )
        
        # Clamp score (model already outputs calibrated probability)
        clamped_score = max(0.0, min(1.0, prediction.score))
        
        return DetectionOutput(
            risk_signal_score=clamped_score,
            risk_factors=risk_factors
        )
    
    def _analyze_heuristic(
        self,
        login_event: LoginEvent,
        session: Session,
        device: Device
    ) -> DetectionOutput:
        """Analyze using rule-based heuristics.
        
        Original Phase 3 logic preserved for fallback.
        
        Args:
            login_event: Login event data
            session: Session data
            device: Device data
            
        Returns:
            DetectionOutput with heuristic-based score and factors
        """
        risk_score = 0.0
        risk_factors: list[str] = []
        
        # New device detection
        if login_event.is_new_device or not device.is_known:
            risk_score += self.RISK_WEIGHTS["new_device"]
            risk_factors.append("new_device_detected")
        
        # New IP detection
        if login_event.is_new_ip:
            risk_score += self.RISK_WEIGHTS["new_ip"]
            risk_factors.append("login_from_new_ip")
        
        # New location detection (highest weight)
        if login_event.is_new_location:
            risk_score += self.RISK_WEIGHTS["new_location"]
            risk_factors.append("login_from_new_country")
        
        # Failed attempts velocity
        if login_event.failed_attempts_before > 0:
            capped_attempts = min(
                login_event.failed_attempts_before,
                self.FAILED_ATTEMPTS_CAP
            )
            risk_score += self.RISK_WEIGHTS["failed_attempts"] * capped_attempts
            risk_factors.append(
                f"high_login_velocity_{login_event.failed_attempts_before}_failed_attempts"
            )
        
        # VPN detection
        if session.is_vpn:
            risk_score += self.RISK_WEIGHTS["vpn_detected"]
            risk_factors.append("vpn_or_proxy_detected")
        
        # Tor detection (high risk)
        if session.is_tor:
            risk_score += self.RISK_WEIGHTS["tor_detected"]
            risk_factors.append("tor_exit_node_detected")
        
        # Long absence
        if login_event.time_since_last_login_hours is not None:
            if login_event.time_since_last_login_hours > self.LONG_ABSENCE_HOURS:
                risk_score += self.RISK_WEIGHTS["long_time_since_login"]
                risk_factors.append("login_after_extended_absence")
        
        # Clamp score to [0, 1]
        clamped_score = max(0.0, min(1.0, risk_score))
        
        return DetectionOutput(
            risk_signal_score=clamped_score,
            risk_factors=risk_factors
        )
