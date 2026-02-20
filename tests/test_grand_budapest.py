#!/usr/bin/env python3
"""Test TMDB client with The Grand Budapest Hotel."""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from preprocessing.tmdb_client import TMDBClient


async def test_grand_budapest():
    """Test with a movie not in our existing corpus."""
    print("=" * 70)
    print("Testing TMDB Client with 'The Grand Budapest Hotel'")
    print("=" * 70)
    
    client = TMDBClient()
    
    # Get full metadata
    print("\n[Fetching metadata...]")
    metadata = await client.get_movie_metadata("The Grand Budapest Hotel", 2014)
    
    print(f"\n✓ Successfully retrieved metadata!\n")
    print(f"Title:         {metadata['title']}")
    print(f"Movie ID:      {metadata['movie_id']}")
    print(f"Release Year:  {metadata['release_year']}")
    print(f"Runtime:       {metadata['runtime_seconds']} seconds ({metadata['runtime_seconds']//60} min)")
    print(f"Genres:        {', '.join(metadata['genres'])}")
    print(f"\nOverview:")
    print(f"  {metadata['overview'][:200]}...")
    
    print(f"\n{'='*70}")
    print(f"Main Cast ({len(metadata['characters'])} characters found):")
    print(f"{'='*70}")
    
    for i, char in enumerate(metadata['characters'][:10], 1):
        gender_icon = "♀" if char["gender"] == "female" else "♂" if char["gender"] == "male" else "?"
        print(f"  {i:2d}. {gender_icon} {char['actor_name']:25s} as {char['character_name']}")
    
    if len(metadata['characters']) > 10:
        print(f"\n  ... and {len(metadata['characters']) - 10} more characters")
    
    print(f"\n{'='*70}")
    print("✅ Test successful! TMDB client works with movies outside corpus.")
    print(f"{'='*70}")


if __name__ == "__main__":
    asyncio.run(test_grand_budapest())

