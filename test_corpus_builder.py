"""
Test script for MovieCorpusBuilder (Step 6)

Tests the full pipeline orchestration:
1. TMDB metadata fetching
2. Script parsing
3. Character extraction
4. Character merging
5. Timestamp alignment
6. Scene summary generation
7. Enriched chunk building
8. JSONL output
"""

import asyncio
import json
import os
from pathlib import Path
from preprocessing.corpus_builder import MovieCorpusBuilder

# Try to load .env file if available
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✓ Loaded environment variables from .env")
except ImportError:
    print("⚠️  python-dotenv not installed, using system environment variables")
except Exception:
    pass


async def test_full_pipeline():
    """Test the complete corpus building pipeline."""
    print("\n" + "="*60)
    print("Testing MovieCorpusBuilder - Full Pipeline")
    print("="*60 + "\n")
    
    # Check for API keys first
    if not os.getenv("TMDB_API_KEY"):
        print("⚠️  TMDB_API_KEY not set in environment")
        print("   Skipping full pipeline test.")
        print("   To run this test, create a .env file with:")
        print("   TMDB_API_KEY=your_key_here")
        print("   AZURE_OPENAI_API_KEY=your_key_here")
        print("   AZURE_OPENAI_ENDPOINT=your_endpoint_url")
        return False
    
    if not os.getenv("AZURE_OPENAI_API_KEY"):
        print("⚠️  AZURE_OPENAI_API_KEY not set in environment")
        print("   Skipping full pipeline test.")
        return False
    
    try:
        builder = MovieCorpusBuilder()
    except ValueError as e:
        print(f"⚠️  Failed to initialize builder: {e}")
        print("   Skipping full pipeline test.")
        return False
    
    # Note: This test requires actual script file
    # For now, we'll test with La La Land if the script exists
    
    script_path = "scripts/lalaland_script.txt"
    subtitle_path = "data/lalaland.srt"
    
    # Check if files exist
    if not Path(script_path).exists():
        print(f"⚠️  Script file not found: {script_path}")
        print("   Skipping full pipeline test.")
        print("   To run this test, place a La La Land script at:")
        print(f"   {script_path}")
        return False
    
    if not Path(subtitle_path).exists():
        print(f"⚠️  Subtitle file not found: {subtitle_path}")
        return False
    
    # Run the full pipeline
    try:
        corpus = await builder.build_corpus(
            movie_title="La La Land",
            script_path=script_path,
            subtitle_path=subtitle_path,
            release_year=2016,
            output_dir="corpus"
        )
        
        # Validate output
        print("\n" + "="*60)
        print("Validating Output")
        print("="*60 + "\n")
        
        # Check movie_id
        assert corpus["movie_id"] == "la_la_land_2016", f"Unexpected movie_id: {corpus['movie_id']}"
        print("✓ Movie ID correct: la_la_land_2016")
        
        # Check scenes
        num_scenes = len(corpus["scenes"])
        assert num_scenes > 10, f"Too few scenes: {num_scenes}"
        print(f"✓ Built {num_scenes} scenes")
        
        # Check characters
        assert len(corpus["characters"]) > 0, "No characters found"
        print(f"✓ Found {len(corpus['characters'])} characters")
        
        # Check if main characters are present
        character_names = list(corpus["characters"].keys())
        print(f"  Characters: {', '.join(character_names[:5])}{'...' if len(character_names) > 5 else ''}")
        
        # Check if TMDB data was merged (check for actors)
        characters_with_actors = sum(1 for c in corpus["characters"].values() if c.get('actor'))
        print(f"✓ {characters_with_actors} characters have actor information from TMDB")
        
        # Validate a sample scene
        sample_scene = corpus["scenes"][0]
        
        required_fields = [
            'chunk_id', 'movie_id', 'source_type', 't_start', 't_end',
            'scene_id', 'location', 'summary', 'characters_present',
            'character_details', 'alignment_confidence', 'alignment_method'
        ]
        
        for field in required_fields:
            assert field in sample_scene, f"Missing field in scene: {field}"
        
        print("✓ All required fields present in scenes")
        
        # Display sample scene
        print(f"\n{'='*60}")
        print("Sample Scene (Scene 1)")
        print(f"{'='*60}")
        print(f"Location: {sample_scene['location']}")
        print(f"Time: {sample_scene['t_start']:.1f}s - {sample_scene['t_end']:.1f}s")
        print(f"Characters: {', '.join(sample_scene['characters_present'])}")
        print(f"Summary: {sample_scene['summary'][:100]}...")
        print(f"Alignment: {sample_scene['alignment_method']} (confidence: {sample_scene['alignment_confidence']:.2f})")
        
        # Check alignment statistics
        stats = corpus['stats']
        print(f"\n{'='*60}")
        print("Pipeline Statistics")
        print(f"{'='*60}")
        print(f"Total Time: {stats['total_time']:.1f}s")
        print(f"  - TMDB: {stats['tmdb_time']:.2f}s")
        print(f"  - Parsing: {stats['parse_time']:.2f}s")
        print(f"  - Character Extraction: {stats['character_extraction_time']:.1f}s")
        print(f"  - Alignment: {stats['alignment_time']:.2f}s")
        print(f"  - Summaries: {stats['summary_time']:.1f}s")
        print(f"\nScenes: {stats['total_scenes']}")
        print(f"Characters: {stats['total_characters']}")
        print(f"Alignment Rate: {stats['aligned_scenes']}/{stats['total_scenes']} ({stats['aligned_scenes']/stats['total_scenes']*100:.1f}%)")
        
        # Verify JSONL file was created
        output_file = Path("corpus") / f"{corpus['movie_id']}_enriched.jsonl"
        assert output_file.exists(), f"Output file not created: {output_file}"
        print(f"\n✓ Output file created: {output_file}")
        
        # Verify metadata file was created
        metadata_file = Path("corpus") / f"{corpus['movie_id']}_metadata.json"
        assert metadata_file.exists(), f"Metadata file not created: {metadata_file}"
        print(f"✓ Metadata file created: {metadata_file}")
        
        # Validate JSONL structure
        with open(output_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            assert len(lines) == num_scenes, f"JSONL line count mismatch: {len(lines)} vs {num_scenes}"
            
            # Parse first line to ensure it's valid JSON
            first_chunk = json.loads(lines[0])
            assert 'chunk_id' in first_chunk
            assert 'characters_present' in first_chunk
            assert 'character_details' in first_chunk
        
        print(f"✓ JSONL file valid with {len(lines)} scenes")
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED!")
        print("="*60 + "\n")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_character_merging():
    """Test character data merging logic."""
    print("\n" + "="*60)
    print("Testing Character Merging")
    print("="*60 + "\n")
    
    # For this test, we only need the _merge_character_data method
    # We can create a builder instance without initializing API clients
    try:
        builder = MovieCorpusBuilder()
    except ValueError as e:
        # If API keys are missing, create a minimal builder for testing merge logic only
        print(f"⚠️  API keys not configured: {e}")
        print("   Testing merge logic with mock builder...")
        builder = object.__new__(MovieCorpusBuilder)  # Create without __init__
    
    # Mock script characters
    script_characters = {
        "MIA": {
            "full_name": "Mia Dolan",
            "gender": "female",
            "role": "protagonist",
            "description": "Aspiring actress working as a barista",
            "occupation": "Barista / Actress",
            "relationships": {"SEBASTIAN": "love interest"}
        },
        "SEBASTIAN": {
            "full_name": "Sebastian Wilder",
            "gender": "male",
            "role": "protagonist",
            "description": "Jazz pianist",
            "occupation": "Musician",
            "relationships": {"MIA": "love interest"}
        },
        "BILL": {
            "full_name": "Bill",
            "gender": "male",
            "role": "minor",
            "description": "Friend",
            "occupation": "Unknown",
            "relationships": {}
        }
    }
    
    # Mock TMDB cast
    tmdb_cast = [
        {
            "character_name": "Mia Dolan",
            "actor_name": "Emma Stone",
            "gender": "female",
            "order": 0,
            "profile_path": "https://image.tmdb.org/emma_stone.jpg"
        },
        {
            "character_name": "Sebastian",
            "actor_name": "Ryan Gosling",
            "gender": "male",
            "order": 1,
            "profile_path": "https://image.tmdb.org/ryan_gosling.jpg"
        }
    ]
    
    # Test merging
    merged = builder._merge_character_data(script_characters, tmdb_cast)
    
    # Validate MIA
    assert "MIA" in merged, "MIA not found in merged data"
    mia = merged["MIA"]
    assert mia["full_name"] == "Mia Dolan", f"Wrong full name: {mia['full_name']}"
    assert mia["actor"] == "Emma Stone", f"Wrong actor: {mia['actor']}"
    assert mia["gender"] == "female", f"Wrong gender: {mia['gender']}"
    assert mia["role"] == "protagonist", f"Wrong role: {mia['role']}"
    print("✓ MIA merged correctly:")
    print(f"  Full name: {mia['full_name']}")
    print(f"  Actor: {mia['actor']}")
    print(f"  Role: {mia['role']}")
    
    # Validate SEBASTIAN (fuzzy match - "Sebastian" vs "SEBASTIAN")
    assert "SEBASTIAN" in merged, "SEBASTIAN not found in merged data"
    seb = merged["SEBASTIAN"]
    assert seb["actor"] == "Ryan Gosling", f"Wrong actor: {seb['actor']}"
    print("\n✓ SEBASTIAN merged correctly (fuzzy matched):")
    print(f"  Full name: {seb['full_name']}")
    print(f"  Actor: {seb['actor']}")
    
    # Validate BILL (script only, no TMDB match)
    assert "BILL" in merged, "BILL not found in merged data"
    bill = merged["BILL"]
    assert bill["actor"] is None, "BILL shouldn't have actor"
    print("\n✓ BILL kept from script (no TMDB match):")
    print(f"  Full name: {bill['full_name']}")
    print(f"  Actor: {bill['actor']} (expected None)")
    
    print("\n✅ Character merging tests passed!\n")
    return True


async def test_enriched_chunk_building():
    """Test enriched chunk building."""
    print("\n" + "="*60)
    print("Testing Enriched Chunk Building")
    print("="*60 + "\n")
    
    # For this test, we only need the _build_enriched_chunk method
    try:
        builder = MovieCorpusBuilder()
    except ValueError as e:
        print(f"⚠️  API keys not configured: {e}")
        print("   Testing chunk building with mock builder...")
        builder = object.__new__(MovieCorpusBuilder)
    
    # Mock scene data
    scene = {
        "scene_id": 1,
        "scene_header": "INT. COFFEE SHOP - DAY",
        "location": "COFFEE SHOP",
        "time_of_day": "DAY",
        "int_ext": "INT",
        "characters": ["MIA", "MANAGER"],
        "dialogue": [
            {"character": "MIA", "text": "Sorry I'm late. Traffic was insane."},
            {"character": "MANAGER", "text": "This is the third time this week."}
        ],
        "action_lines": ["Mia enters, looking harried."],
        "raw_text": "INT. COFFEE SHOP - DAY\n\nMia enters...",
        "t_start": 120.0,
        "t_end": 145.5,
        "alignment_confidence": 0.95,
        "alignment_method": "dialogue_match"
    }
    
    # Mock characters
    characters = {
        "MIA": {
            "full_name": "Mia Dolan",
            "actor": "Emma Stone",
            "gender": "female",
            "role": "protagonist",
            "description": "Aspiring actress",
            "occupation": "Barista / Actress"
        },
        "MANAGER": {
            "full_name": "Manager",
            "actor": None,
            "gender": "male",
            "role": "minor",
            "description": "Coffee shop manager",
            "occupation": "Manager"
        }
    }
    
    summary = "Mia arrives late to her barista job and gets reprimanded by her manager."
    movie_id = "test_movie_2024"
    
    # Build chunk
    chunk = builder._build_enriched_chunk(scene, characters, summary, movie_id)
    
    # Validate chunk structure
    assert chunk["chunk_id"] == "test_movie_2024_scene_001", f"Wrong chunk_id: {chunk['chunk_id']}"
    assert chunk["movie_id"] == movie_id
    assert chunk["source_type"] == "script"
    assert chunk["t_start"] == 120.0
    assert chunk["t_end"] == 145.5
    assert chunk["scene_id"] == 1
    assert chunk["location"] == "COFFEE SHOP"
    assert chunk["summary"] == summary
    assert "MIA" in chunk["characters_present"]
    assert "MANAGER" in chunk["characters_present"]
    
    print("✓ Basic chunk fields correct")
    
    # Validate character details
    assert "MIA" in chunk["character_details"]
    mia_details = chunk["character_details"]["MIA"]
    assert mia_details["full_name"] == "Mia Dolan"
    assert mia_details["actor"] == "Emma Stone"
    assert mia_details["gender"] == "female"
    assert mia_details["role"] == "protagonist"
    
    print("✓ Character details embedded correctly")
    
    # Validate dialogue text
    assert "MIA: Sorry I'm late" in chunk["dialogue_text"]
    assert "MANAGER: This is the third time" in chunk["dialogue_text"]
    
    print("✓ Dialogue text formatted correctly")
    
    # Validate action text
    assert "Mia enters, looking harried" in chunk["action_text"]
    
    print("✓ Action text included")
    
    # Validate alignment metadata
    assert chunk["alignment_confidence"] == 0.95
    assert chunk["alignment_method"] == "dialogue_match"
    
    print("✓ Alignment metadata preserved")
    
    # Display sample chunk
    print(f"\n{'='*60}")
    print("Sample Enriched Chunk")
    print(f"{'='*60}")
    print(f"Chunk ID: {chunk['chunk_id']}")
    print(f"Location: {chunk['location']}")
    print(f"Time: {chunk['t_start']:.1f}s - {chunk['t_end']:.1f}s")
    print(f"Characters: {', '.join(chunk['characters_present'])}")
    print(f"Summary: {chunk['summary']}")
    print(f"\nCharacter Details:")
    for char_name, details in chunk['character_details'].items():
        actor_str = f" ({details['actor']})" if details['actor'] else ""
        print(f"  - {details['full_name']}{actor_str}: {details['role']}")
    
    print("\n✅ Chunk building tests passed!\n")
    return True


async def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("MovieCorpusBuilder Test Suite (Step 6)")
    print("="*70)
    
    results = []
    
    # Test 1: Character merging
    result1 = await test_character_merging()
    results.append(("Character Merging", result1))
    
    # Test 2: Enriched chunk building
    result2 = await test_enriched_chunk_building()
    results.append(("Enriched Chunk Building", result2))
    
    # Test 3: Full pipeline (requires script file)
    result3 = await test_full_pipeline()
    results.append(("Full Pipeline", result3))
    
    # Summary
    print("\n" + "="*70)
    print("Test Summary")
    print("="*70)
    
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    print(f"\nTotal: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️  {total_count - passed_count} test(s) failed or skipped")
    
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

