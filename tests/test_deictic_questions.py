#!/usr/bin/env python3
"""
Vague/Deictic Question Tests for FilmBuddy (Step 9)

Tests the system's ability to answer vague questions like "Who's that guy?"
using enriched scene context and character metadata.
"""

import requests
import time
from typing import List, Tuple


BASE_URL = "http://localhost:8000"


# Test cases: (query, timestamp, expected_keywords, description)
VAGUE_QUESTIONS = [
    (
        "Who is the main character?",
        845.0,
        ["mia", "emma stone"],
        "Identify main character by name/actor"
    ),
    (
        "Who is the guy playing piano?",
        2400.0,
        ["sebastian", "ryan gosling"],
        "Identify character by activity"
    ),
    (
        "What is this girl's name?",
        400.0,
        ["mia"],
        "Identify character from vague reference"
    ),
    (
        "Who are they?",
        650.0,
        ["mia", "sebastian", "characters"],
        "Identify multiple characters"
    ),
    (
        "What is this song about?",
        100.0,
        ["dream", "la", "california", "another day"],
        "Explain song meaning"
    ),
    (
        "Where are they?",
        750.0,
        ["party", "pool", "house", "hollywood"],
        "Identify location"
    ),
    (
        "What just happened?",
        1200.0,
        ["audition", "casting", "meeting"],
        "Summarize recent events"
    ),
    (
        "Why is she upset?",
        3600.0,
        ["audition", "job", "relationship", "disappointed"],
        "Explain character emotion"
    ),
]


def query_api(question: str, timestamp: float, film_id: str = "la_la_land") -> dict:
    """Query the /ask endpoint."""
    payload = {
        "film_id": film_id,
        "t_now": timestamp,
        "query": question,
        "spoiler_mode": "off"
    }
    
    response = requests.post(f"{BASE_URL}/ask", json=payload)
    assert response.status_code == 200, f"API error: {response.status_code}"
    
    return response.json()


def check_answer_quality(answer: str, expected_keywords: List[str]) -> Tuple[bool, List[str]]:
    """
    Check if answer contains expected keywords.
    
    Returns:
        (has_any_keyword, matched_keywords)
    """
    answer_lower = answer.lower()
    matched = [kw for kw in expected_keywords if kw.lower() in answer_lower]
    return len(matched) > 0, matched


def test_vague_question(
    query: str, 
    timestamp: float, 
    expected_keywords: List[str],
    description: str
) -> bool:
    """Test a single vague question."""
    print(f"\n  Query: \"{query}\" at {timestamp:.0f}s")
    print(f"  Goal: {description}")
    
    try:
        start_time = time.time()
        result = query_api(query, timestamp)
        elapsed = time.time() - start_time
        
        answer = result.get("answer", "")
        
        if not answer:
            print(f"    ❌ No answer generated")
            return False
        
        # Check if answer contains expected keywords
        has_keywords, matched = check_answer_quality(answer, expected_keywords)
        
        print(f"    ⏱  Response time: {elapsed:.2f}s")
        print(f"    📝 Answer: {answer[:150]}...")
        
        if has_keywords:
            print(f"    ✅ Contains expected info: {', '.join(matched)}")
            return True
        else:
            print(f"    ⚠️  Missing expected keywords: {', '.join(expected_keywords)}")
            print(f"    Full answer: {answer}")
            return False
            
    except Exception as e:
        print(f"    ❌ Error: {e}")
        return False


def test_contextual_awareness():
    """Test that system uses current scene context."""
    print("\n[Contextual Awareness Test]")
    print("Testing if system uses current timestamp for context...")
    
    # Same question at different times should give different answers
    question = "Who is on screen?"
    
    early_result = query_api(question, 100.0)
    later_result = query_api(question, 2000.0)
    
    early_answer = early_result.get("answer", "")
    later_answer = later_result.get("answer", "")
    
    # Answers should be different (different scenes/characters)
    similarity = len(set(early_answer.split()) & set(later_answer.split())) / max(len(early_answer.split()), 1)
    
    is_different = similarity < 0.7  # Less than 70% word overlap
    
    print(f"  ✓ Early answer (100s): {early_answer[:100]}...")
    print(f"  ✓ Later answer (2000s): {later_answer[:100]}...")
    print(f"  ✓ Contextually different: {is_different}")
    
    return is_different


def test_character_identification():
    """Test character identification from enriched data."""
    print("\n[Character Identification Test]")
    print("Testing character identification with full names and actors...")
    
    result = query_api("Who is Mia?", 845.0)
    answer = result.get("answer", "")
    
    # Should mention Emma Stone (actor)
    has_actor = "emma stone" in answer.lower()
    
    # Should mention protagonist/main character/actress
    has_role = any(term in answer.lower() for term in ["protagonist", "main", "actress", "aspiring"])
    
    print(f"  ✓ Mentions actor: {has_actor}")
    print(f"  ✓ Mentions role/description: {has_role}")
    print(f"  ✓ Answer: {answer[:200]}...")
    
    return has_actor or has_role


def run_deictic_tests():
    """Run all vague/deictic question tests."""
    print("="*70)
    print("STEP 9 - VAGUE/DEICTIC QUESTION TESTS")
    print("="*70)
    print()
    print("Testing FilmBuddy's ability to answer vague questions...")
    print("Goal: 80%+ accuracy on vague references (\"who's that guy?\", etc.)")
    print()
    
    results = []
    
    print(f"[Testing {len(VAGUE_QUESTIONS)} vague questions]")
    
    for i, (query, timestamp, keywords, description) in enumerate(VAGUE_QUESTIONS, 1):
        print(f"\n[Test {i}/{len(VAGUE_QUESTIONS)}]")
        success = test_vague_question(query, timestamp, keywords, description)
        results.append((query, success))
    
    # Additional contextual tests
    print("\n" + "="*70)
    print("ADDITIONAL TESTS")
    print("="*70)
    
    try:
        contextual_success = test_contextual_awareness()
        results.append(("Contextual awareness", contextual_success))
    except Exception as e:
        print(f"⚠️  Contextual test error: {e}")
        contextual_success = False
    
    try:
        char_id_success = test_character_identification()
        results.append(("Character identification", char_id_success))
    except Exception as e:
        print(f"⚠️  Character ID test error: {e}")
        char_id_success = False
    
    # Summary
    print("\n" + "="*70)
    print("TEST RESULTS")
    print("="*70)
    
    for query, passed in results:
        status = "✅" if passed else "❌"
        print(f"{status} {query[:50]}")
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    accuracy = (passed_count / total_count) * 100
    
    print(f"\nAccuracy: {passed_count}/{total_count} ({accuracy:.1f}%)")
    print(f"Target: 80%+ accuracy")
    
    if accuracy >= 80:
        print("\n🎉 EXCELLENT! Exceeded target accuracy!")
    elif accuracy >= 60:
        print("\n✅ GOOD! Reasonable accuracy achieved.")
    else:
        print("\n⚠️  Below target. System needs improvement.")
    
    print("="*70)
    
    return accuracy >= 60  # Pass if 60%+ accuracy


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
    
    success = run_deictic_tests()
    sys.exit(0 if success else 1)

