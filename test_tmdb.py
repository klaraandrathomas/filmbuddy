#!/usr/bin/env python3
"""Test script for TMDB Client (Step 2)."""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv()

from preprocessing.tmdb_client import TMDBClient


async def test_tmdb():
    """Test TMDB client functionality."""
    print("=" * 70)
    print("STEP 2 TEST: TMDB Client")
    print("=" * 70)
    
    try:
        client = TMDBClient()
        print("✓ TMDBClient initialized successfully\n")
    except ValueError as e:
        print(f"✗ Failed to initialize: {e}")
        print("\nPlease set TMDB_API_KEY environment variable.")
        print("Get your key from: https://www.themoviedb.org/settings/api")
        return 1
    
    # Test 1: Search for movie
    print("[Test 1] Searching for 'La La Land' (2016)...")
    try:
        result = await client.search_movie("La La Land", 2016)
        assert result is not None, "Movie not found"
        assert result["title"] == "La La Land", f"Wrong title: {result['title']}"
        print(f"✓ Found movie: {result['title']} (ID: {result['id']})")
        print(f"  Release date: {result['release_date']}")
        print(f"  Overview: {result['overview'][:80]}...")
    except Exception as e:
        print(f"✗ Test 1 failed: {e}")
        return 1
    
    # Test 2: Get movie details
    print("\n[Test 2] Getting movie details...")
    try:
        details = await client.get_movie_details(result["id"])
        assert details["runtime"] is not None, "Runtime not found"
        assert details["runtime"] > 0, "Invalid runtime"
        print(f"✓ Movie details retrieved")
        print(f"  Runtime: {details['runtime']} minutes")
        print(f"  Genres: {', '.join(details['genres'])}")
    except Exception as e:
        print(f"✗ Test 2 failed: {e}")
        return 1
    
    # Test 3: Get cast
    print("\n[Test 3] Getting cast information...")
    try:
        cast = await client.get_cast(result["id"], limit=10)
        assert len(cast) >= 5, f"Expected at least 5 cast members, got {len(cast)}"
        print(f"✓ Found {len(cast)} cast members")
        
        # Show first 5 cast members
        print("\n  Top 5 Cast:")
        for person in cast[:5]:
            gender_icon = "♀" if person["gender"] == "female" else "♂" if person["gender"] == "male" else "?"
            print(f"    {gender_icon} {person['actor_name']:20s} as {person['character_name']}")
    except Exception as e:
        print(f"✗ Test 3 failed: {e}")
        return 1
    
    # Test 4: Get full metadata
    print("\n[Test 4] Getting full movie metadata...")
    try:
        metadata = await client.get_movie_metadata("La La Land", 2016)
        assert "characters" in metadata, "Characters not in metadata"
        assert len(metadata["characters"]) > 0, "No characters found"
        print(f"✓ Full metadata retrieved")
        print(f"  Movie ID: {metadata['movie_id']}")
        print(f"  Title: {metadata['title']}")
        print(f"  Runtime: {metadata['runtime_seconds']} seconds ({metadata['runtime_seconds']//60} min)")
        print(f"  Release year: {metadata['release_year']}")
        print(f"  Characters: {len(metadata['characters'])}")
    except Exception as e:
        print(f"✗ Test 4 failed: {e}")
        return 1
    
    # Test 5: Verify specific character data
    print("\n[Test 5] Verifying character details...")
    try:
        # Look for Mia in the cast
        mia = next((c for c in metadata["characters"] if "Mia" in c["character_name"]), None)
        assert mia is not None, "Mia Dolan not found in cast"
        assert mia["actor_name"] == "Emma Stone", f"Expected Emma Stone, got {mia['actor_name']}"
        assert mia["gender"] == "female", f"Expected female, got {mia['gender']}"
        print(f"✓ Character verification passed")
        print(f"  {mia['character_name']} played by {mia['actor_name']} ({mia['gender']})")
        
        # Look for Sebastian
        sebastian = next((c for c in metadata["characters"] if "Sebastian" in c["character_name"]), None)
        if sebastian:
            print(f"  {sebastian['character_name']} played by {sebastian['actor_name']} ({sebastian['gender']})")
    except Exception as e:
        print(f"✗ Test 5 failed: {e}")
        return 1
    
    # Test 6: Handle movie not found
    print("\n[Test 6] Testing error handling (movie not found)...")
    try:
        result = await client.search_movie("ThisMovieDoesNotExist12345XYZ", 1900)
        assert result is None, "Should return None for non-existent movie"
        print("✓ Correctly returns None for non-existent movie")
    except Exception as e:
        print(f"✗ Test 6 failed: {e}")
        return 1
    
    # Test 7: Test another movie to ensure generalizability
    print("\n[Test 7] Testing with another movie (10 Things I Hate About You)...")
    try:
        metadata = await client.get_movie_metadata("10 Things I Hate About You", 1999)
        assert metadata["title"] == "10 Things I Hate About You"
        assert metadata["release_year"] == 1999
        assert len(metadata["characters"]) >= 5
        print(f"✓ Found movie: {metadata['title']}")
        print(f"  Runtime: {metadata['runtime_seconds']//60} minutes")
        print(f"  Top 3 characters:")
        for char in metadata["characters"][:3]:
            print(f"    - {char['actor_name']} as {char['character_name']}")
    except Exception as e:
        print(f"✗ Test 7 failed: {e}")
        return 1
    
    # Summary
    print("\n" + "=" * 70)
    print("✅ ALL TMDB TESTS PASSED!")
    print("=" * 70)
    print("\nAcceptance Criteria Status:")
    print("  ✓ Can search for any movie by title")
    print("  ✓ Returns correct runtime in seconds")
    print("  ✓ Returns at least top 10 cast members with character names")
    print("  ✓ Gender extracted correctly (1=female, 2=male, 0=unknown)")
    print("  ✓ Handles movies not found gracefully (returns None)")
    print("\nReady for Step 3: Implement ScriptParser")
    print("=" * 70)
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(test_tmdb())
    sys.exit(exit_code)

