"""Legitimate login scenario generator."""

from datetime import datetime, timedelta
from typing import List, Tuple, Optional

from src.aegis_ai.data.schemas import User, Device, Session, LoginEvent
from aegis_ai.data.generators.base_generator import BaseGenerator


class LegitLoginGenerator(BaseGenerator):
    """Generates legitimate (non-fraudulent) login scenarios.
    
    Legitimate logins have these characteristics:
    - Login from known devices (most of the time)
    - Login from home location (most of the time)
    - Login during typical hours (most of the time)
    - Low failed attempts
    - Reasonable time between logins
    """
    
    def __init__(self, seed: int = 42):
        super().__init__(seed)
        self._user_devices: dict[str, List[Device]] = {}  # user_id -> known devices
        self._user_last_login: dict[str, datetime] = {}  # user_id -> last login time
    
    def reset(self):
        super().reset()
        self._user_devices = {}
        self._user_last_login = {}
    
    def _get_or_create_known_device(self, user: User) -> Device:
        """Get a known device for user, or create one."""
        if user.user_id not in self._user_devices:
            # Create 1-3 known devices for new user
            num_devices = self._random_int(1, 3)
            devices = []
            for i in range(num_devices):
                is_mobile = i > 0 and self._random_bool(0.5)  # First device usually desktop
                device = self.generate_device(is_mobile=is_mobile)
                device.is_known = True
                device.first_seen_at = datetime.utcnow() - timedelta(days=self._random_int(30, 365))
                devices.append(device)
            self._user_devices[user.user_id] = devices
        
        return self._random_choice(self._user_devices[user.user_id])
    
    def generate_login_event(
        self,
        session: Session,
        user: User,
        device: Device,
        timestamp: datetime,
    ) -> LoginEvent:
        """Generate a legitimate login event."""
        self._event_counter += 1
        
        # Calculate time since last login
        last_login = self._user_last_login.get(user.user_id)
        if last_login:
            hours_since = (timestamp - last_login).total_seconds() / 3600
        else:
            hours_since = self._random_float(1, 168)  # 1 hour to 1 week
        
        # Update last login
        self._user_last_login[user.user_id] = timestamp
        
        # Legitimate logins: mostly successful, low failed attempts
        failed_before = 0 if self._random_bool(0.95) else self._random_int(1, 2)
        success = self._random_bool(0.98)  # 98% success rate
        
        return LoginEvent(
            event_id=self._generate_id("evt", self._event_counter),
            session_id=session.session_id,
            user_id=user.user_id,
            timestamp=timestamp,
            success=success,
            auth_method=self._random_choice(["password", "password", "mfa", "sso"]),
            failed_attempts_before=failed_before,
            time_since_last_login_hours=round(hours_since, 2),
            is_new_device=not device.is_known,
            is_new_ip=self._random_bool(0.1),  # 10% new IP (dynamic IPs, etc.)
            is_new_location=False,  # Legit users login from home
            is_ato=False,  # Ground truth: NOT an ATO
        )
    
    def generate_legit_scenario(
        self,
        user: User,
        base_time: datetime,
        num_events: int = 1,
    ) -> List[Tuple[Session, Device, LoginEvent]]:
        """Generate a complete legitimate login scenario.
        
        Returns list of (Session, Device, LoginEvent) tuples.
        """
        results = []
        current_time = base_time
        
        for i in range(num_events):
            # Get known device
            device = self._get_or_create_known_device(user)
            
            # Generate session from home location
            session = self.generate_session(
                user=user,
                device=device,
                timestamp=current_time,
                geo_city=user.home_city,
                geo_country=user.home_country,
                is_vpn=self._random_bool(0.05),  # 5% VPN use is normal
                is_tor=False,
            )
            
            # Generate login event
            event = self.generate_login_event(session, user, device, current_time)
            
            results.append((session, device, event))
            
            # Time gap between logins (1-48 hours for legit users)
            gap_hours = self._random_float(1, 48)
            current_time = current_time + timedelta(hours=gap_hours)
        
        return results
