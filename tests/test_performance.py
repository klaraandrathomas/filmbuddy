#!/usr/bin/env python3
"""
Performance Tests for FilmBuddy (Step 9)

Tests response times and system performance metrics.
"""

import requests
import time
import statistics
from typing import List


BASE_URL = "http://localhost:8000"


def measure_query_latency(num_requests: int = 10) -> List[float]:
    """Measure query response times."""
    print(f"\n[Test 1/2] Measuring query latency ({num_requests} requests)...")
    
    latencies = []
    
    test_queries = [
        {"film_id": "la_la_land", "t_now": 845.0, "query": "What is happening?", "spoiler_mode": "off"},
        {"film_id": "la_la_land", "t_now": 600.0, "query": "Who is that?", "spoiler_mode": "off"},
        {"film_id": "la_la_land", "t_now": 2400.0, "query": "What is this scene about?", "spoiler_mode": "off"},
    ]
    
    for i in range(num_requests):
        payload = test_queries[i % len(test_queries)]
        
        start = time.time()
        response = requests.post(f"{BASE_URL}/ask", json=payload)
        elapsed = time.time() - start
        
        if response.status_code == 200:
            latencies.append(elapsed)
            print(f"  Request {i+1}: {elapsed:.3f}s")
        else:
            print(f"  Request {i+1}: FAILED (status {response.status_code})")
    
    if latencies:
        print(f"\n  Statistics:")
        print(f"    Min:    {min(latencies):.3f}s")
        print(f"    Max:    {max(latencies):.3f}s")
        print(f"    Mean:   {statistics.mean(latencies):.3f}s")
        print(f"    Median: {statistics.median(latencies):.3f}s")
        
        # Target: < 3 seconds average
        avg_latency = statistics.mean(latencies)
        if avg_latency < 3.0:
            print(f"  ✅ PASS: Average latency {avg_latency:.3f}s < 3.0s target")
            return latencies
        else:
            print(f"  ⚠️  WARNING: Average latency {avg_latency:.3f}s exceeds 3.0s target")
            return latencies
    else:
        print(f"  ❌ FAIL: No successful requests")
        return []


def test_concurrent_requests():
    """Test handling of concurrent requests."""
    print(f"\n[Test 2/2] Testing concurrent request handling...")
    
    import concurrent.futures
    
    def make_request(i):
        payload = {
            "film_id": "la_la_land",
            "t_now": 500.0 + (i * 100),
            "query": f"What is happening at this moment?",
            "spoiler_mode": "off"
        }
        start = time.time()
        response = requests.post(f"{BASE_URL}/ask", json=payload)
        elapsed = time.time() - start
        return response.status_code == 200, elapsed
    
    num_concurrent = 5
    
    print(f"  Sending {num_concurrent} concurrent requests...")
    
    start_time = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_concurrent) as executor:
        results = list(executor.map(make_request, range(num_concurrent)))
    total_time = time.time() - start_time
    
    successes = sum(1 for success, _ in results if success)
    latencies = [elapsed for success, elapsed in results if success]
    
    print(f"  ✓ Completed in: {total_time:.3f}s")
    print(f"  ✓ Successful: {successes}/{num_concurrent}")
    
    if latencies:
        print(f"  ✓ Average latency: {statistics.mean(latencies):.3f}s")
    
    if successes == num_concurrent:
        print(f"  ✅ PASS: All concurrent requests succeeded")
        return True
    else:
        print(f"  ⚠️  WARNING: Some requests failed")
        return False


def test_embedding_performance():
    """Test embedding generation performance."""
    print(f"\n[Bonus Test] Testing embedding performance...")
    
    # Test with different query lengths
    queries = [
        "Who?",  # Short
        "What is happening in this scene?",  # Medium
        "Can you explain what the characters are doing and why this moment is important to the story?",  # Long
    ]
    
    for i, query in enumerate(queries, 1):
        payload = {
            "film_id": "la_la_land",
            "t_now": 845.0,
            "query": query,
            "spoiler_mode": "off"
        }
        
        start = time.time()
        response = requests.post(f"{BASE_URL}/ask", json=payload)
        elapsed = time.time() - start
        
        if response.status_code == 200:
            data = response.json()
            num_hits = len(data.get("hits", []))
            print(f"  Query {i} ({len(query)} chars): {elapsed:.3f}s, {num_hits} hits")
        else:
            print(f"  Query {i}: FAILED")
    
    return True


def run_performance_tests():
    """Run all performance tests."""
    print("="*70)
    print("STEP 9 - PERFORMANCE TESTS")
    print("="*70)
    print()
    print("Testing FilmBuddy response times and throughput...")
    print("Target: Query latency < 3 seconds average")
    print()
    
    results = []
    
    # Test 1: Query latency
    try:
        latencies = measure_query_latency(num_requests=10)
        if latencies:
            avg_latency = statistics.mean(latencies)
            results.append(("Query latency", avg_latency < 3.0))
        else:
            results.append(("Query latency", False))
    except Exception as e:
        print(f"  ❌ Latency test error: {e}")
        results.append(("Query latency", False))
    
    # Test 2: Concurrent requests
    try:
        concurrent_success = test_concurrent_requests()
        results.append(("Concurrent requests", concurrent_success))
    except Exception as e:
        print(f"  ❌ Concurrent test error: {e}")
        results.append(("Concurrent requests", False))
    
    # Bonus: Embedding performance
    try:
        test_embedding_performance()
    except Exception as e:
        print(f"  ⚠️  Embedding test error: {e}")
    
    # Summary
    print("\n" + "="*70)
    print("PERFORMANCE SUMMARY")
    print("="*70)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    print(f"\nTotal: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        print("\n🎉 ALL PERFORMANCE TESTS PASSED!")
    else:
        print(f"\n⚠️  {total_count - passed_count} test(s) need optimization")
    
    print("="*70)
    
    return passed_count == total_count


if __name__ == "__main__":
    import sys
    
    print("Waiting for server to be ready...")
    time.sleep(2)
    
    # Check if server is running
    try:
        requests.get(f"{BASE_URL}/ping", timeout=2)
    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Server not running!")
        print("Please start the server first:")
        print("  uvicorn server.main:app --reload")
        sys.exit(1)
    
    success = run_performance_tests()
    sys.exit(0 if success else 1)

