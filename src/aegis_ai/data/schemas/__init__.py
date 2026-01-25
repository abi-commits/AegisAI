"""Data schemas - canonical Pydantic definitions."""

from src.aegis_ai.data.schemas.user import User
from src.aegis_ai.data.schemas.device import Device
from src.aegis_ai.data.schemas.session import Session, GeoLocation
from src.aegis_ai.data.schemas.login_event import LoginEvent
from src.aegis_ai.data.schemas.risk_decision import RiskDecision

__all__ = [
    "User",
    "Device",
    "Session",
    "GeoLocation",
    "LoginEvent",
    "RiskDecision",
]
