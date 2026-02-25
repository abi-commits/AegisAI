"""
AegisAI HTTP Load Test — Locust
================================
Exercises the real HTTP API layer (POST /evaluate-login) end-to-end.
Complements benchmarks/latency_benchmark.py, which benchmarks the
in-process DecisionFlow directly without going through the network stack.

Usage (headless, 200 concurrent users, 60-second run):

    locust -f benchmarks/locustfile.py \\
           --headless -u 200 -r 20 --run-time 60s \\
           --host http://localhost:8000

    # Or against the Docker-composed API:
    docker compose up aegis-api -d
    locust -f benchmarks/locustfile.py \\
           --headless -u 200 -r 20 --run-time 60s \\
           --host http://localhost:8000

    # Interactive web UI (browse to http://localhost:8089):
    locust -f benchmarks/locustfile.py --host http://localhost:8000

Key stats emitted at test end
------------------------------
  - Total requests / failure count / error rate (%)
  - P50 / P95 / P99 HTTP latency (ms)
  - Requests per second (RPS) at steady state
  - Mean CPU utilisation (%) + peak CPU (%) sampled via psutil
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import deque
from datetime import datetime, timezone

import psutil
from locust import HttpUser, between, events, task

# ---------------------------------------------------------------------------
# CPU utilisation sampler — runs in a background thread during the test
# ---------------------------------------------------------------------------

_cpu_samples: deque[float] = deque()
_cpu_sampler_stop = threading.Event()


def _sample_cpu() -> None:
    """Collect system-wide CPU% every second until signalled to stop."""
    while not _cpu_sampler_stop.is_set():
        _cpu_samples.append(psutil.cpu_percent(interval=None))
        time.sleep(1.0)


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Start the CPU sampler thread and prime the psutil baseline reading."""
    _cpu_samples.clear()
    _cpu_sampler_stop.clear()
    # Prime psutil — first call always returns 0.0
    psutil.cpu_percent(interval=None)
    t = threading.Thread(target=_sample_cpu, daemon=True, name="cpu-sampler")
    t.start()
    print("\n[aegis-load-test] CPU sampler started.")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Stop the CPU sampler and print a consolidated results summary."""
    _cpu_sampler_stop.set()

    stats = environment.runner.stats.total
    req_count = stats.num_requests
    fail_count = stats.num_failures
    error_rate = (fail_count / req_count * 100) if req_count > 0 else 0.0

    p50 = stats.get_response_time_percentile(0.50) or 0
    p95 = stats.get_response_time_percentile(0.95) or 0
    p99 = stats.get_response_time_percentile(0.99) or 0
    rps = stats.current_rps

    cpu_list = list(_cpu_samples)
    mean_cpu = sum(cpu_list) / len(cpu_list) if cpu_list else 0.0
    peak_cpu = max(cpu_list) if cpu_list else 0.0

    print("\n" + "=" * 60)
    print("  AegisAI Load Test Results")
    print("=" * 60)
    print(f"  Requests        : {req_count:>8,}")
    print(f"  Failures        : {fail_count:>8,}")
    print(f"  Error rate      : {error_rate:>7.2f}%")
    print(f"  RPS (current)   : {rps:>7.1f}")
    print(f"  P50 latency     : {p50:>7} ms")
    print(f"  P95 latency     : {p95:>7} ms  ← target < 450 ms")
    print(f"  P99 latency     : {p99:>7} ms")
    print(f"  CPU mean        : {mean_cpu:>7.1f}%")
    print(f"  CPU peak        : {peak_cpu:>7.1f}%")
    print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# Payload factories
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normal_login_payload() -> dict:
    """Low-risk profile — known device, in-hours, no VPN/Tor, no prior failures."""
    uid = f"user_{uuid.uuid4().hex[:8]}"
    did = f"dev_{uuid.uuid4().hex[:8]}"
    return {
        "login_event": {
            "event_id": f"evt_{uuid.uuid4().hex[:12]}",
            "timestamp": _now_iso(),
            "success": True,
            "auth_method": "password",
            "failed_attempts_before": 0,
            "time_since_last_login_hours": 12.0,
            "is_new_device": False,
            "is_new_ip": False,
            "is_new_location": False,
        },
        "session": {
            "session_id": f"sess_{uuid.uuid4().hex[:12]}",
            "device_id": did,
            "ip_address": "203.0.113.42",
            "geo_location": {
                "city": "New York",
                "country": "US",
                "latitude": 40.7128,
                "longitude": -74.006,
            },
            "start_time": _now_iso(),
            "is_vpn": False,
            "is_tor": False,
        },
        "device": {
            "device_id": did,
            "device_type": "desktop",
            "os": "Windows 11",
            "browser": "Chrome 120",
            "is_known": True,
            "first_seen_at": "2025-06-15T10:30:00+00:00",
        },
        "user": {
            "user_id": uid,
            "account_age_days": 420,
            "home_country": "US",
            "home_city": "New York",
            "typical_login_hour_start": 8,
            "typical_login_hour_end": 18,
        },
    }


def _suspicious_login_payload() -> dict:
    """High-risk profile — new device, new IP, VPN+Tor, off-hours, prior failures."""
    uid = f"user_{uuid.uuid4().hex[:8]}"
    did = f"dev_{uuid.uuid4().hex[:8]}"
    return {
        "login_event": {
            "event_id": f"evt_{uuid.uuid4().hex[:12]}",
            "timestamp": _now_iso(),
            "success": True,
            "auth_method": "password",
            "failed_attempts_before": 4,
            "time_since_last_login_hours": 312.0,
            "is_new_device": True,
            "is_new_ip": True,
            "is_new_location": True,
        },
        "session": {
            "session_id": f"sess_{uuid.uuid4().hex[:12]}",
            "device_id": did,
            "ip_address": "198.51.100.77",
            "geo_location": {
                "city": "Amsterdam",
                "country": "NL",
                "latitude": 52.3676,
                "longitude": 4.9041,
            },
            "start_time": _now_iso(),
            "is_vpn": True,
            "is_tor": True,
        },
        "device": {
            "device_id": did,
            "device_type": "mobile",
            "os": "Android 14",
            "browser": "Firefox 121",
            "is_known": False,
            "first_seen_at": _now_iso(),
        },
        "user": {
            "user_id": uid,
            "account_age_days": 30,
            "home_country": "US",
            "home_city": "Chicago",
            "typical_login_hour_start": 9,
            "typical_login_hour_end": 17,
        },
    }


# ---------------------------------------------------------------------------
# Locust user
# ---------------------------------------------------------------------------

class AegisUser(HttpUser):
    """
    Simulates a mix of real-world traffic against POST /evaluate-login.

    Task weighting:
      - 80% normal (low-risk) logins  → expected outcome: ALLOW
      - 20% suspicious (high-risk) logins → expected outcome: BLOCK / CHALLENGE

    Wait time: 0.1–0.5 s between requests per user, yielding ~400–2000 RPS
    at 200 concurrent users.
    """

    wait_time = between(0.1, 0.5)

    def on_start(self):
        """Verify the API is healthy before sending evaluation requests."""
        with self.client.get("/health", catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Health check failed: HTTP {resp.status_code}")

    @task(8)
    def normal_login(self):
        """Low-risk login — exercises the ALLOW / CHALLENGE happy path."""
        with self.client.post(
            "/evaluate-login",
            json=_normal_login_payload(),
            name="POST /evaluate-login [normal]",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                body = response.json()
                if "decision" not in body:
                    response.failure("Response missing 'decision' field")
            elif response.status_code in (400, 422):
                response.failure(f"Validation error: {response.text[:200]}")
            else:
                response.failure(f"Unexpected HTTP {response.status_code}")

    @task(2)
    def suspicious_login(self):
        """High-risk login — exercises the BLOCK / ESCALATE path."""
        with self.client.post(
            "/evaluate-login",
            json=_suspicious_login_payload(),
            name="POST /evaluate-login [suspicious]",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                body = response.json()
                if "decision" not in body:
                    response.failure("Response missing 'decision' field")
            elif response.status_code in (400, 422):
                response.failure(f"Validation error: {response.text[:200]}")
            else:
                response.failure(f"Unexpected HTTP {response.status_code}")
