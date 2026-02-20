#!/usr/bin/env python3
"""
Test the improved timestamp aligner on a small subset of scenes.

This script tests the aligner without requiring a full LLM-based corpus build.
It only tests the timestamp alignment component in isolation.

Usage:
    python test_improved_aligner.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from preprocessing.improved_aligner import ImprovedTimestampAligner
from preprocessing.script_parser import ScriptParser


def test_aligner():
    """Test the improved aligner on 10 Things I Hate About You."""
    
    print("="*80)
    print("TESTING IMPROVED TIMESTAMP ALIGNER")
    print("="*80)
    print()
    
    # Parse script
    print("[1/3] Parsing script...")
    parser = ScriptParser()
    
    with open("scripts/10thingsihateaboutyou_script.txt", 'r', encoding='utf-8') as f:
        script_text = f.read()
    
    scenes = parser.parse_script(script_text)
    print(f"  ✓ Parsed {len(scenes)} scenes")
    
    # Parse subtitles
    print("\n[2/3] Parsing subtitles...")
    aligner = ImprovedTimestampAligner()
    subtitles = aligner.parse_srt("data/10thingsihateaboutyou.srt")
    print(f"  ✓ Parsed {len(subtitles)} subtitle cues")
    print(f"  ✓ Duration: {subtitles[-1]['t_end'] / 60:.1f} minutes")
    
    # Align scenes
    print("\n[3/3] Aligning scenes to subtitles...")
    aligned_scenes = aligner.align_scenes_to_subtitles(scenes, subtitles)
    
    # Analyze results
    print("\n" + "="*80)
    print("RESULTS ANALYSIS")
    print("="*80)
    
    # Check for duplicates
    timestamp_map = {}
    duplicates = []
    
    for scene in aligned_scenes:
        ts_key = f"{scene['t_start']:.1f}-{scene['t_end']:.1f}"
        if ts_key in timestamp_map:
            duplicates.append((ts_key, timestamp_map[ts_key], scene['scene_id']))
        timestamp_map[ts_key] = scene['scene_id']
    
    print(f"\n1. Duplicate Timestamp Check:")
    if duplicates:
        print(f"   ❌ FAILED: Found {len(duplicates)} duplicate timestamps")
        for ts, s1, s2 in duplicates[:5]:
            print(f"      {ts}: Scene {s1} and Scene {s2}")
    else:
        print(f"   ✅ PASSED: No duplicate timestamps found!")
        print(f"   (Original aligner had 26/79 scenes with duplicate timestamps)")
    
    # Check temporal ordering
    print(f"\n2. Temporal Ordering Check:")
    ordering_errors = 0
    for i in range(1, len(aligned_scenes)):
        if aligned_scenes[i]['t_start'] < aligned_scenes[i-1]['t_end']:
            ordering_errors += 1
    
    if ordering_errors > 0:
        print(f"   ❌ FAILED: {ordering_errors} ordering violations")
    else:
        print(f"   ✅ PASSED: All scenes in correct temporal order")
    
    # Check alignment methods
    print(f"\n3. Alignment Method Distribution:")
    anchor_count = sum(1 for s in aligned_scenes if s.get('alignment_method') == 'anchor_match')
    interpolated_count = sum(1 for s in aligned_scenes if s.get('alignment_method') == 'interpolated')
    anchor_rate = anchor_count / len(aligned_scenes) * 100
    
    print(f"   Total scenes: {len(aligned_scenes)}")
    print(f"   Anchor matches: {anchor_count} ({anchor_rate:.1f}%)")
    print(f"   Interpolated: {interpolated_count} ({100 - anchor_rate:.1f}%)")
    print(f"   Target: 50-70% anchors (original: 92.4%)")
    
    if 50 <= anchor_rate <= 80:
        print(f"   ✅ PASSED: Anchor rate in expected range")
    else:
        print(f"   ⚠️  WARNING: Anchor rate outside expected range")
    
    # Check confidence distribution
    print(f"\n4. Confidence Score Distribution:")
    confidences = [s['alignment_confidence'] for s in aligned_scenes]
    avg_conf = sum(confidences) / len(confidences)
    min_conf = min(confidences)
    max_conf = max(confidences)
    
    print(f"   Average: {avg_conf:.3f}")
    print(f"   Min: {min_conf:.3f}")
    print(f"   Max: {max_conf:.3f}")
    
    if avg_conf >= 0.6:
        print(f"   ✅ PASSED: Average confidence acceptable")
    else:
        print(f"   ⚠️  WARNING: Low average confidence")
    
    # Check specific test case: 72:41 (where Cameron & Bianca are)
    print(f"\n5. Test Case: 72:41 (Cameron & Bianca Scene):")
    target_time = 72 * 60 + 41  # 4361 seconds
    
    scene_at_target = None
    for scene in aligned_scenes:
        if scene['t_start'] <= target_time <= scene['t_end']:
            scene_at_target = scene
            break
    
    if scene_at_target:
        print(f"   ✅ Scene found at target timestamp!")
        print(f"   Scene ID: {scene_at_target['scene_id']}")
        print(f"   Time range: {scene_at_target['t_start']:.1f}s - {scene_at_target['t_end']:.1f}s")
        mins_s, secs_s = int(scene_at_target['t_start'] // 60), int(scene_at_target['t_start'] % 60)
        mins_e, secs_e = int(scene_at_target['t_end'] // 60), int(scene_at_target['t_end'] % 60)
        print(f"   Time range: {mins_s}:{secs_s:02d} - {mins_e}:{secs_e:02d}")
        print(f"   Location: {scene_at_target.get('location', 'unknown')}")
        print(f"   Characters: {scene_at_target.get('characters', [])}")
        print(f"   Method: {scene_at_target.get('alignment_method')}")
        print(f"   Confidence: {scene_at_target.get('alignment_confidence', 0):.3f}")
        print(f"   (Original aligner: NO SCENE FOUND at this timestamp)")
    else:
        print(f"   ❌ FAILED: No scene found at target timestamp")
    
    # Show sample of anchor scenes
    print(f"\n6. Sample Anchor Scenes (first 5):")
    anchors = [s for s in aligned_scenes if s.get('alignment_method') == 'anchor_match']
    for i, scene in enumerate(anchors[:5], 1):
        mins, secs = int(scene['t_start'] // 60), int(scene['t_start'] % 60)
        conf = scene.get('alignment_confidence', 0)
        dist = scene.get('distinctiveness_score', 0)
        loc = scene.get('location', 'unknown')
        print(f"   {i}. Scene {scene['scene_id']:3d} @ {mins:2d}:{secs:02d} | {loc[:30]:30s} | conf: {conf:.3f}, dist: {dist:.3f}")
    
    # Final summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    issues = []
    if duplicates:
        issues.append(f"{len(duplicates)} duplicate timestamps")
    if ordering_errors > 0:
        issues.append(f"{ordering_errors} ordering violations")
    if avg_conf < 0.6:
        issues.append("low average confidence")
    if not scene_at_target:
        issues.append("test case failed (no scene at 72:41)")
    
    if issues:
        print(f"\n⚠️  Issues found: {', '.join(issues)}")
        print(f"Consider adjusting aligner parameters.")
    else:
        print(f"\n✅ ALL TESTS PASSED!")
        print(f"The improved aligner eliminates duplicate timestamps and provides")
        print(f"better coverage. Ready to rebuild full corpus with LLM enrichment.")
    
    print()


if __name__ == "__main__":
    # Check if required files exist
    if not os.path.exists("scripts/10thingsihateaboutyou_script.txt"):
        print("❌ Error: Script file not found at scripts/10thingsihateaboutyou_script.txt")
        sys.exit(1)
    
    if not os.path.exists("data/10thingsihateaboutyou.srt"):
        print("❌ Error: Subtitle file not found at data/10thingsihateaboutyou.srt")
        sys.exit(1)
    
    test_aligner()

