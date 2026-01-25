#!/usr/bin/env python3
"""Generate synthetic dataset for AegisAI.

Usage:
    python generate_dataset.py --seed 42 --users 100 --ato-ratio 0.1
    
Output:
    - Users, Sessions, LoginEvents
    - Mix of legitimate and ATO scenarios
    - All objects validated against schemas
"""

import argparse
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any
from dataclasses import dataclass

from src.aegis_ai.data.schemas import User, Device, Session, LoginEvent
from aegis_ai.data.generators.legit_login import LegitLoginGenerator
from aegis_ai.data.generators.ato_login import ATOLoginGenerator, ATOScenarioType
from src.aegis_ai.data.validators.schema_validator import validate_all


@dataclass
class DatasetStats:
    """Statistics about generated dataset."""
    total_users: int
    total_sessions: int
    total_events: int
    legit_events: int
    ato_events: int
    ato_ratio: float


class DatasetGenerator:
    """Generates complete synthetic dataset."""
    
    def __init__(self, seed: int = 42):
        self.seed = seed
        self.legit_gen = LegitLoginGenerator(seed=seed)
        self.ato_gen = ATOLoginGenerator(seed=seed + 1000)  # Different seed for ATO
        
        # Generated data
        self.users: List[User] = []
        self.devices: List[Device] = []
        self.sessions: List[Session] = []
        self.events: List[LoginEvent] = []
    
    def reset(self):
        """Reset generators and data."""
        self.legit_gen.reset()
        self.ato_gen.reset()
        self.users = []
        self.devices = []
        self.sessions = []
        self.events = []
    
    def generate(
        self,
        num_users: int = 100,
        events_per_user: int = 5,
        ato_ratio: float = 0.1,
        base_time: datetime = None,
    ) -> DatasetStats:
        """Generate complete dataset.
        
        Args:
            num_users: Number of users to generate
            events_per_user: Average login events per user
            ato_ratio: Fraction of users who experience ATO (0.0-1.0)
            base_time: Starting timestamp for events
            
        Returns:
            DatasetStats with generation summary
        """
        self.reset()
        base_time = base_time or datetime.utcnow() - timedelta(days=30)
        
        num_ato_users = int(num_users * ato_ratio)
        num_legit_users = num_users - num_ato_users
        
        # Track stats
        legit_event_count = 0
        ato_event_count = 0
        
        # Generate users with legitimate logins
        for i in range(num_legit_users):
            user = self.legit_gen.generate_user()
            self.users.append(user)
            
            # Generate legit login history
            user_time = base_time + timedelta(hours=i * 2)
            scenarios = self.legit_gen.generate_legit_scenario(
                user=user,
                base_time=user_time,
                num_events=events_per_user,
            )
            
            for session, device, event in scenarios:
                self.sessions.append(session)
                if device not in self.devices:
                    self.devices.append(device)
                self.events.append(event)
                legit_event_count += 1
        
        # Generate users who experience ATO
        for i in range(num_ato_users):
            user = self.ato_gen.generate_user()
            self.users.append(user)
            
            user_time = base_time + timedelta(hours=(num_legit_users + i) * 2)
            
            # First, generate some legit history
            legit_scenarios = self.legit_gen.generate_legit_scenario(
                user=user,
                base_time=user_time,
                num_events=max(1, events_per_user - 2),  # Some legit history
            )
            
            for session, device, event in legit_scenarios:
                self.sessions.append(session)
                if device not in self.devices:
                    self.devices.append(device)
                self.events.append(event)
                legit_event_count += 1
            
            # Then, generate ATO attack
            ato_time = user_time + timedelta(days=self.ato_gen._random_int(1, 7))
            ato_scenarios = self.ato_gen.generate_ato_scenario(
                user=user,
                base_time=ato_time,
            )
            
            for session, device, event in ato_scenarios:
                self.sessions.append(session)
                if device not in self.devices:
                    self.devices.append(device)
                self.events.append(event)
                ato_event_count += 1
        
        return DatasetStats(
            total_users=len(self.users),
            total_sessions=len(self.sessions),
            total_events=len(self.events),
            legit_events=legit_event_count,
            ato_events=ato_event_count,
            ato_ratio=ato_event_count / max(1, len(self.events)),
        )
    
    def to_dict(self) -> Dict[str, List[Dict[str, Any]]]:
        """Export dataset as dictionary."""
        return {
            "users": [u.model_dump(mode="json") for u in self.users],
            "devices": [d.model_dump(mode="json") for d in self.devices],
            "sessions": [s.model_dump(mode="json") for s in self.sessions],
            "events": [e.model_dump(mode="json") for e in self.events],
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Export dataset as JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)


def print_ato_scenario(generator: DatasetGenerator):
    """Print one full ATO scenario for verification."""
    print("\n" + "=" * 70)
    print("EXAMPLE ATO SCENARIO (End-to-End)")
    print("=" * 70)
    
    # Find a user with ATO events
    ato_events = [e for e in generator.events if e.is_ato]
    if not ato_events:
        print("No ATO events in dataset")
        return
    
    # Get first ATO event
    ato_event = ato_events[0]
    
    # Find associated user, session
    user = next((u for u in generator.users if u.user_id == ato_event.user_id), None)
    session = next((s for s in generator.sessions if s.session_id == ato_event.session_id), None)
    device = next((d for d in generator.devices if d.device_id == session.device_id), None) if session else None
    
    print(f"\n👤 TARGET USER:")
    print(f"   ID: {user.user_id}")
    print(f"   Home: {user.home_city}, {user.home_country}")
    print(f"   Account age: {user.account_age_days} days")
    print(f"   Typical hours: {user.typical_login_hour_start}:00 - {user.typical_login_hour_end}:00")
    
    if device:
        print(f"\n💻 ATTACKER DEVICE:")
        print(f"   ID: {device.device_id}")
        print(f"   Type: {device.device_type}")
        print(f"   OS: {device.os}")
        print(f"   Browser: {device.browser}")
        print(f"   Known: {device.is_known}")
    
    if session:
        print(f"\n🌐 SESSION:")
        print(f"   ID: {session.session_id}")
        print(f"   IP: {session.ip_address}")
        print(f"   Location: {session.geo_location.city}, {session.geo_location.country}")
        print(f"   VPN: {session.is_vpn}")
        print(f"   Tor: {session.is_tor}")
    
    print(f"\n⚠️ LOGIN EVENT (ATO):")
    print(f"   ID: {ato_event.event_id}")
    print(f"   Timestamp: {ato_event.timestamp}")
    print(f"   Success: {ato_event.success}")
    print(f"   Failed attempts before: {ato_event.failed_attempts_before}")
    print(f"   New device: {ato_event.is_new_device}")
    print(f"   New IP: {ato_event.is_new_ip}")
    print(f"   New location: {ato_event.is_new_location}")
    print(f"   IS ATO (ground truth): {ato_event.is_ato}")
    
    # Find all events for this user
    user_events = [e for e in generator.events if e.user_id == ato_event.user_id]
    print(f"\n📊 USER EVENT HISTORY:")
    print(f"   Total events: {len(user_events)}")
    print(f"   Legit events: {len([e for e in user_events if not e.is_ato])}")
    print(f"   ATO events: {len([e for e in user_events if e.is_ato])}")


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic AegisAI dataset")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--users", type=int, default=100, help="Number of users to generate")
    parser.add_argument("--events-per-user", type=int, default=5, help="Events per user")
    parser.add_argument("--ato-ratio", type=float, default=0.1, help="Fraction of users with ATO")
    parser.add_argument("--output", type=str, default=None, help="Output JSON file path")
    parser.add_argument("--validate", action="store_true", help="Validate all generated objects")
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("AEGISAI SYNTHETIC DATA GENERATOR")
    print("=" * 70)
    print(f"\nParameters:")
    print(f"  Seed: {args.seed}")
    print(f"  Users: {args.users}")
    print(f"  Events per user: {args.events_per_user}")
    print(f"  ATO ratio: {args.ato_ratio:.1%}")
    
    # Generate dataset
    generator = DatasetGenerator(seed=args.seed)
    stats = generator.generate(
        num_users=args.users,
        events_per_user=args.events_per_user,
        ato_ratio=args.ato_ratio,
    )
    
    print(f"\n✓ Generated:")
    print(f"  Users: {stats.total_users}")
    print(f"  Sessions: {stats.total_sessions}")
    print(f"  Events: {stats.total_events}")
    print(f"    - Legitimate: {stats.legit_events}")
    print(f"    - ATO: {stats.ato_events}")
    print(f"  Actual ATO ratio: {stats.ato_ratio:.1%}")
    
    # Validate if requested
    if args.validate:
        print("\n🔍 Validating schemas...")
        validation_results = validate_all(
            users=generator.users,
            devices=generator.devices,
            sessions=generator.sessions,
            events=generator.events,
        )
        if validation_results["valid"]:
            print("✓ All objects validated successfully!")
        else:
            print(f"✗ Validation errors: {validation_results['errors']}")
    
    # Print ATO scenario
    print_ato_scenario(generator)
    
    # Verify determinism
    print("\n" + "=" * 70)
    print("DETERMINISM CHECK")
    print("=" * 70)
    
    # Generate again with same seed
    generator2 = DatasetGenerator(seed=args.seed)
    stats2 = generator2.generate(
        num_users=args.users,
        events_per_user=args.events_per_user,
        ato_ratio=args.ato_ratio,
    )
    
    # Compare first user
    if generator.users and generator2.users:
        same_user = generator.users[0].user_id == generator2.users[0].user_id
        same_events = len(generator.events) == len(generator2.events)
        print(f"  Same first user ID: {same_user}")
        print(f"  Same event count: {same_events}")
        if same_user and same_events:
            print("✓ Deterministic: Same seed produces identical data!")
        else:
            print("✗ WARNING: Non-deterministic output detected!")
    
    # Output to file
    if args.output:
        with open(args.output, "w") as f:
            f.write(generator.to_json())
        print(f"\n✓ Dataset saved to: {args.output}")
    
    print("\n" + "=" * 70)
    print("DONE")
    print("=" * 70)


if __name__ == "__main__":
    main()
