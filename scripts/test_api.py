"""Quick test script for the API Gateway."""

from fastapi.testclient import TestClient
from aegis_ai.api.gateway import app

client = TestClient(app)

request_data = {
    "login_event": {
        "event_id": "evt_test_001",
        "timestamp": "2026-01-28T14:30:05Z",
        "success": True,
        "auth_method": "password",
        "failed_attempts_before": 0,
        "time_since_last_login_hours": 24.5,
        "is_new_device": False,
        "is_new_ip": False,
        "is_new_location": False,
    },
    "session": {
        "session_id": "sess_test_001",
        "device_id": "dev_test_001",
        "ip_address": "192.168.1.100",
        "geo_location": {
            "city": "New York",
            "country": "US",
            "latitude": 40.7128,
            "longitude": -74.0060,
        },
        "start_time": "2026-01-28T14:30:00Z",
        "is_vpn": False,
        "is_tor": False,
    },
    "device": {
        "device_id": "dev_test_001",
        "device_type": "desktop",
        "os": "Windows 11",
        "browser": "Chrome 120",
        "is_known": True,
        "first_seen_at": "2025-06-15T10:30:00Z",
    },
    "user": {
        "user_id": "user_test_001",
        "account_age_days": 365,
        "home_country": "US",
        "home_city": "New York",
        "typical_login_hour_start": 8,
        "typical_login_hour_end": 18,
    },
}

print("=" * 60)
print("Testing POST /evaluate-login")
print("=" * 60)

response = client.post("/evaluate-login", json=request_data)
print(f"\nStatus code: {response.status_code}")

data = response.json()
print(f"\nResponse:")
import json
print(json.dumps(data, indent=2))

print("\n" + "=" * 60)
print("Response Field Verification")
print("=" * 60)
print(f"decision: {data.get('decision')}")
print(f"confidence: {data.get('confidence')}")
print(f"explanation: {data.get('explanation')[:80] if data.get('explanation') else None}...")
print(f"escalation_flag: {data.get('escalation_flag')}")
print(f"audit_id: {data.get('audit_id')}")

print("\n" + "=" * 60)
print("Security Check: No Agent Outputs Exposed")
print("=" * 60)
forbidden_fields = ["detection", "behavioral", "network", "agent_outputs", 
                   "detection_score", "behavioral_score", "network_score", 
                   "disagreement_score", "risk_factors", "deviation_summary"]
all_passed = True
for field in forbidden_fields:
    if field in data:
        print(f"❌ FAIL: '{field}' exposed!")
        all_passed = False
    else:
        print(f"✓ '{field}' not exposed")

print("\n" + "=" * 60)
if all_passed and response.status_code == 200:
    print("✅ ALL TESTS PASSED!")
else:
    print("❌ TESTS FAILED!")
print("=" * 60)
