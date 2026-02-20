#!/usr/bin/env python3
"""
Rebuild enriched corpus using the improved timestamp aligner.

This script rebuilds the corpus for "10 Things I Hate About You" using
the new ImprovedTimestampAligner, which eliminates timestamp duplication
and provides better alignment accuracy.

Usage:
    python rebuild_corpus_improved.py
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from preprocessing.corpus_builder import MovieCorpusBuilder
from preprocessing.vector_store import MovieVectorStore


async def rebuild_10_things():
    """Rebuild corpus for 10 Things I Hate About You with improved aligner."""
    
    print("="*80)
    print("REBUILDING CORPUS WITH IMPROVED TIMESTAMP ALIGNER")
    print("="*80)
    print()
    print("Movie: 10 Things I Hate About You")
    print("Improvements:")
    print("  • Anchor-based sequential alignment")
    print("  • Distinctiveness scoring for dialogue")
    print("  • Uniqueness constraints (no duplicate timestamps)")
    print("  • Temporal ordering enforcement")
    print("="*80)
    print()
    
    # Initialize corpus builder with improved aligner
    builder = MovieCorpusBuilder(use_improved_aligner=True)
    
    # Build corpus
    corpus = await builder.build_corpus(
        movie_title="10 Things I Hate About You",
        script_path="scripts/10thingsihateaboutyou_script.txt",
        subtitle_path="data/10thingsihateaboutyou.srt",
        release_year=1999,
        output_dir="corpus"
    )
    
    print("\n" + "="*80)
    print("STORING IN VECTOR DATABASE")
    print("="*80)
    print()
    
    # Store in ChromaDB
    vector_store = MovieVectorStore(persist_directory="./chroma_db")
    vector_store.store_movie_corpus(corpus)
    
    print("\n" + "="*80)
    print("✅ CORPUS REBUILD COMPLETE!")
    print("="*80)
    print()
    print("Validation:")
    print("  1. Check corpus/10_things_i_hate_about_you_1999_enriched.jsonl")
    print("  2. Verify no duplicate timestamps")
    print("  3. Test query at 72:41 (should find Cameron & Bianca scene)")
    print()
    print("Next steps:")
    print("  1. Restart server: uvicorn server.main:app --reload")
    print("  2. Test query: 'who are these two?' at 72:41")
    print("  3. Compare with DIAGNOSIS_72_41_ERROR.md expected results")
    print()
    
    return corpus


def validate_corpus(corpus):
    """Quick validation of rebuilt corpus."""
    scenes = corpus['scenes']
    
    print("\n" + "="*80)
    print("QUICK VALIDATION")
    print("="*80)
    
    # Check for duplicate timestamps
    timestamp_map = {}
    duplicates = []
    
    for scene in scenes:
        ts_key = f"{scene['t_start']:.1f}-{scene['t_end']:.1f}"
        if ts_key in timestamp_map:
            duplicates.append((ts_key, timestamp_map[ts_key], scene['scene_id']))
        timestamp_map[ts_key] = scene['scene_id']
    
    if duplicates:
        print(f"\n❌ FAILED: {len(duplicates)} duplicate timestamps found")
        for ts, s1, s2 in duplicates[:5]:
            print(f"   {ts}: Scene {s1} and Scene {s2}")
    else:
        print(f"\n✅ PASSED: No duplicate timestamps")
    
    # Check temporal ordering
    ordering_errors = 0
    for i in range(1, len(scenes)):
        if scenes[i]['t_start'] < scenes[i-1]['t_end']:
            ordering_errors += 1
    
    if ordering_errors > 0:
        print(f"❌ FAILED: {ordering_errors} temporal ordering violations")
    else:
        print(f"✅ PASSED: Temporal ordering correct")
    
    # Check alignment methods
    anchor_count = sum(1 for s in scenes if s.get('alignment_method') == 'anchor_match')
    interpolated_count = sum(1 for s in scenes if s.get('alignment_method') == 'interpolated')
    anchor_rate = anchor_count / len(scenes) * 100
    
    print(f"\n📊 Alignment Statistics:")
    print(f"   Total scenes: {len(scenes)}")
    print(f"   Anchor matches: {anchor_count} ({anchor_rate:.1f}%)")
    print(f"   Interpolated: {interpolated_count} ({100 - anchor_rate:.1f}%)")
    
    # Check confidence distribution
    confidences = [s['alignment_confidence'] for s in scenes]
    avg_conf = sum(confidences) / len(confidences)
    min_conf = min(confidences)
    max_conf = max(confidences)
    
    print(f"   Avg confidence: {avg_conf:.3f}")
    print(f"   Min confidence: {min_conf:.3f}")
    print(f"   Max confidence: {max_conf:.3f}")
    
    # Check specific timestamp (72:41 = 4361s)
    target_time = 72 * 60 + 41
    scene_at_target = None
    
    for scene in scenes:
        if scene['t_start'] <= target_time <= scene['t_end']:
            scene_at_target = scene
            break
    
    print(f"\n📍 Test Query at 72:41 (4361 seconds):")
    if scene_at_target:
        print(f"   ✅ Scene found: #{scene_at_target['scene_id']}")
        print(f"   Location: {scene_at_target.get('location', 'unknown')}")
        print(f"   Characters: {scene_at_target.get('characters_present', [])}")
        print(f"   Method: {scene_at_target.get('alignment_method')}")
        print(f"   Confidence: {scene_at_target.get('alignment_confidence', 0):.3f}")
        
        # Check if it's Cameron & Bianca
        chars = scene_at_target.get('characters_present', [])
        if 'CAMERON' in chars and 'BIANCA' in chars:
            print(f"   ✅ CORRECT: Cameron & Bianca identified!")
        else:
            print(f"   ⚠️  Expected Cameron & Bianca, got: {chars}")
    else:
        print(f"   ❌ No scene found at this timestamp")
    
    print()


if __name__ == "__main__":
    # Check if required files exist
    if not os.path.exists("scripts/10thingsihateaboutyou_script.txt"):
        print("❌ Error: Script file not found at scripts/10thingsihateaboutyou_script.txt")
        sys.exit(1)
    
    if not os.path.exists("data/10thingsihateaboutyou.srt"):
        print("❌ Error: Subtitle file not found at data/10thingsihateaboutyou.srt")
        sys.exit(1)
    
    # Run rebuild
    corpus = asyncio.run(rebuild_10_things())
    
    # Validate
    validate_corpus(corpus)

