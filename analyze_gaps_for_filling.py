#!/usr/bin/env python3
"""
Analyze gaps in enriched corpus and show what dialogue exists for LLM-based gap filling.

This script identifies gaps and shows subtitle dialogue available,
so you can decide whether to proceed with LLM gap filling.
"""

import json
import re


def parse_srt(srt_path: str) -> list:
    """Parse SRT subtitle file."""
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.*?)(?=\n\n|\Z)'
    matches = re.findall(pattern, content, re.DOTALL)
    
    def time_to_seconds(time_str):
        parts = time_str.split(':')
        hours = int(parts[0])
        minutes = int(parts[1])
        secs_ms = parts[2].split(',')
        seconds = int(secs_ms[0])
        ms = int(secs_ms[1])
        return hours * 3600 + minutes * 60 + seconds + ms / 1000
    
    subtitles = []
    for idx, start_time, end_time, text in matches:
        subtitles.append({
            'index': int(idx),
            't_start': time_to_seconds(start_time),
            't_end': time_to_seconds(end_time),
            'text': text.strip().replace('\n', ' ')
        })
    
    return subtitles


def find_gaps(enriched_corpus_path: str, min_gap_size: float = 180) -> list:
    """Find temporal gaps in enriched corpus."""
    with open(enriched_corpus_path, 'r') as f:
        scenes = [json.loads(line) for line in f]
    
    scenes_sorted = sorted(scenes, key=lambda s: s['t_start'])
    
    gaps = []
    for i in range(len(scenes_sorted) - 1):
        current_end = scenes_sorted[i]['t_end']
        next_start = scenes_sorted[i+1]['t_start']
        gap_size = next_start - current_end
        
        if gap_size >= min_gap_size:
            gaps.append({
                'gap_start': current_end,
                'gap_end': next_start,
                'gap_size': gap_size,
                'before_scene': scenes_sorted[i]['location'],
                'after_scene': scenes_sorted[i+1]['location'],
            })
    
    return gaps


def collect_dialogue_stats(subtitles: list, start_time: float, end_time: float) -> dict:
    """Get statistics about dialogue in a time range."""
    dialogue_lines = []
    total_chars = 0
    
    for sub in subtitles:
        if start_time <= sub['t_start'] < end_time:
            dialogue_lines.append(sub['text'])
            total_chars += len(sub['text'])
    
    return {
        'line_count': len(dialogue_lines),
        'char_count': total_chars,
        'sample': '\n'.join(dialogue_lines[:5]) if dialogue_lines else "(No dialogue)",
        'has_content': len(dialogue_lines) > 0
    }


def main():
    print("="*70)
    print("GAP ANALYSIS FOR LLM-BASED CORPUS ENRICHMENT")
    print("="*70)
    
    # Load data
    enriched_path = "corpus/10_things_i_hate_about_you_1999_enriched.jsonl"
    subtitle_path = "data/10thingsihateaboutyou.srt"
    
    print("\n[1/3] Loading data...")
    subtitles = parse_srt(subtitle_path)
    print(f"  ✓ Loaded {len(subtitles)} subtitle entries")
    
    print("\n[2/3] Finding gaps...")
    gaps = find_gaps(enriched_path, min_gap_size=180)  # 3+ minute gaps
    print(f"  ✓ Found {len(gaps)} gaps (≥3 minutes)")
    
    print("\n[3/3] Analyzing dialogue availability...")
    print()
    
    fillable_gaps = []
    empty_gaps = []
    
    for idx, gap in enumerate(gaps, 1):
        mins_start = int(gap['gap_start'] // 60)
        mins_end = int(gap['gap_end'] // 60)
        
        print(f"\n{'='*70}")
        print(f"GAP {idx}/{len(gaps)}")
        print(f"{'='*70}")
        print(f"Time Range: {mins_start}:{int(gap['gap_start']%60):02d} - {mins_end}:{int(gap['gap_end']%60):02d}")
        print(f"Duration: {gap['gap_size']/60:.1f} minutes")
        print(f"Before: {gap['before_scene']}")
        print(f"After:  {gap['after_scene']}")
        print()
        
        # Analyze dialogue availability
        stats = collect_dialogue_stats(subtitles, gap['gap_start'], gap['gap_end'])
        
        if stats['has_content']:
            fillable_gaps.append(gap)
            status = "✅ FILLABLE"
            print(f"Status: {status}")
            print(f"Dialogue Lines: {stats['line_count']}")
            print(f"Characters: ~{stats['char_count']:,}")
            print(f"\nSample dialogue:")
            for line in stats['sample'].split('\n')[:5]:
                print(f"  {line[:70]}{'...' if len(line) > 70 else ''}")
        else:
            empty_gaps.append(gap)
            status = "⚠️  NO DIALOGUE"
            print(f"Status: {status}")
            print(f"  This gap has no subtitle dialogue (likely music/montage)")
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"\nTotal Gaps: {len(gaps)}")
    print(f"  Fillable (with dialogue): {len(fillable_gaps)}")
    print(f"  Empty (no dialogue): {len(empty_gaps)}")
    
    if fillable_gaps:
        total_duration = sum(g['gap_size'] for g in fillable_gaps) / 60
        estimated_chunks = int(total_duration / 2)  # 2-minute chunks
        estimated_cost = estimated_chunks * 0.02  # Rough estimate: $0.02 per call
        
        print(f"\nEstimated LLM Requirements:")
        print(f"  Total duration to fill: {total_duration:.1f} minutes")
        print(f"  Estimated chunks (2-min each): ~{estimated_chunks}")
        print(f"  Estimated API calls: ~{estimated_chunks}")
        print(f"  Estimated cost: ~${estimated_cost:.2f} (rough estimate)")
        
        print(f"\n💡 RECOMMENDATION:")
        print(f"  YES - Proceed with LLM gap filling")
        print(f"  These gaps have dialogue that can be analyzed")
        print(f"  Will significantly improve coverage, especially 70-80 min range")
    
    if empty_gaps:
        print(f"\n⚠️  GAPS WITHOUT DIALOGUE:")
        for gap in empty_gaps:
            mins_start = int(gap['gap_start'] // 60)
            mins_end = int(gap['gap_end'] // 60)
            print(f"  {mins_start}:{int(gap['gap_start']%60):02d} - {mins_end}:{int(gap['gap_end']%60):02d} ({gap['gap_size']/60:.1f} min)")
        print(f"  These likely contain only music/montage")
        print(f"  Cannot create meaningful synthetic scenes for these")
    
    # Check problematic timestamp
    print(f"\n" + "="*70)
    print("SPECIFIC CHECK: Timestamp 69:55 (4195s)")
    print("="*70)
    
    target_time = 69 * 60 + 55
    for gap in gaps:
        if gap['gap_start'] <= target_time < gap['gap_end']:
            stats = collect_dialogue_stats(subtitles, gap['gap_start'], gap['gap_end'])
            print(f"✅ Falls within gap that {'CAN' if stats['has_content'] else 'CANNOT'} be filled")
            print(f"   Gap: {int(gap['gap_start']//60)}:{int(gap['gap_start']%60):02d} - {int(gap['gap_end']//60)}:{int(gap['gap_end']%60):02d}")
            print(f"   Dialogue lines available: {stats['line_count']}")
            break
    else:
        print(f"✓ Already covered (no gap at this timestamp)")
    
    print(f"\n{'='*70}")
    print("Analysis complete!")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
