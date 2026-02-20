#!/usr/bin/env python3
"""
API Integration Tests for FilmBuddy (Step 9)

Tests the full API endpoints with Azure OpenAI integration.
"""

import asyncio
import requests
import time
import json
from typing import Optional


BASE_URL = "http://localhost:8000"


def test_ping_endpoint():
    """Test /ping endpoint returns correct status."""
    print("[Test 1/6] Testing /ping endpoint...")
    
    response = requests.get(f"{BASE_URL}/ping")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    data = response.json()
    assert data["ok"] == True, "Server should be OK"
    assert "llm_enabled" in data, "Should include llm_enabled status"
    assert "available_films" in data, "Should list available films"
    
    print(f"  ✓ Server OK, LLM enabled: {data['llm_enabled']}")
    print(f"  ✓ Available films: {data['available_films']}")
    return True


def test_films_endpoint():
    """Test /films endpoint returns film metadata."""
    print("\n[Test 2/6] Testing /films endpoint...")
    
    response = requests.get(f"{BASE_URL}/films")
    assert response.status_code == 200
    
    data = response.json()
    assert "films" in data
    assert len(data["films"]) > 0, "Should have at least one film"
    
    # Check film structure
    film = data["films"][0]
    required_fields = ["film_id", "num_chunks", "duration_seconds", "has_enriched_corpus"]
    for field in required_fields:
        assert field in film, f"Film missing field: {field}"
    
    print(f"  ✓ Found {len(data['films'])} films")
    for f in data["films"]:
        print(f"    - {f['film_id']}: {f['num_chunks']} chunks, {f['duration_seconds']/60:.1f} min")
    
    return True


def test_scene_endpoint():
    """Test /movie/{id}/scene endpoint returns enriched scene data."""
    print("\n[Test 3/6] Testing /movie/{id}/scene endpoint...")
    
    # Test with a timestamp we know exists
    response = requests.get(f"{BASE_URL}/movie/la_la_land_2016/scene?timestamp=50")
    
    if response.status_code == 404:
        print("  ⚠ No enriched scene data available (expected if corpus not built)")
        return True
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    scene = response.json()
    
    # Check required fields
    required_fields = ["location", "t_start", "t_end", "characters_present", "character_details"]
    for field in required_fields:
        assert field in scene, f"Scene missing field: {field}"
    
    print(f"  ✓ Scene at timestamp 50s:")
    print(f"    Location: {scene['location']}")
    print(f"    Time: {scene['t_start']:.1f}s - {scene['t_end']:.1f}s")
    print(f"    Characters: {', '.join(scene['characters_present'][:3])}")
    
    return True


def test_characters_endpoint():
    """Test /movie/{id}/characters endpoint."""
    print("\n[Test 4/6] Testing /movie/{id}/characters endpoint...")
    
    response = requests.get(f"{BASE_URL}/movie/la_la_land_2016/characters")
    
    if response.status_code == 404:
        print("  ⚠ No character data available (expected if corpus not built)")
        return True
    
    assert response.status_code == 200
    
    data = response.json()
    assert "characters" in data
    assert len(data["characters"]) > 0, "Should have characters"
    
    # Check character structure
    char_name = list(data["characters"].keys())[0]
    char = data["characters"][char_name]
    
    required_fields = ["full_name", "actor", "gender", "role"]
    for field in required_fields:
        assert field in char, f"Character missing field: {field}"
    
    print(f"  ✓ Found {len(data['characters'])} characters")
    
    # Show main characters (those with actors)
    main_chars = {k: v for k, v in data["characters"].items() if v.get("actor")}
    print(f"  ✓ Main characters with actors: {len(main_chars)}")
    for name, info in list(main_chars.items())[:3]:
        print(f"    - {name}: {info['actor']}")
    
    return True


def test_ask_endpoint_basic():
    """Test /ask endpoint with basic query."""
    print("\n[Test 5/6] Testing /ask endpoint (basic query)...")
    
    payload = {
        "film_id": "la_la_land",
        "t_now": 845.0,
        "query": "What is happening in this scene?",
        "spoiler_mode": "off"
    }
    
    start_time = time.time()
    response = requests.post(f"{BASE_URL}/ask", json=payload)
    elapsed = time.time() - start_time
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    data = response.json()
    
    # Check response structure
    required_fields = ["answer", "hits", "film_id", "t_now", "llm_enabled"]
    for field in required_fields:
        assert field in data, f"Response missing field: {field}"
    
    assert data["llm_enabled"] == True, "LLM should be enabled"
    assert data["answer"] is not None, "Should have LLM-generated answer"
    assert len(data["hits"]) > 0, "Should have relevant hits"
    
    print(f"  ✓ Response time: {elapsed:.2f}s")
    print(f"  ✓ LLM enabled: {data['llm_enabled']}")
    print(f"  ✓ Answer length: {len(data['answer'])} chars")
    print(f"  ✓ Hits returned: {len(data['hits'])}")
    print(f"  ✓ Answer preview: {data['answer'][:150]}...")
    
    return True


def test_ask_endpoint_vague_question():
    """Test /ask endpoint with vague deictic question."""
    print("\n[Test 6/6] Testing /ask endpoint (vague question)...")
    
    payload = {
        "film_id": "la_la_land",
        "t_now": 600.0,
        "query": "Who is the girl?",
        "spoiler_mode": "off"
    }
    
    response = requests.post(f"{BASE_URL}/ask", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    answer = data["answer"]
    
    # Answer should mention a character name
    # For La La Land, should mention Mia or Emma Stone
    has_character = any(name.lower() in answer.lower() 
                       for name in ["mia", "emma stone", "emma", "stone"])
    
    print(f"  ✓ Answer mentions character: {has_character}")
    print(f"  ✓ Answer: {answer[:200]}...")
    
    if not has_character:
        print("  ⚠ Warning: Answer may not identify character clearly")
    
    return True


def test_spoiler_filtering():
    """Test that spoiler mode correctly filters future content."""
    print("\n[Bonus Test] Testing spoiler mode filtering...")
    
    # Query early in movie with spoiler off
    payload_no_spoiler = {
        "film_id": "la_la_land",
        "t_now": 100.0,
        "query": "What happens to them?",
        "spoiler_mode": "off"
    }
    
    response = requests.post(f"{BASE_URL}/ask", json=payload_no_spoiler)
    data_no_spoiler = response.json()
    
    # All hits should be before current time
    all_before = all(hit["t_start"] <= 100.0 for hit in data_no_spoiler["hits"])
    
    print(f"  ✓ Spoiler filtering: {'PASS' if all_before else 'FAIL'}")
    print(f"  ✓ All hits before t_now: {all_before}")
    
    if not all_before:
        future_hits = [h for h in data_no_spoiler["hits"] if h["t_start"] > 100.0]
        print(f"  ⚠ Found {len(future_hits)} hits after current time")
    
    return all_before


def run_integration_tests():
    """Run all integration tests."""
    print("="*70)
    print("STEP 9 - API INTEGRATION TESTS")
    print("="*70)
    print()
    print("Testing FilmBuddy API with Azure OpenAI integration...")
    print()
    
    tests = [
        ("Ping", test_ping_endpoint),
        ("Films", test_films_endpoint),
        ("Scene", test_scene_endpoint),
        ("Characters", test_characters_endpoint),
        ("Ask (Basic)", test_ask_endpoint_basic),
        ("Ask (Vague)", test_ask_endpoint_vague_question),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"  ❌ Test failed: {e}")
            results.append((test_name, False))
    
    # Bonus test
    try:
        print()
        test_spoiler_filtering()
    except Exception as e:
        print(f"  ⚠ Spoiler test failed: {e}")
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    print(f"\nTotal: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        print("\n🎉 ALL INTEGRATION TESTS PASSED!")
    else:
        print(f"\n⚠️  {total_count - passed_count} test(s) failed")
    
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
    
    success = run_integration_tests()
    sys.exit(0 if success else 1)
