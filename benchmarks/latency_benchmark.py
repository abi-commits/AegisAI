import time
import numpy as np
import concurrent.futures
from datetime import datetime, timezone
from aegis_ai.data.schemas import User, Device, Session, LoginEvent, GeoLocation
from aegis_ai.orchestration.decision_context import InputContext
from aegis_ai.orchestration.decision_flow import DecisionFlow

def create_mock_context():
    user = User(
        user_id="user_bench_001",
        account_age_days=365,
        home_country="US",
        home_city="New York",
        typical_login_hour_start=8,
        typical_login_hour_end=18,
    )
    device = Device(
        device_id="device_bench_001",
        device_type="desktop",
        os="Windows 11",
        browser="Chrome 120",
        is_known=True,
        first_seen_at=datetime.now(timezone.utc),
    )
    session = Session(
        session_id="session_bench_001",
        user_id="user_bench_001",
        start_time=datetime.now(timezone.utc),
        device_id=device.device_id,
        ip_address="192.168.1.1",
        geo_location=GeoLocation(
            city="New York",
            country="US",
            latitude=40.7128,
            longitude=-74.0060,
        ),
        is_vpn=False,
        is_tor=False,
    )
    login_event = LoginEvent(
        event_id="event_bench_001",
        session_id=session.session_id,
        user_id=user.user_id,
        timestamp=datetime.now(timezone.utc),
        success=True,
        auth_method="password",
        failed_attempts_before=0,
        time_since_last_login_hours=24.0,
    )
    return InputContext(
        login_event=login_event,
        session=session,
        device=device,
        user=user,
    )

def run_latency_benchmark(iterations=100):
    flow = DecisionFlow()
    context = create_mock_context()
    
    print(f"--- Latency Benchmark ({iterations} iterations) ---")
    
    latencies = []
    
    # Warmup
    flow.process(context)
    
    for i in range(iterations):
        start_time = time.perf_counter()
        flow.process(context)
        end_time = time.perf_counter()
        
        latency_ms = (end_time - start_time) * 1000
        latencies.append(latency_ms)
        
        if (i + 1) % 20 == 0:
            print(f"  Completed {i + 1}/{iterations} iterations")
            
    print("\nLatency Results:")
    print(f"  Mean:   {np.mean(latencies):.2f} ms")
    print(f"  Median: {np.median(latencies):.2f} ms")
    print(f"  P95:    {np.percentile(latencies, 95):.2f} ms")
    print(f"  P99:    {np.percentile(latencies, 99):.2f} ms")
    print("-" * 40)
    return latencies

def run_throughput_benchmark(total_requests=500, concurrent_users=10):
    flow = DecisionFlow()
    context = create_mock_context()
    
    print(f"\n--- Throughput Benchmark ({total_requests} requests, {concurrent_users} concurrent) ---")
    
    start_time = time.perf_counter()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_users) as executor:
        futures = [executor.submit(flow.process, context) for _ in range(total_requests)]
        concurrent.futures.wait(futures)
        
    end_time = time.perf_counter()
    total_time = end_time - start_time
    
    throughput = total_requests / total_time
    
    print(f"\nThroughput Results:")
    print(f"  Total Time: {total_time:.2f} s")
    print(f"  Throughput: {throughput:.2f} requests/sec")
    print("-" * 40)
    return throughput

if __name__ == "__main__":
    run_latency_benchmark()
    run_throughput_benchmark()
