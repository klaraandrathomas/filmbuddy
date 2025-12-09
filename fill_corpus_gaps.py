#!/usr/bin/env python3
"""
Fill Corpus Gaps with LLM-Generated Summaries

For time ranges where we have no enriched scenes (but DO have subtitles),
generate synthetic enriched scenes by:
1. Collecting subtitle dialogue in the gap
2. Using LLM to generate scene summary and infer context
3. Creating enriched scene chunks with "synthetic" marker

This provides better context than nothing for the 70-80 min gap and other problem areas.
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add preprocessing to path
sys.path.insert(0, os.path.dirname(__file__))

from preprocessing.character_extractor import CharacterExtractor

# Use existing CharacterExtractor which has Azure OpenAI setup
extractor = CharacterExtractor()


def parse_srt(srt_path: str) -> List[Dict]:
    """Parse SRT subtitle file into list of dialogue entries."""
    import re
    
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Pattern: index, timestamp, text
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


def find_gaps(enriched_corpus_path: str, min_gap_size: float = 60) -> List[Dict]:
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
                'before_scene_id': scenes_sorted[i]['scene_id'],
                'after_scene_id': scenes_sorted[i+1]['scene_id'],
            })
    
    return gaps


def collect_dialogue_in_range(subtitles: List[Dict], start_time: float, end_time: float) -> str:
    """Collect all subtitle dialogue within a time range."""
    dialogue_parts = []
    
    for sub in subtitles:
        if start_time <= sub['t_start'] < end_time:
            # Format with timestamp
            mins = int(sub['t_start'] // 60)
            secs = int(sub['t_start'] % 60)
            dialogue_parts.append(f"[{mins}:{secs:02d}] {sub['text']}")
    
    return '\n'.join(dialogue_parts)


async def generate_scene_summary(dialogue: str, start_time: float, end_time: float) -> Dict:
    """Use LLM to generate scene summary from dialogue."""
    
    mins_start = int(start_time // 60)
    mins_end = int(end_time // 60)
    
    prompt = f"""You are analyzing a segment of dialogue from the movie "10 Things I Hate About You" 
from {mins_start}:{int(start_time%60):02d} to {mins_end}:{int(end_time%60):02d}.

DIALOGUE:
{dialogue}

Based on this dialogue, provide a JSON response with:
1. "location" - Your best guess of where this scene takes place (e.g., "SCHOOL HALLWAY", "CLASSROOM", "HOUSE", "OUTDOOR LOCATION"). If uncertain, use "UNKNOWN LOCATION"
2. "summary" - A 1-2 sentence summary of what's happening in this scene
3. "characters" - List of character names mentioned or speaking (extract from dialogue)
4. "tone" - The emotional tone (e.g., "romantic", "tense", "comedic", "action")

IMPORTANT: 
- Only use information from the dialogue provided
- If you can't determine something, use "Unknown" or empty list
- Be concise and factual
- Return ONLY valid JSON, no other text

Example format:
{{
    "location": "CLASSROOM",
    "summary": "Students are taking an exam while the teacher monitors the room.",
    "characters": ["KAT", "TEACHER"],
    "tone": "tense"
}}"""

    try:
        # Use extractor's LLM client
        response = extractor.client.chat.completions.create(
            model=extractor.deployment_name,
            messages=[
                {"role": "system", "content": "You are a movie analysis assistant. Respond only with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=400
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # Try to parse JSON (handle markdown code blocks if present)
        if result_text.startswith('```'):
            # Extract JSON from code block
            lines = result_text.split('\n')
            result_text = '\n'.join(lines[1:-1])
        
        result = json.loads(result_text)
        return result
        
    except Exception as e:
        print(f"Error generating summary: {e}")
        return {
            "location": "UNKNOWN LOCATION",
            "summary": "Scene with dialogue.",
            "characters": [],
            "tone": "unknown"
        }


def create_synthetic_scene(
    movie_id: str,
    scene_id: int,
    gap: Dict,
    dialogue: str,
    llm_analysis: Dict
) -> Dict:
    """Create synthetic enriched scene from LLM analysis."""
    
    return {
        # IDs
        'chunk_id': f"{movie_id}_synthetic_{scene_id:03d}",
        'movie_id': movie_id,
        'source_type': 'synthetic',  # Mark as synthetic
        
        # Timestamps
        't_start': gap['gap_start'],
        't_end': gap['gap_end'],
        
        # Scene info (from LLM)
        'scene_id': scene_id,
        'scene_header': f"SYNTHETIC - {llm_analysis.get('location', 'UNKNOWN')}",
        'location': llm_analysis.get('location', 'UNKNOWN LOCATION'),
        'time_of_day': None,
        'int_ext': None,
        
        # Content
        'summary': llm_analysis.get('summary', 'Scene extracted from dialogue.'),
        'dialogue_text': dialogue,
        'action_text': f"(Synthetic scene - no script source)\nTone: {llm_analysis.get('tone', 'unknown')}",
        'raw_text': dialogue,
        
        # Characters (from LLM)
        'characters_present': llm_analysis.get('characters', []),
        'character_details': {},  # No detailed character info for synthetic scenes
        
        # Alignment metadata
        'alignment_confidence': 0.5,  # Medium-low confidence (synthetic)
        'alignment_method': 'synthetic_llm',
        
        # Additional metadata
        'synthetic': True,
        'generation_method': 'llm_dialogue_analysis',
    }


async def fill_gap(
    gap: Dict,
    subtitles: List[Dict],
    movie_id: str,
    scene_id_start: int
) -> List[Dict]:
    """Fill a gap by creating synthetic scenes."""
    
    print(f"\nProcessing gap: {gap['gap_size']/60:.1f} minutes ({int(gap['gap_start']//60)}:{int(gap['gap_start']%60):02d} - {int(gap['gap_end']//60)}:{int(gap['gap_end']%60):02d})")
    
    # Split large gaps into ~2 minute chunks
    chunk_size = 120  # 2 minutes
    synthetic_scenes = []
    
    current_start = gap['gap_start']
    chunk_num = 0
    
    while current_start < gap['gap_end']:
        current_end = min(current_start + chunk_size, gap['gap_end'])
        
        # Collect dialogue in this chunk
        dialogue = collect_dialogue_in_range(subtitles, current_start, current_end)
        
        if not dialogue.strip():
            print(f"  Chunk {chunk_num + 1}: No dialogue found, skipping")
            current_start = current_end
            chunk_num += 1
            continue
        
        print(f"  Chunk {chunk_num + 1}: {int(current_start//60)}:{int(current_start%60):02d} - {int(current_end//60)}:{int(current_end%60):02d}")
        print(f"    Dialogue lines: {len(dialogue.split(chr(10)))}")
        
        # Generate summary via LLM
        llm_analysis = await generate_scene_summary(dialogue, current_start, current_end)
        print(f"    Location: {llm_analysis.get('location', 'Unknown')}")
        print(f"    Summary: {llm_analysis.get('summary', 'N/A')[:60]}...")
        
        # Create synthetic scene
        synthetic_scene = create_synthetic_scene(
            movie_id=movie_id,
            scene_id=scene_id_start + chunk_num,
            gap={'gap_start': current_start, 'gap_end': current_end},
            dialogue=dialogue,
            llm_analysis=llm_analysis
        )
        
        synthetic_scenes.append(synthetic_scene)
        
        current_start = current_end
        chunk_num += 1
    
    return synthetic_scenes


async def main():
    """Main function to fill corpus gaps."""
    
    print("="*70)
    print("CORPUS GAP FILLER - LLM-Based Synthetic Scene Generation")
    print("="*70)
    
    # Paths
    movie_id = "10_things_i_hate_about_you_1999"
    enriched_path = f"corpus/{movie_id}_enriched.jsonl"
    subtitle_path = "data/10thingsihateaboutyou.srt"
    output_path = f"corpus/{movie_id}_enriched_with_synthetic.jsonl"
    
    # Load data
    print("\n[1/5] Loading existing enriched corpus...")
    with open(enriched_path, 'r') as f:
        existing_scenes = [json.loads(line) for line in f]
    print(f"  Loaded {len(existing_scenes)} scenes")
    
    print("\n[2/5] Loading subtitles...")
    subtitles = parse_srt(subtitle_path)
    print(f"  Loaded {len(subtitles)} subtitle entries")
    
    print("\n[3/5] Finding gaps in corpus...")
    gaps = find_gaps(enriched_path, min_gap_size=180)  # 3+ minute gaps
    print(f"  Found {len(gaps)} gaps (≥3 minutes)")
    
    # Get next available scene ID
    max_scene_id = max(s['scene_id'] for s in existing_scenes)
    next_scene_id = max_scene_id + 1
    
    print(f"\n[4/5] Generating synthetic scenes...")
    print(f"  Starting scene IDs from {next_scene_id}")
    
    all_synthetic_scenes = []
    
    for idx, gap in enumerate(gaps, 1):
        print(f"\n--- Gap {idx}/{len(gaps)} ---")
        
        synthetic_scenes = await fill_gap(
            gap=gap,
            subtitles=subtitles,
            movie_id=movie_id,
            scene_id_start=next_scene_id
        )
        
        all_synthetic_scenes.extend(synthetic_scenes)
        next_scene_id += len(synthetic_scenes)
        
        # Rate limiting
        if idx < len(gaps):
            await asyncio.sleep(2)  # 2 second delay between gaps
    
    print(f"\n[5/5] Saving enhanced corpus...")
    print(f"  Original scenes: {len(existing_scenes)}")
    print(f"  Synthetic scenes: {len(all_synthetic_scenes)}")
    print(f"  Total: {len(existing_scenes) + len(all_synthetic_scenes)}")
    
    # Combine and sort by timestamp
    all_scenes = existing_scenes + all_synthetic_scenes
    all_scenes_sorted = sorted(all_scenes, key=lambda s: s['t_start'])
    
    # Save to new file
    with open(output_path, 'w', encoding='utf-8') as f:
        for scene in all_scenes_sorted:
            f.write(json.dumps(scene, ensure_ascii=False) + '\n')
    
    print(f"\n✅ Saved to: {output_path}")
    
    # Generate report
    print("\n" + "="*70)
    print("COVERAGE REPORT")
    print("="*70)
    
    # Check coverage of originally problematic timestamp
    target_time = 69 * 60 + 55
    found = False
    for scene in all_scenes_sorted:
        if scene['t_start'] <= target_time <= scene['t_end']:
            print(f"\n🎯 Timestamp 69:55 ({target_time}s) - NOW COVERED!")
            print(f"   Scene: {scene['location']}")
            print(f"   Type: {'SYNTHETIC' if scene.get('synthetic') else 'ORIGINAL'}")
            print(f"   Confidence: {scene['alignment_confidence']}")
            found = True
            break
    
    if not found:
        print(f"\n⚠️  Timestamp 69:55 still not covered")
    
    print("\n✅ Corpus gap filling complete!")


if __name__ == "__main__":
    asyncio.run(main())

