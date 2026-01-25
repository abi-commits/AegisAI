"""Schema validation utilities for AegisAI.

Provides validation functions for all data entities.
"""

from typing import List, Dict, Any, Optional, Union
from pydantic import ValidationError

from src.aegis_ai.data.schemas import (
    User,
    Device,
    Session,
    LoginEvent,
    RiskDecision,
)


class ValidationResult:
    """Result of validation operation."""
    
    def __init__(self):
        self.valid: bool = True
        self.errors: List[Dict[str, Any]] = []
        self.validated_count: int = 0
    
    def add_error(self, entity_type: str, index: int, error: str):
        """Add validation error."""
        self.valid = False
        self.errors.append({
            "entity_type": entity_type,
            "index": index,
            "error": error,
        })
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "valid": self.valid,
            "validated_count": self.validated_count,
            "error_count": len(self.errors),
            "errors": self.errors,
        }


def validate_user(user: Union[User, Dict[str, Any]]) -> Optional[str]:
    """Validate a single user.
    
    Args:
        user: User object or dictionary
        
    Returns:
        None if valid, error message if invalid
    """
    try:
        if isinstance(user, dict):
            User.model_validate(user)
        elif isinstance(user, User):
            # Already validated by Pydantic
            pass
        else:
            return f"Expected User or dict, got {type(user)}"
        return None
    except ValidationError as e:
        return str(e)


def validate_device(device: Union[Device, Dict[str, Any]]) -> Optional[str]:
    """Validate a single device."""
    try:
        if isinstance(device, dict):
            Device.model_validate(device)
        elif isinstance(device, Device):
            pass
        else:
            return f"Expected Device or dict, got {type(device)}"
        return None
    except ValidationError as e:
        return str(e)


def validate_session(session: Union[Session, Dict[str, Any]]) -> Optional[str]:
    """Validate a single session."""
    try:
        if isinstance(session, dict):
            Session.model_validate(session)
        elif isinstance(session, Session):
            pass
        else:
            return f"Expected Session or dict, got {type(session)}"
        return None
    except ValidationError as e:
        return str(e)


def validate_login_event(event: Union[LoginEvent, Dict[str, Any]]) -> Optional[str]:
    """Validate a single login event."""
    try:
        if isinstance(event, dict):
            LoginEvent.model_validate(event)
        elif isinstance(event, LoginEvent):
            pass
        else:
            return f"Expected LoginEvent or dict, got {type(event)}"
        return None
    except ValidationError as e:
        return str(e)


def validate_risk_decision(decision: Union[RiskDecision, Dict[str, Any]]) -> Optional[str]:
    """Validate a single risk decision."""
    try:
        if isinstance(decision, dict):
            RiskDecision.model_validate(decision)
        elif isinstance(decision, RiskDecision):
            pass
        else:
            return f"Expected RiskDecision or dict, got {type(decision)}"
        return None
    except ValidationError as e:
        return str(e)


def validate_users(users: List[Union[User, Dict[str, Any]]]) -> ValidationResult:
    """Validate list of users."""
    result = ValidationResult()
    for i, user in enumerate(users):
        error = validate_user(user)
        if error:
            result.add_error("User", i, error)
        else:
            result.validated_count += 1
    return result


def validate_devices(devices: List[Union[Device, Dict[str, Any]]]) -> ValidationResult:
    """Validate list of devices."""
    result = ValidationResult()
    for i, device in enumerate(devices):
        error = validate_device(device)
        if error:
            result.add_error("Device", i, error)
        else:
            result.validated_count += 1
    return result


def validate_sessions(sessions: List[Union[Session, Dict[str, Any]]]) -> ValidationResult:
    """Validate list of sessions."""
    result = ValidationResult()
    for i, session in enumerate(sessions):
        error = validate_session(session)
        if error:
            result.add_error("Session", i, error)
        else:
            result.validated_count += 1
    return result


def validate_events(events: List[Union[LoginEvent, Dict[str, Any]]]) -> ValidationResult:
    """Validate list of login events."""
    result = ValidationResult()
    for i, event in enumerate(events):
        error = validate_login_event(event)
        if error:
            result.add_error("LoginEvent", i, error)
        else:
            result.validated_count += 1
    return result


def validate_all(
    users: List[Union[User, Dict[str, Any]]] = None,
    devices: List[Union[Device, Dict[str, Any]]] = None,
    sessions: List[Union[Session, Dict[str, Any]]] = None,
    events: List[Union[LoginEvent, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Validate all entity types.
    
    Args:
        users: List of users to validate
        devices: List of devices to validate
        sessions: List of sessions to validate
        events: List of login events to validate
        
    Returns:
        Combined validation result
    """
    all_valid = True
    all_errors = []
    total_validated = 0
    
    if users:
        result = validate_users(users)
        all_valid = all_valid and result.valid
        all_errors.extend(result.errors)
        total_validated += result.validated_count
    
    if devices:
        result = validate_devices(devices)
        all_valid = all_valid and result.valid
        all_errors.extend(result.errors)
        total_validated += result.validated_count
    
    if sessions:
        result = validate_sessions(sessions)
        all_valid = all_valid and result.valid
        all_errors.extend(result.errors)
        total_validated += result.validated_count
    
    if events:
        result = validate_events(events)
        all_valid = all_valid and result.valid
        all_errors.extend(result.errors)
        total_validated += result.validated_count
    
    return {
        "valid": all_valid,
        "validated_count": total_validated,
        "error_count": len(all_errors),
        "errors": all_errors,
    }


def validate_json_dataset(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a JSON dataset export.
    
    Args:
        data: Dictionary with users, devices, sessions, events keys
        
    Returns:
        Validation result
    """
    return validate_all(
        users=data.get("users", []),
        devices=data.get("devices", []),
        sessions=data.get("sessions", []),
        events=data.get("events", []),
    )
