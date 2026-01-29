"""Base synthetic data generator with deterministic seeding."""

import random
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod

from aegis_ai.data.schemas import User, Device, Session, GeoLocation, LoginEvent


# Realistic data pools
COUNTRIES = ["US", "GB", "CA", "DE", "FR", "JP", "AU", "NL", "SE", "CH"]

CITIES_BY_COUNTRY = {
    "US": ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "San Francisco", "Seattle"],
    "GB": ["London", "Manchester", "Birmingham", "Leeds", "Glasgow"],
    "CA": ["Toronto", "Vancouver", "Montreal", "Calgary", "Ottawa"],
    "DE": ["Berlin", "Munich", "Hamburg", "Frankfurt", "Cologne"],
    "FR": ["Paris", "Lyon", "Marseille", "Toulouse", "Nice"],
    "JP": ["Tokyo", "Osaka", "Kyoto", "Yokohama", "Nagoya"],
    "AU": ["Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide"],
    "NL": ["Amsterdam", "Rotterdam", "The Hague", "Utrecht"],
    "SE": ["Stockholm", "Gothenburg", "Malmö", "Uppsala"],
    "CH": ["Zurich", "Geneva", "Basel", "Bern"],
}

# Approximate coordinates for cities (for geo realism)
CITY_COORDS = {
    "New York": (40.7128, -74.0060),
    "Los Angeles": (34.0522, -118.2437),
    "Chicago": (41.8781, -87.6298),
    "Houston": (29.7604, -95.3698),
    "Phoenix": (33.4484, -112.0740),
    "San Francisco": (37.7749, -122.4194),
    "Seattle": (47.6062, -122.3321),
    "London": (51.5074, -0.1278),
    "Manchester": (53.4808, -2.2426),
    "Birmingham": (52.4862, -1.8904),
    "Leeds": (53.8008, -1.5491),
    "Glasgow": (55.8642, -4.2518),
    "Toronto": (43.6532, -79.3832),
    "Vancouver": (49.2827, -123.1207),
    "Montreal": (45.5017, -73.5673),
    "Calgary": (51.0447, -114.0719),
    "Ottawa": (45.4215, -75.6972),
    "Berlin": (52.5200, 13.4050),
    "Munich": (48.1351, 11.5820),
    "Hamburg": (53.5511, 9.9937),
    "Frankfurt": (50.1109, 8.6821),
    "Cologne": (50.9375, 6.9603),
    "Paris": (48.8566, 2.3522),
    "Lyon": (45.7640, 4.8357),
    "Marseille": (43.2965, 5.3698),
    "Toulouse": (43.6047, 1.4442),
    "Nice": (43.7102, 7.2620),
    "Tokyo": (35.6762, 139.6503),
    "Osaka": (34.6937, 135.5023),
    "Kyoto": (35.0116, 135.7681),
    "Yokohama": (35.4437, 139.6380),
    "Nagoya": (35.1815, 136.9066),
    "Sydney": (-33.8688, 151.2093),
    "Melbourne": (-37.8136, 144.9631),
    "Brisbane": (-27.4698, 153.0251),
    "Perth": (-31.9505, 115.8605),
    "Adelaide": (-34.9285, 138.6007),
    "Amsterdam": (52.3676, 4.9041),
    "Rotterdam": (51.9244, 4.4777),
    "The Hague": (52.0705, 4.3007),
    "Utrecht": (52.0907, 5.1214),
    "Stockholm": (59.3293, 18.0686),
    "Gothenburg": (57.7089, 11.9746),
    "Malmö": (55.6050, 13.0038),
    "Uppsala": (59.8586, 17.6389),
    "Zurich": (47.3769, 8.5417),
    "Geneva": (46.2044, 6.1432),
    "Basel": (47.5596, 7.5886),
    "Bern": (46.9480, 7.4474),
}

OS_LIST = ["Windows 11", "Windows 10", "macOS 14", "macOS 13", "Ubuntu 22.04", "iOS 17", "Android 14"]
BROWSER_LIST = ["Chrome 120", "Chrome 119", "Firefox 121", "Safari 17", "Edge 120"]
DEVICE_TYPES = ["desktop", "mobile", "tablet"]


class BaseGenerator(ABC):
    """Base class for synthetic data generators.
    
    All generators must be deterministic given the same seed.
    """
    
    def __init__(self, seed: int = 42):
        """Initialize generator with seed for reproducibility."""
        self.seed = seed
        self.rng = random.Random(seed)
        self._user_counter = 0
        self._device_counter = 0
        self._session_counter = 0
        self._event_counter = 0
    
    def reset(self):
        """Reset generator to initial state."""
        self.rng = random.Random(self.seed)
        self._user_counter = 0
        self._device_counter = 0
        self._session_counter = 0
        self._event_counter = 0
    
    def _generate_id(self, prefix: str, counter: int) -> str:
        """Generate deterministic ID."""
        raw = f"{prefix}_{self.seed}_{counter}"
        return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:12]}"
    
    def _random_choice(self, items: list) -> Any:
        """Deterministic random choice."""
        return self.rng.choice(items)
    
    def _random_int(self, low: int, high: int) -> int:
        """Deterministic random integer."""
        return self.rng.randint(low, high)
    
    def _random_float(self, low: float, high: float) -> float:
        """Deterministic random float."""
        return self.rng.uniform(low, high)
    
    def _random_bool(self, probability: float = 0.5) -> bool:
        """Deterministic random boolean with given probability."""
        return self.rng.random() < probability
    
    def generate_user(self) -> User:
        """Generate a synthetic user."""
        self._user_counter += 1
        country = self._random_choice(COUNTRIES)
        city = self._random_choice(CITIES_BY_COUNTRY[country])
        
        # Typical login window (e.g., 8am-6pm or 9am-9pm)
        start_hour = self._random_int(6, 10)
        end_hour = self._random_int(17, 22)
        
        return User(
            user_id=self._generate_id("user", self._user_counter),
            account_age_days=self._random_int(1, 2000),
            home_country=country,
            home_city=city,
            typical_login_hour_start=start_hour,
            typical_login_hour_end=end_hour,
        )
    
    def generate_device(self, is_mobile: bool = False) -> Device:
        """Generate a synthetic device."""
        self._device_counter += 1
        
        if is_mobile:
            device_type = self._random_choice(["mobile", "tablet"])
            os = self._random_choice(["iOS 17", "Android 14"])
            browser = self._random_choice(["Safari 17", "Chrome 120"])
        else:
            device_type = "desktop"
            os = self._random_choice(["Windows 11", "Windows 10", "macOS 14", "macOS 13", "Ubuntu 22.04"])
            browser = self._random_choice(["Chrome 120", "Firefox 121", "Safari 17", "Edge 120"])
        
        return Device(
            device_id=self._generate_id("dev", self._device_counter),
            device_type=device_type,
            os=os,
            browser=browser,
            is_known=False,
            first_seen_at=None,
        )
    
    def generate_geo_location(self, city: str, country: str) -> GeoLocation:
        """Generate geo location with coordinates."""
        coords = CITY_COORDS.get(city, (0.0, 0.0))
        # Add small random offset for realism
        lat = coords[0] + self._random_float(-0.1, 0.1)
        lon = coords[1] + self._random_float(-0.1, 0.1)
        
        return GeoLocation(
            city=city,
            country=country,
            latitude=round(lat, 4),
            longitude=round(lon, 4),
        )
    
    def generate_ip_address(self) -> str:
        """Generate a plausible IP address."""
        # Avoid reserved ranges
        first_octet = self._random_choice([
            self._random_int(1, 126),
            self._random_int(128, 191),
            self._random_int(192, 223),
        ])
        return f"{first_octet}.{self._random_int(0, 255)}.{self._random_int(0, 255)}.{self._random_int(1, 254)}"
    
    def generate_session(
        self,
        user: User,
        device: Device,
        timestamp: datetime,
        geo_city: Optional[str] = None,
        geo_country: Optional[str] = None,
        is_vpn: bool = False,
        is_tor: bool = False,
    ) -> Session:
        """Generate a session for a user."""
        self._session_counter += 1
        
        city = geo_city or user.home_city
        country = geo_country or user.home_country
        
        return Session(
            session_id=self._generate_id("sess", self._session_counter),
            user_id=user.user_id,
            device_id=device.device_id,
            ip_address=self.generate_ip_address(),
            geo_location=self.generate_geo_location(city, country),
            start_time=timestamp,
            is_vpn=is_vpn,
            is_tor=is_tor,
        )
    
    @abstractmethod
    def generate_login_event(
        self,
        session: Session,
        user: User,
        device: Device,
        timestamp: datetime,
    ) -> LoginEvent:
        """Generate a login event. Must be implemented by subclasses."""
        pass
