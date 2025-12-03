"""
Test script for MovieVectorStore (Step 7)

Tests ChromaDB integration:
1. Storing enriched corpus
2. Timestamp-based queries
3. Character lookup by scene
4. Semantic search with temporal constraints
5. Spoiler filtering
6. Movie listing and metadata retrieval
"""

import json
from pathlib import Path
from preprocessing.vector_store import MovieVectorStore


def load_test_corpus():
    """Load the La La Land enriched corpus we created in Step 6."""
    corpus_path = Path("corpus/la_la_land_2016_enriched.jsonl")
    metadata_path = Path("corpus/la_la_land_2016_metadata.json")
    
    if not corpus_path.exists():
        print(f"⚠️  Corpus file not found: {corpus_path}")
        print("   Run test_corpus_builder.py first to generate the corpus.")
        return None
    
    # Load scenes from JSONL
    scenes = []
    with open(corpus_path, 'r', encoding='utf-8') as f:
        for line in f:
            scenes.append(json.loads(line))
    
    # Load metadata
    with open(metadata_path, 'r', encoding='utf-8') as f:
        corpus_meta = json.load(f)
    
    # Combine into corpus format
    corpus = {
        'movie_id': corpus_meta['movie_id'],
        'metadata': corpus_meta['metadata'],
        'characters': corpus_meta['characters'],
        'scenes': scenes,
        'stats': corpus_meta['stats']
    }
    
    return corpus


def test_store_corpus():
    """Test storing a corpus in ChromaDB."""
    print("\n" + "="*60)
    print("Test 1: Store Corpus in ChromaDB")
    print("="*60 + "\n")
    
    # Load test corpus
    corpus = load_test_corpus()
    if not corpus:
        return False
    
    # Initialize vector store
    store = MovieVectorStore(persist_directory="./test_chroma_db")
    
    # Store corpus
    store.store_movie_corpus(corpus)
    
    # Verify it was stored
    movies = store.list_movies()
    assert "la_la_land_2016" in movies, "Movie not found in store"
    print(f"✓ Movie stored successfully")
    print(f"✓ Movies in store: {movies}")
    
    # Verify has_movie
    assert store.has_movie("la_la_land_2016"), "has_movie() returned False"
    print(f"✓ has_movie() working correctly")
    
    print("\n✅ Store corpus test passed!\n")
    return True


def test_timestamp_query():
    """Test querying scenes by timestamp."""
    print("\n" + "="*60)
    print("Test 2: Timestamp-Based Query")
    print("="*60 + "\n")
    
    store = MovieVectorStore(persist_directory="./test_chroma_db")
    
    # Query at specific timestamp (should match first scene)
    timestamp = 50.0  # In the middle of first scene (38.8 - 61.5)
    scene = store.query_scene_at_timestamp("la_la_land_2016", timestamp)
    
    assert scene is not None, f"No scene found at timestamp {timestamp}"
    print(f"✓ Found scene at timestamp {timestamp}s")
    print(f"  Scene ID: {scene['scene_id']}")
    print(f"  Location: {scene['location']}")
    print(f"  Time range: {scene['t_start']:.1f}s - {scene['t_end']:.1f}s")
    print(f"  Characters: {', '.join(scene['characters_present'])}")
    
    # Verify it's the right scene
    assert scene['scene_id'] == 1, f"Wrong scene: expected 1, got {scene['scene_id']}"
    assert scene['location'] == "MIA'S CAR", f"Wrong location: {scene['location']}"
    assert 'MIA' in scene['characters_present'], "MIA not in characters"
    
    print(f"✓ Correct scene retrieved")
    
    # Test edge case: timestamp outside any scene
    far_future = 99999.0
    scene = store.query_scene_at_timestamp("la_la_land_2016", far_future)
    print(f"\n✓ Timestamp {far_future}s (outside range): {'Found' if scene else 'Not found (expected)'}")
    
    print("\n✅ Timestamp query test passed!\n")
    return True


def test_character_query():
    """Test querying characters in a specific scene."""
    print("\n" + "="*60)
    print("Test 3: Character Query by Scene")
    print("="*60 + "\n")
    
    store = MovieVectorStore(persist_directory="./test_chroma_db")
    
    # Query characters in scene 1
    characters = store.query_characters_in_scene("la_la_land_2016", scene_id=1)
    
    assert len(characters) > 0, "No characters found in scene 1"
    print(f"✓ Found {len(characters)} characters in scene 1:")
    
    for char in characters:
        actor_str = f" (played by {char['actor']})" if char.get('actor') else ""
        print(f"  - {char['full_name']}{actor_str}")
        print(f"    Role: {char['role']}, Gender: {char['gender']}")
    
    # Verify MIA is present
    char_names = [c['character_name'] for c in characters]
    assert 'MIA' in char_names, "MIA not found in scene 1"
    
    print(f"\n✓ Character details correct")
    
    print("\n✅ Character query test passed!\n")
    return True


def test_semantic_search():
    """Test semantic search functionality."""
    print("\n" + "="*60)
    print("Test 4: Semantic Search")
    print("="*60 + "\n")
    
    store = MovieVectorStore(persist_directory="./test_chroma_db")
    
    # Test various queries
    test_queries = [
        ("traffic jam", "Should find the car/traffic scene"),
        ("coffee shop", "Should find the coffee shop scene"),
        ("jazz music", "Should find jazz-related scenes"),
        ("audition", "Should find audition-related scenes"),
    ]
    
    for query, description in test_queries:
        print(f"Query: '{query}'")
        print(f"  Expected: {description}")
        
        results = store.semantic_search(
            movie_id="la_la_land_2016",
            query=query,
            top_k=3
        )
        
        assert len(results) > 0, f"No results for query: {query}"
        print(f"  ✓ Found {len(results)} results")
        
        # Show top result
        top_result = results[0]
        print(f"  Top result:")
        print(f"    Scene {top_result['scene_id']}: {top_result['location']}")
        print(f"    Relevance: {top_result['relevance_score']:.3f}")
        print(f"    Time: {top_result['t_start']:.1f}s - {top_result['t_end']:.1f}s")
        print()
    
    print("✅ Semantic search test passed!\n")
    return True


def test_spoiler_filtering():
    """Test spoiler mode filtering."""
    print("\n" + "="*60)
    print("Test 5: Spoiler Filtering")
    print("="*60 + "\n")
    
    store = MovieVectorStore(persist_directory="./test_chroma_db")
    
    # Get a timestamp in the middle of the movie
    current_timestamp = 100.0  # Viewing at 100 seconds
    
    # Search with spoiler mode OFF (should only return scenes before timestamp)
    print(f"Query at timestamp {current_timestamp}s with spoiler_mode=OFF")
    results_no_spoilers = store.semantic_search(
        movie_id="la_la_land_2016",
        query="what happens",
        timestamp=current_timestamp,
        top_k=10,
        spoiler_mode="off"
    )
    
    print(f"  ✓ Found {len(results_no_spoilers)} results")
    for result in results_no_spoilers:
        assert result['t_start'] <= current_timestamp, \
            f"Spoiler leaked! Scene {result['scene_id']} starts at {result['t_start']}s"
        print(f"    Scene {result['scene_id']}: starts at {result['t_start']:.1f}s (OK)")
    
    print(f"\n✓ No spoilers leaked with spoiler_mode=OFF")
    
    # Search with spoiler mode ON (should return all scenes)
    print(f"\nQuery with spoiler_mode=ON")
    results_with_spoilers = store.semantic_search(
        movie_id="la_la_land_2016",
        query="what happens",
        timestamp=current_timestamp,
        top_k=10,
        spoiler_mode="on"
    )
    
    print(f"  ✓ Found {len(results_with_spoilers)} results")
    
    # Should have more results with spoilers on
    assert len(results_with_spoilers) >= len(results_no_spoilers), \
        "Spoiler mode ON should return at least as many results"
    
    print(f"✓ Spoiler mode ON returns {len(results_with_spoilers)} scenes (all available)")
    
    print("\n✅ Spoiler filtering test passed!\n")
    return True


def test_movie_metadata():
    """Test movie metadata retrieval."""
    print("\n" + "="*60)
    print("Test 6: Movie Metadata Retrieval")
    print("="*60 + "\n")
    
    store = MovieVectorStore(persist_directory="./test_chroma_db")
    
    # Get movie metadata
    metadata = store.get_movie_metadata("la_la_land_2016")
    
    assert metadata is not None, "Metadata not found"
    print(f"✓ Retrieved metadata for: {metadata['metadata']['title']}")
    print(f"  Release year: {metadata['metadata']['release_year']}")
    print(f"  Runtime: {metadata['metadata']['runtime_seconds'] / 60:.0f} minutes")
    print(f"  Genres: {', '.join(metadata['metadata']['genres'])}")
    
    # Get all characters
    characters = store.get_all_characters("la_la_land_2016")
    print(f"\n✓ Retrieved {len(characters)} characters")
    
    # Show a few characters with actors
    print(f"  Sample characters:")
    for char_name, char_data in list(characters.items())[:5]:
        actor_str = f" → {char_data['actor']}" if char_data.get('actor') else ""
        print(f"    - {char_data['full_name']}{actor_str}")
    
    print("\n✅ Metadata retrieval test passed!\n")
    return True


def test_delete_movie():
    """Test deleting a movie from the store."""
    print("\n" + "="*60)
    print("Test 7: Delete Movie")
    print("="*60 + "\n")
    
    store = MovieVectorStore(persist_directory="./test_chroma_db")
    
    # Verify movie exists
    assert store.has_movie("la_la_land_2016"), "Movie not found before delete"
    print(f"✓ Movie exists in store")
    
    # Delete movie
    success = store.delete_movie("la_la_land_2016")
    assert success, "Delete operation failed"
    print(f"✓ Movie deleted successfully")
    
    # Verify movie is gone
    assert not store.has_movie("la_la_land_2016"), "Movie still exists after delete"
    print(f"✓ Movie no longer in store")
    
    # Verify list is empty
    movies = store.list_movies()
    assert "la_la_land_2016" not in movies, "Movie still in list"
    print(f"✓ Movie removed from list")
    
    print("\n✅ Delete movie test passed!\n")
    return True


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("MovieVectorStore Test Suite (Step 7)")
    print("="*70)
    
    results = []
    
    # Test 1: Store corpus
    result1 = test_store_corpus()
    results.append(("Store Corpus", result1))
    
    if not result1:
        print("\n⚠️  Skipping remaining tests (corpus not available)")
        return
    
    # Test 2: Timestamp query
    try:
        result2 = test_timestamp_query()
        results.append(("Timestamp Query", result2))
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        results.append(("Timestamp Query", False))
    
    # Test 3: Character query
    try:
        result3 = test_character_query()
        results.append(("Character Query", result3))
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        results.append(("Character Query", False))
    
    # Test 4: Semantic search
    try:
        result4 = test_semantic_search()
        results.append(("Semantic Search", result4))
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        results.append(("Semantic Search", False))
    
    # Test 5: Spoiler filtering
    try:
        result5 = test_spoiler_filtering()
        results.append(("Spoiler Filtering", result5))
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        results.append(("Spoiler Filtering", False))
    
    # Test 6: Metadata retrieval
    try:
        result6 = test_movie_metadata()
        results.append(("Metadata Retrieval", result6))
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        results.append(("Metadata Retrieval", False))
    
    # Test 7: Delete movie (run last since it removes the data)
    try:
        result7 = test_delete_movie()
        results.append(("Delete Movie", result7))
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        results.append(("Delete Movie", False))
    
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
        print(f"\n⚠️  {total_count - passed_count} test(s) failed")
    
    print("="*70 + "\n")


if __name__ == "__main__":
    main()

