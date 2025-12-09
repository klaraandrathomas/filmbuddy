#!/usr/bin/env python3
"""
Compare original vs improved timestamp aligner.

Shows side-by-side comparison of alignment quality.

Usage:
    python compare_aligners.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from preprocessing.improved_aligner import ImprovedTimestampAligner
from preprocessing.timestamp_aligner import TimestampAligner
from preprocessing.script_parser import ScriptParser


def analyze_alignment(scenes, name):
    """Analyze alignment quality."""
    # Duplicate timestamps
    timestamp_map = {}
    duplicates = []
    for scene in scenes:
        ts_key = f"{scene['t_start']:.1f}-{scene['t_end']:.1f}"
        if ts_key in timestamp_map:
            duplicates.append(ts_key)
        else:
            timestamp_map[ts_key] = scene['scene_id']
    
    # Temporal ordering
    ordering_errors = 0
    for i in range(1, len(scenes)):
        if scenes[i]['t_start'] < scenes[i-1]['t_end']:
            ordering_errors += 1
    
    # Alignment methods
    methods = {}
    for scene in scenes:
        method = scene.get('alignment_method', 'unknown')
        methods[method] = methods.get(method, 0) + 1
    
    # Confidence
    confidences = [s.get('alignment_confidence', 0) for s in scenes]
    avg_conf = sum(confidences) / len(confidences) if confidences else 0
    
    return {
        'name': name,
        'total_scenes': len(scenes),
        'unique_timestamps': len(timestamp_map),
        'duplicates': len(duplicates),
        'ordering_errors': ordering_errors,
        'methods': methods,
        'avg_confidence': avg_conf
    }


def main():
    print("="*80)
    print("COMPARING ORIGINAL VS IMPROVED TIMESTAMP ALIGNERS")
    print("="*80)
    print()
    
    # Parse script
    print("Parsing script...")
    parser = ScriptParser()
    with open("scripts/10thingsihateaboutyou_script.txt", 'r', encoding='utf-8') as f:
        script_text = f.read()
    scenes = parser.parse_script(script_text)
    print(f"  ✓ {len(scenes)} scenes")
    
    # Parse subtitles
    print("Parsing subtitles...")
    improved_aligner = ImprovedTimestampAligner()
    subtitles = improved_aligner.parse_srt("data/10thingsihateaboutyou.srt")
    print(f"  ✓ {len(subtitles)} subtitle cues\n")
    
    # Test original aligner
    print("="*80)
    print("RUNNING ORIGINAL ALIGNER")
    print("="*80)
    original_aligner = TimestampAligner(match_threshold=0.75)
    original_scenes = original_aligner.align_scenes_to_subtitles(scenes[:], subtitles)
    original_stats = analyze_alignment(original_scenes, "Original")
    
    # Test improved aligner
    print("\n" + "="*80)
    print("RUNNING IMPROVED ALIGNER")
    print("="*80)
    improved_scenes = improved_aligner.align_scenes_to_subtitles(scenes[:], subtitles)
    improved_stats = analyze_alignment(improved_scenes, "Improved")
    
    # Compare results
    print("\n" + "="*80)
    print("SIDE-BY-SIDE COMPARISON")
    print("="*80)
    
    print(f"\n{'Metric':<30} {'Original':>15} {'Improved':>15} {'Change':>15}")
    print("-"*80)
    
    # Total scenes
    print(f"{'Total Scenes':<30} {original_stats['total_scenes']:>15} {improved_stats['total_scenes']:>15} {'=':<15}")
    
    # Unique timestamps
    orig_unique = original_stats['unique_timestamps']
    impr_unique = improved_stats['unique_timestamps']
    change = impr_unique - orig_unique
    print(f"{'Unique Timestamps':<30} {orig_unique:>15} {impr_unique:>15} {f'+{change}':>15}")
    
    # Duplicates
    orig_dup = original_stats['duplicates']
    impr_dup = improved_stats['duplicates']
    change = impr_dup - orig_dup
    change_str = f"{change:+d}" if change != 0 else "="
    status = "✅" if impr_dup < orig_dup else "❌"
    print(f"{'Duplicate Timestamps':<30} {orig_dup:>15} {impr_dup:>15} {status + ' ' + change_str:>15}")
    
    # Ordering errors
    orig_ord = original_stats['ordering_errors']
    impr_ord = improved_stats['ordering_errors']
    change = impr_ord - orig_ord
    change_str = f"{change:+d}" if change != 0 else "="
    status = "✅" if impr_ord <= orig_ord else "❌"
    print(f"{'Ordering Errors':<30} {orig_ord:>15} {impr_ord:>15} {status + ' ' + change_str:>15}")
    
    # Confidence
    orig_conf = original_stats['avg_confidence']
    impr_conf = improved_stats['avg_confidence']
    change = impr_conf - orig_conf
    change_str = f"{change:+.3f}" if abs(change) > 0.001 else "="
    status = "✅" if impr_conf >= orig_conf - 0.05 else "⚠️"  # Allow slight decrease
    print(f"{'Average Confidence':<30} {orig_conf:>15.3f} {impr_conf:>15.3f} {status + ' ' + change_str:>15}")
    
    # Alignment methods
    print(f"\n{'Alignment Methods':<30} {'Original':>15} {'Improved':>15}")
    print("-"*80)
    
    all_methods = set(original_stats['methods'].keys()) | set(improved_stats['methods'].keys())
    for method in sorted(all_methods):
        orig_count = original_stats['methods'].get(method, 0)
        impr_count = improved_stats['methods'].get(method, 0)
        orig_pct = orig_count / original_stats['total_scenes'] * 100 if original_stats['total_scenes'] else 0
        impr_pct = impr_count / improved_stats['total_scenes'] * 100 if improved_stats['total_scenes'] else 0
        print(f"  {method:<28} {f'{orig_count} ({orig_pct:.1f}%)':>15} {f'{impr_count} ({impr_pct:.1f}%)':>15}")
    
    # Test case: 72:41
    print(f"\n{'Test Case: 72:41':<30} {'Original':>15} {'Improved':>15}")
    print("-"*80)
    
    target_time = 72 * 60 + 41
    
    orig_scene = None
    for scene in original_scenes:
        if scene['t_start'] <= target_time <= scene['t_end']:
            orig_scene = scene
            break
    
    impr_scene = None
    for scene in improved_scenes:
        if scene['t_start'] <= target_time <= scene['t_end']:
            impr_scene = scene
            break
    
    print(f"  {'Scene Found?':<28} {('Yes' if orig_scene else 'No'):>15} {('Yes ✅' if impr_scene else 'No ❌'):>15}")
    
    if orig_scene:
        print(f"  {'Scene ID':<28} {orig_scene['scene_id']:>15} {(impr_scene['scene_id'] if impr_scene else 'N/A'):>15}")
        print(f"  {'Location':<28} {orig_scene.get('location', 'N/A')[:15]:>15} {(impr_scene.get('location', 'N/A')[:15] if impr_scene else 'N/A'):>15}")
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    improvements = []
    regressions = []
    
    if impr_dup < orig_dup:
        improvements.append(f"Eliminated {orig_dup - impr_dup} duplicate timestamps")
    elif impr_dup > orig_dup:
        regressions.append(f"Added {impr_dup - orig_dup} duplicate timestamps")
    
    if impr_ord < orig_ord:
        improvements.append(f"Fixed {orig_ord - impr_ord} ordering errors")
    elif impr_ord > orig_ord:
        regressions.append(f"Added {impr_ord - orig_ord} ordering errors")
    
    if impr_scene and not orig_scene:
        improvements.append("Test case now has scene at 72:41")
    
    if impr_unique > orig_unique:
        improvements.append(f"Increased unique timestamps by {impr_unique - orig_unique}")
    
    if improvements:
        print("\n✅ Improvements:")
        for imp in improvements:
            print(f"  • {imp}")
    
    if regressions:
        print("\n⚠️  Regressions:")
        for reg in regressions:
            print(f"  • {reg}")
    
    if not regressions and improvements:
        print("\n🎉 The improved aligner is strictly better!")
        print("   Ready to use for corpus building.")
    
    print()


if __name__ == "__main__":
    if not os.path.exists("scripts/10thingsihateaboutyou_script.txt"):
        print("❌ Error: Script file not found")
        sys.exit(1)
    
    if not os.path.exists("data/10thingsihateaboutyou.srt"):
        print("❌ Error: Subtitle file not found")
        sys.exit(1)
    
    main()

