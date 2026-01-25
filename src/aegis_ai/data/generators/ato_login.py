"""Account Takeover (ATO) login scenario generator."""

from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Literal

from src.aegis_ai.data.schemas import User, Device, Session, LoginEvent
from aegis_ai.data.generators.base_generator import (
    BaseGenerator,
    COUNTRIES,
    CITIES_BY_COUNTRY,
)


class ATOScenarioType:
    """Common ATO attack patterns."""
    CREDENTIAL_STUFFING = "credential_stuffing"  # Bulk automated attempts
    TARGETED_PHISH = "targeted_phish"  # Single user, stolen creds
    SESSION_HIJACK = "session_hijack"  # Stolen session from new location
    BRUTE_FORCE = "brute_force"  # Many failed attempts
    NEW_DEVICE_FOREIGN = "new_device_foreign"  # New device from foreign country


class ATOLoginGenerator(BaseGenerator):
    """Generates Account Takeover (ATO) login scenarios.
    
    ATO logins have these characteristics:
    - New/unknown devices
    - Unusual locations (often different country)
    - Unusual login times
    - Higher failed attempts
    - VPN/Tor usage
    - Rapid succession (credential stuffing)
    """
    
    def __init__(self, seed: int = 42):
        super().__init__(seed)
    
    def _get_foreign_location(self, user: User) -> Tuple[str, str]:
        """Get a location different from user's home."""
        foreign_countries = [c for c in COUNTRIES if c != user.home_country]
        country = self._random_choice(foreign_countries)
        city = self._random_choice(CITIES_BY_COUNTRY[country])
        return city, country
    
    def _get_unusual_time(self, user: User, base_time: datetime) -> datetime:
        """Get a time outside user's typical login window."""
        # Login at unusual hour (e.g., 3 AM in their timezone)
        unusual_hours = []
        for h in range(24):
            if h < user.typical_login_hour_start or h > user.typical_login_hour_end:
                unusual_hours.append(h)
        
        if unusual_hours:
            unusual_hour = self._random_choice(unusual_hours)
        else:
            unusual_hour = 3  # Default to 3 AM
        
        return base_time.replace(hour=unusual_hour, minute=self._random_int(0, 59))
    
    def generate_login_event(
        self,
        session: Session,
        user: User,
        device: Device,
        timestamp: datetime,
        failed_attempts: int = 0,
        success: bool = True,
    ) -> LoginEvent:
        """Generate an ATO login event."""
        self._event_counter += 1
        
        return LoginEvent(
            event_id=self._generate_id("evt", self._event_counter),
            session_id=session.session_id,
            user_id=user.user_id,
            timestamp=timestamp,
            success=success,
            auth_method="password",  # ATOs usually password-based
            failed_attempts_before=failed_attempts,
            time_since_last_login_hours=self._random_float(0.1, 720),  # Variable
            is_new_device=True,  # ATO always uses new device
            is_new_ip=True,  # ATO always uses new IP
            is_new_location=True,  # ATO usually from new location
            is_ato=True,  # Ground truth: IS an ATO
        )
    
    def generate_credential_stuffing_scenario(
        self,
        user: User,
        base_time: datetime,
        num_attempts: int = 5,
    ) -> List[Tuple[Session, Device, LoginEvent]]:
        """Generate credential stuffing attack scenario.
        
        Characteristics:
        - Many rapid failed attempts
        - Same device (bot)
        - Foreign location
        - Eventually may succeed
        """
        results = []
        current_time = base_time
        
        # Attacker uses one device (bot)
        attacker_device = self.generate_device(is_mobile=False)
        attacker_device.is_known = False
        
        # Foreign location
        city, country = self._get_foreign_location(user)
        
        for i in range(num_attempts):
            session = self.generate_session(
                user=user,
                device=attacker_device,
                timestamp=current_time,
                geo_city=city,
                geo_country=country,
                is_vpn=self._random_bool(0.7),  # Often use VPN
                is_tor=self._random_bool(0.2),
            )
            
            # First N-1 attempts fail, last may succeed
            is_last = (i == num_attempts - 1)
            success = is_last and self._random_bool(0.6)  # 60% chance final succeeds
            
            event = self.generate_login_event(
                session=session,
                user=user,
                device=attacker_device,
                timestamp=current_time,
                failed_attempts=i,
                success=success,
            )
            
            results.append((session, attacker_device, event))
            
            # Very short gaps (seconds to minutes) - automated attack
            gap_seconds = self._random_int(2, 30)
            current_time = current_time + timedelta(seconds=gap_seconds)
        
        return results
    
    def generate_targeted_phish_scenario(
        self,
        user: User,
        base_time: datetime,
    ) -> List[Tuple[Session, Device, LoginEvent]]:
        """Generate targeted phishing attack scenario.
        
        Characteristics:
        - Single attempt (attacker has valid creds)
        - New device
        - Often foreign location
        - Unusual time
        - Usually succeeds on first try
        """
        # Attacker device
        attacker_device = self.generate_device(is_mobile=self._random_bool(0.3))
        attacker_device.is_known = False
        
        # Foreign location
        city, country = self._get_foreign_location(user)
        
        # Unusual time
        attack_time = self._get_unusual_time(user, base_time)
        
        session = self.generate_session(
            user=user,
            device=attacker_device,
            timestamp=attack_time,
            geo_city=city,
            geo_country=country,
            is_vpn=self._random_bool(0.5),
            is_tor=self._random_bool(0.1),
        )
        
        event = self.generate_login_event(
            session=session,
            user=user,
            device=attacker_device,
            timestamp=attack_time,
            failed_attempts=0,  # Attacker has valid creds
            success=True,
        )
        
        return [(session, attacker_device, event)]
    
    def generate_brute_force_scenario(
        self,
        user: User,
        base_time: datetime,
        num_attempts: int = 10,
    ) -> List[Tuple[Session, Device, LoginEvent]]:
        """Generate brute force attack scenario.
        
        Characteristics:
        - Many failed attempts
        - May rotate IPs (different sessions)
        - Usually fails
        """
        results = []
        current_time = base_time
        
        city, country = self._get_foreign_location(user)
        
        for i in range(num_attempts):
            # Attacker may rotate devices/IPs
            attacker_device = self.generate_device(is_mobile=False)
            attacker_device.is_known = False
            
            session = self.generate_session(
                user=user,
                device=attacker_device,
                timestamp=current_time,
                geo_city=city,
                geo_country=country,
                is_vpn=self._random_bool(0.8),
                is_tor=self._random_bool(0.3),
            )
            
            # Brute force: all fail except maybe last
            is_last = (i == num_attempts - 1)
            success = is_last and self._random_bool(0.1)  # 10% chance final succeeds
            
            event = self.generate_login_event(
                session=session,
                user=user,
                device=attacker_device,
                timestamp=current_time,
                failed_attempts=i,
                success=success,
            )
            
            results.append((session, attacker_device, event))
            
            # Short gaps
            gap_seconds = self._random_int(5, 60)
            current_time = current_time + timedelta(seconds=gap_seconds)
        
        return results
    
    def generate_ato_scenario(
        self,
        user: User,
        base_time: datetime,
        scenario_type: str = None,
    ) -> List[Tuple[Session, Device, LoginEvent]]:
        """Generate a complete ATO scenario.
        
        Args:
            user: Target user
            base_time: Attack start time
            scenario_type: One of ATOScenarioType values, or random if None
            
        Returns:
            List of (Session, Device, LoginEvent) tuples
        """
        if scenario_type is None:
            scenario_type = self._random_choice([
                ATOScenarioType.CREDENTIAL_STUFFING,
                ATOScenarioType.TARGETED_PHISH,
                ATOScenarioType.BRUTE_FORCE,
            ])
        
        if scenario_type == ATOScenarioType.CREDENTIAL_STUFFING:
            return self.generate_credential_stuffing_scenario(
                user, base_time, num_attempts=self._random_int(3, 8)
            )
        elif scenario_type == ATOScenarioType.TARGETED_PHISH:
            return self.generate_targeted_phish_scenario(user, base_time)
        elif scenario_type == ATOScenarioType.BRUTE_FORCE:
            return self.generate_brute_force_scenario(
                user, base_time, num_attempts=self._random_int(5, 15)
            )
        else:
            # Default to targeted phish
            return self.generate_targeted_phish_scenario(user, base_time)
