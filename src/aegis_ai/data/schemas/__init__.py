"""Data schemas - canonical Pydantic definitions."""

from aegis_ai.data.schemas.user import User
from aegis_ai.data.schemas.device import Device
from aegis_ai.data.schemas.session import Session, GeoLocation
from aegis_ai.data.schemas.login_event import LoginEvent
from aegis_ai.data.schemas.risk_decision import RiskDecision

__all__ = [
    "User",
    "Device",
    "Session",
    "GeoLocation",
    "LoginEvent",
    "RiskDecision",
]
