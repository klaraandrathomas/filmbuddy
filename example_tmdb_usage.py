#!/usr/bin/env python3
"""
Example usage of TMDBClient.

This demonstrates how to use the TMDB client to fetch movie metadata.
"""

import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv()

from preprocessing.tmdb_client import TMDBClient


async def example_usage():
    """Demonstrate TMDBClient usage."""
    
    # Initialize client (reads TMDB_API_KEY from environment)
    client = TMDBClient()
    
    print("=" * 70)
    print("TMDB Client Example Usage")
    print("=" * 70)
    
    # Example 1: Get complete metadata for a movie
    print("\n[Example 1] Get metadata for 'La La Land'")
    print("-" * 70)
    
    metadata = await client.get_movie_metadata("La La Land", 2016)
    
    print(f"Title: {metadata['title']}")
    print(f"Movie ID: {metadata['movie_id']}")
    print(f"Release Year: {metadata['release_year']}")
    print(f"Runtime: {metadata['runtime_seconds']} seconds ({metadata['runtime_seconds']//60} min)")
    print(f"Genres: {', '.join(metadata['genres'])}")
    print(f"\nOverview: {metadata['overview'][:150]}...")
    
    print(f"\nMain Cast ({len(metadata['characters'])} total):")
    for i, char in enumerate(metadata['characters'][:5], 1):
        gender_icon = "♀" if char["gender"] == "female" else "♂" if char["gender"] == "male" else "?"
        print(f"  {i}. {gender_icon} {char['actor_name']:20s} as {char['character_name']}")
    
    # Example 2: Search for a movie
    print("\n" + "=" * 70)
    print("[Example 2] Search for '10 Things I Hate About You'")
    print("-" * 70)
    
    search_result = await client.search_movie("10 Things I Hate About You", 1999)
    
    if search_result:
        print(f"Found: {search_result['title']}")
        print(f"Release Date: {search_result['release_date']}")
        print(f"TMDB ID: {search_result['id']}")
        
        # Get cast for this movie
        cast = await client.get_cast(search_result['id'], limit=3)
        print(f"\nTop 3 Cast:")
        for person in cast:
            print(f"  - {person['actor_name']} as {person['character_name']}")
    
    # Example 3: Handling missing movies
    print("\n" + "=" * 70)
    print("[Example 3] Handling non-existent movies")
    print("-" * 70)
    
    result = await client.search_movie("This Movie Does Not Exist XYZ123", 1900)
    if result is None:
        print("✓ Correctly returns None for non-existent movie")
    
    print("\n" + "=" * 70)
    print("Examples complete!")
    print("=" * 70)


if __name__ == "__main__":
    # Check if API key is set
    if not os.environ.get("TMDB_API_KEY"):
        print("ERROR: TMDB_API_KEY environment variable not set")
        print("\nPlease set your TMDB API key:")
        print("  export TMDB_API_KEY='your_key_here'")
        print("\nOr add it to your .env file:")
        print("  echo 'TMDB_API_KEY=your_key_here' >> .env")
        print("\nGet your API key from: https://www.themoviedb.org/settings/api")
        sys.exit(1)
    
    asyncio.run(example_usage())

