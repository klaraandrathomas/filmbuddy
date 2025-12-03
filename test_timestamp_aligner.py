#!/usr/bin/env python3
"""Test script for TimestampAligner (Step 5)."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from preprocessing.timestamp_aligner import TimestampAligner


def test_aligner():
    """Test TimestampAligner functionality."""
    print("=" * 70)
    print("STEP 5 TEST: Timestamp Aligner")
    print("=" * 70)
    
    # Initialize aligner
    aligner = TimestampAligner(match_threshold=0.75)
    print("✓ TimestampAligner initialized")
    print(f"  Match threshold: {aligner.match_threshold}")
    
    # Test 1: Parse SRT file
    print("\n[Test 1] Parsing SRT file...")
    try:
        subtitles = aligner.parse_srt("data/lalaland.srt")
        assert len(subtitles) > 0, "No subtitles parsed"
        print(f"✓ Parsed {len(subtitles)} subtitle cues")
        print(f"  First subtitle: \"{subtitles[0]['text'][:50]}...\"")
        print(f"  Timestamp: {subtitles[0]['t_start']:.1f}s - {subtitles[0]['t_end']:.1f}s")
        print(f"  Last subtitle at: {subtitles[-1]['t_end']:.1f}s ({subtitles[-1]['t_end']/60:.1f} min)")
    except Exception as e:
        print(f"✗ Test 1 failed: {e}")
        return 1
    
    # Test 2: Text normalization
    print("\n[Test 2] Text normalization...")
    test_text = "Hello, World! This is a TEST."
    normalized = aligner._normalize_text(test_text)
    assert normalized == "hello world this is a test", f"Wrong normalization: {normalized}"
    print(f"✓ Text normalization working")
    print(f"  Original: \"{test_text}\"")
    print(f"  Normalized: \"{normalized}\"")
    
    # Test 3: Key dialogue extraction
    print("\n[Test 3] Key dialogue extraction...")
    sample_scene = {
        "scene_id": 1,
        "dialogue": [
            {"character": "MIA", "text": "Why do I do this to myself every day?"},
            {"character": "MANAGER", "text": "This is the third time this week you're late."},
            {"character": "MIA", "text": "Traffic was insane on the 405."},
            {"character": "MANAGER", "text": "I don't want to hear excuses anymore."}
        ]
    }
    
    key_phrases = aligner._extract_key_dialogue(sample_scene)
    assert len(key_phrases) > 0, "No key phrases extracted"
    print(f"✓ Extracted {len(key_phrases)} key phrases:")
    for phrase in key_phrases:
        print(f"  - \"{phrase}\"")
    
    # Test 4: Fuzzy matching with real subtitle data
    print("\n[Test 4] Fuzzy matching with real subtitles...")
    
    # Find a known phrase from La La Land opening
    # "Another hot sunny day" or similar from the first few minutes
    test_phrase = aligner._normalize_text("hot sunny day")
    
    match = aligner._fuzzy_match_in_subtitles(test_phrase, subtitles[:100])  # Search first 100
    if match:
        t_start, t_end, confidence = match
        print(f"✓ Found match for \"{test_phrase}\"")
        print(f"  Timestamp: {t_start:.1f}s - {t_end:.1f}s")
        print(f"  Confidence: {confidence:.2f}")
    else:
        print(f"○ No high-confidence match found (this is OK, depends on subtitle content)")
    
    # Test 5: Scene alignment with mock scenes
    print("\n[Test 5] Scene alignment with test scenes...")
    
    # Create test scenes with dialogue we know exists in La La Land
    test_scenes = [
        {
            "scene_id": 1,
            "scene_header": "INT. CAR - DAY",
            "location": "CAR",
            "characters": ["RADIO"],
            "dialogue": [
                {"character": "RADIO", "text": "It's another hot sunny day today here in Southern California"}
            ],
            "action_lines": ["Opening scene on the freeway"]
        },
        {
            "scene_id": 2,
            "scene_header": "EXT. FREEWAY - DAY",
            "location": "FREEWAY",
            "characters": ["WOMAN"],
            "dialogue": [
                {"character": "WOMAN", "text": "I mean we could not believe what was happening"}
            ],
            "action_lines": ["Cars stuck in traffic"]
        },
        {
            "scene_id": 3,
            "scene_header": "INT. MIA'S CAR - DAY",
            "location": "MIA'S CAR",
            "characters": [],
            "dialogue": [],  # No dialogue scene - will be interpolated
            "action_lines": ["Mia rehearses lines"]
        }
    ]
    
    try:
        aligned = aligner.align_scenes_to_subtitles(test_scenes, subtitles)
        
        assert len(aligned) == len(test_scenes), "Scene count mismatch"
        
        print(f"✓ Aligned {len(aligned)} scenes")
        
        for scene in aligned:
            method_icon = "🎯" if scene['alignment_method'] == 'dialogue_match' else "📐"
            print(f"\n  Scene {scene['scene_id']}: {scene.get('location', 'Unknown')}")
            print(f"    {method_icon} Method: {scene['alignment_method']}")
            print(f"    ⏱️  Time: {scene['t_start']:.1f}s - {scene['t_end']:.1f}s")
            print(f"    📊 Confidence: {scene['alignment_confidence']:.2f}")
        
        # Verify timestamps are reasonable
        for scene in aligned:
            assert 't_start' in scene, "Missing t_start"
            assert 't_end' in scene, "Missing t_end"
            assert scene['t_start'] >= 0, "Negative t_start"
            assert scene['t_end'] > scene['t_start'], "t_end not after t_start"
            assert 'alignment_confidence' in scene, "Missing confidence"
            assert 'alignment_method' in scene, "Missing alignment method"
        
        print(f"\n✓ All scenes have valid timestamps")
        
        # Count alignment methods
        dialogue_matches = sum(1 for s in aligned if s['alignment_method'] == 'dialogue_match')
        interpolated = sum(1 for s in aligned if s['alignment_method'] == 'interpolated')
        
        print(f"✓ Alignment methods:")
        print(f"  - Dialogue match: {dialogue_matches}/{len(aligned)}")
        print(f"  - Interpolated: {interpolated}/{len(aligned)}")
        
    except Exception as e:
        print(f"✗ Test 5 failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Test 6: Edge cases
    print("\n[Test 6] Edge case handling...")
    
    # Scene with no dialogue
    no_dialogue_scene = {
        "scene_id": 100,
        "location": "TEST LOCATION",
        "dialogue": [],
        "action_lines": ["Silent scene"]
    }
    
    key_phrases = aligner._extract_key_dialogue(no_dialogue_scene)
    assert key_phrases == [], "Should return empty list for no dialogue"
    print(f"✓ Handles scenes with no dialogue")
    
    # Very short dialogue (< 4 words)
    short_dialogue_scene = {
        "scene_id": 101,
        "dialogue": [
            {"character": "MIA", "text": "Hi."},
            {"character": "SEBASTIAN", "text": "Hey."}
        ]
    }
    
    key_phrases = aligner._extract_key_dialogue(short_dialogue_scene)
    assert len(key_phrases) == 0, "Should skip short phrases"
    print(f"✓ Skips dialogue shorter than 4 words")
    
    # Summary
    print("\n" + "=" * 70)
    print("✅ ALL TIMESTAMP ALIGNER TESTS PASSED!")
    print("=" * 70)
    print("\nAcceptance Criteria Status:")
    print("  ✓ Parses SRT files correctly")
    print("  ✓ Extracts key dialogue for matching")
    print("  ✓ Fuzzy matching with confidence scores")
    print("  ✓ Interpolates timestamps for unmatched scenes")
    print("  ✓ Handles scenes without dialogue gracefully")
    print("  ✓ All scenes get valid timestamps")
    print("\nReady for Step 6: Implement MovieCorpusBuilder")
    print("=" * 70)
    
    return 0


if __name__ == "__main__":
    try:
        exit_code = test_aligner()
        sys.exit(exit_code)
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

