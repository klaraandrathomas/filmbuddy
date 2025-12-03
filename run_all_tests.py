#!/usr/bin/env python3
"""
Master Test Runner for FilmBuddy (Step 9)

Runs all test suites and generates comprehensive report.
"""

import sys
import time
import subprocess
import requests


BASE_URL = "http://localhost:8000"


def check_server():
    """Check if server is running."""
    try:
        response = requests.get(f"{BASE_URL}/ping", timeout=2)
        return response.status_code == 200
    except:
        return False


def run_test_suite(name: str, script: str) -> bool:
    """Run a test suite and return success status."""
    print(f"\n{'='*70}")
    print(f"Running: {name}")
    print(f"{'='*70}\n")
    
    try:
        result = subprocess.run(
            [sys.executable, script],
            capture_output=False,
            text=True
        )
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Error running {name}: {e}")
        return False


def main():
    """Run all test suites."""
    print("="*70)
    print("FILMBUDDY - STEP 9 COMPREHENSIVE TEST SUITE")
    print("="*70)
    print()
    print("Testing FilmBuddy with Azure OpenAI Integration")
    print()
    
    # Check dependencies
    print("[Pre-flight Checks]")
    
    # Check if server is running
    if check_server():
        print("  ✓ Server is running")
    else:
        print("  ❌ Server is NOT running")
        print()
        print("Please start the server first:")
        print("  uvicorn server.main:app --reload")
        print()
        return 1
    
    # Run test suites
    test_suites = [
        ("Unit Tests", "test_unit.py"),
        ("API Integration Tests", "test_api_integration.py"),
        ("Vague/Deictic Question Tests", "test_deictic_questions.py"),
        ("Performance Tests", "test_performance.py"),
    ]
    
    results = []
    
    for name, script in test_suites:
        success = run_test_suite(name, script)
        results.append((name, success))
        time.sleep(2)  # Brief pause between suites
    
    # Final summary
    print("\n" + "="*70)
    print("FINAL TEST SUMMARY - STEP 9 COMPLETE")
    print("="*70)
    print()
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    print()
    print(f"Total: {passed_count}/{total_count} test suites passed")
    print()
    
    if passed_count == total_count:
        print("🎉 ALL TESTS PASSED!")
        print()
        print("Step 9 - Testing & Validation: COMPLETE ✅")
        print()
        print("FilmBuddy is fully functional with Azure OpenAI integration!")
        print()
        print("Key achievements:")
        print("  ✓ All components tested and working")
        print("  ✓ API endpoints functional")
        print("  ✓ Vague question handling validated")
        print("  ✓ Performance meets targets")
        print("  ✓ Azure OpenAI integration successful")
    else:
        print(f"⚠️  {total_count - passed_count} test suite(s) need attention")
        print()
        print("Please review failed tests and address issues.")
    
    print()
    print("="*70)
    
    return 0 if passed_count == total_count else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

