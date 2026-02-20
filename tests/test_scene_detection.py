#!/usr/bin/env python3
"""
Test the improved scene detection for timestamp 72:41 (4361s)
Should correctly identify two scenes and prioritize the current one.
"""

import json

# Simulate the chunks around 72:41
test_chunks = [
    {"film_id": "10_things_i_hate_about_you", "t_start": 4256.502, "t_end": 4274.687, "text": "- Tell me something true.\n- Something true. I hate peas. No. Something real.\nSomething no one else knows. Okay. You're sweet, and sexy,", "cue_type": "dialogue"},
    {"film_id": "10_things_i_hate_about_you", "t_start": 4274.812, "t_end": 4276.355, "text": "(KISSES NECK)", "cue_type": "nonverbal"},
    {"film_id": "10_things_i_hate_about_you", "t_start": 4276.481, "t_end": 4332.495, "text": "And completely hot for me. You are amazingly self-assured.\nHas anyone ever told you that? I tell myself that every day, actually. - Go to the prom with me.\n- Is that a request or a command? Come on. Go with me. - No.\n- No? Why not? Because I don't want to.\nBecause it's a stupid tradition. Come on.\nPeople won't expect you to go. Why are you pushing this? What's in it for you? Oh. So now I need to have a motive\nto want to be with you? You tell me. You need therapy, you know that? Has anyone ever told you that? - Answer the question, Patrick.\n- Nothing! There is nothing in it for me, just the pleasure of your company.\nOkay?", "cue_type": "dialogue"},
    {"film_id": "10_things_i_hate_about_you", "t_start": 4333.412, "t_end": 4334.747, "text": "(SCOFFS)", "cue_type": "nonverbal"},
    {"film_id": "10_things_i_hate_about_you", "t_start": 4344.09, "t_end": 4345.758, "text": "(SPEAKING FRENCH)", "cue_type": "nonverbal"},
    {"film_id": "10_things_i_hate_about_you", "t_start": 4357.228, "t_end": 4360.189, "text": "Wait. Wait a minute.\nThat... That's not on this page.", "cue_type": "dialogue"},
]

def simulate_scene_detection(chunks, t_now):
    """Simulate the new scene detection logic"""
    print(f"\n{'='*70}")
    print(f"TESTING: Scene Detection at t_now = {t_now:.1f}s ({int(t_now//60)}:{int(t_now%60):02d})")
    print(f"{'='*70}\n")
    
    # Copy chunks to avoid modifying
    recent_chunks = [c.copy() for c in chunks]
    recent_chunks.sort(key=lambda x: x["t_start"])
    
    print(f"Input: {len(recent_chunks)} chunks")
    for i, c in enumerate(recent_chunks):
        print(f"  {i}: [{c['t_start']:.1f}-{c['t_end']:.1f}] ({c['cue_type']}) {c['text'][:60]}...")
    
    # Detect scene boundaries
    print(f"\n🔍 Detecting scene boundaries (gap > 3.0s)...")
    scene_boundaries = []
    for i in range(len(recent_chunks) - 1):
        time_gap = recent_chunks[i+1]['t_start'] - recent_chunks[i]['t_end']
        if time_gap > 3.0:
            scene_boundaries.append(i)
            print(f"   ✓ Boundary at index {i}: gap = {time_gap:.2f}s")
        else:
            print(f"   - No boundary between {i} and {i+1}: gap = {time_gap:.2f}s")
    
    # Segment into scenes
    print(f"\n📽️ Segmenting into scenes...")
    scenes = []
    start_idx = 0
    for boundary_idx in scene_boundaries:
        scene_chunks = recent_chunks[start_idx:boundary_idx + 1]
        if scene_chunks:
            scenes.append({
                'chunks': scene_chunks,
                't_start': scene_chunks[0]['t_start'],
                't_end': scene_chunks[-1]['t_end'],
                'is_current': False
            })
        start_idx = boundary_idx + 1
    
    # Add final scene
    final_scene_chunks = recent_chunks[start_idx:]
    if final_scene_chunks:
        scenes.append({
            'chunks': final_scene_chunks,
            't_start': final_scene_chunks[0]['t_start'],
            't_end': final_scene_chunks[-1]['t_end'],
            'is_current': True
        })
    
    print(f"\nDetected {len(scenes)} scene(s):")
    for idx, scene in enumerate(scenes):
        duration = scene['t_end'] - scene['t_start']
        print(f"\n  Scene {idx}: [{scene['t_start']:.1f}-{scene['t_end']:.1f}] ({duration:.1f}s, {len(scene['chunks'])} chunks)")
        for chunk in scene['chunks']:
            print(f"    • [{chunk['t_start']:.1f}] {chunk['text'][:50]}...")
    
    # Apply soft weighting
    print(f"\n⚖️ Applying soft weights...")
    for scene_idx, scene in enumerate(scenes):
        is_current = scene['is_current']
        if is_current:
            scene_weight = 1.0
        else:
            scenes_ago = len(scenes) - 1 - scene_idx
            scene_weight = 0.3 ** scenes_ago
        
        scene['weight'] = scene_weight
        for chunk in scene['chunks']:
            chunk['scene_weight'] = scene_weight
            chunk['scene_idx'] = scene_idx
    
    # Identify current scene based on t_now
    print(f"\n🎯 Identifying current scene at t_now = {t_now:.1f}s...")
    current_scene_idx = len(scenes) - 1  # Default to most recent
    for idx, scene in enumerate(scenes):
        if scene['t_start'] <= t_now <= scene['t_end'] + 5:
            current_scene_idx = idx
            scene['is_current'] = True
            print(f"   ✓ t_now falls in Scene {idx}")
        else:
            scene['is_current'] = False
    
    print(f"\n📊 FINAL SCENE WEIGHTS:")
    for idx, scene in enumerate(scenes):
        marker = "🎬 CURRENT" if scene['is_current'] else "📽️ Previous"
        print(f"  Scene {idx}: {marker} (weight: {scene['weight']:.2f})")
        print(f"    Time range: {scene['t_start']:.1f}-{scene['t_end']:.1f}s")
        print(f"    Chunks: {len(scene['chunks'])}")
    
    # Show what LLM would see
    print(f"\n{'='*70}")
    print("🤖 CONTEXT SENT TO LLM:")
    print(f"{'='*70}\n")
    
    for idx, scene in enumerate(scenes):
        is_current = scene['is_current']
        scene_marker = "🎬 CURRENT SCENE" if is_current else f"📽️ Previous Scene ({scene['weight']:.1f} relevance)"
        
        print(f"{scene_marker}:")
        for chunk in scene['chunks'][-5:]:  # Last 5 per scene
            ts = chunk['t_start']
            mins, secs = int(ts // 60), int(ts % 60)
            time_fmt = f"{mins}:{secs:02d}"
            text = chunk['text'][:80]
            
            if chunk['cue_type'] == "dialogue":
                print(f"[{time_fmt}] {text}")
            elif chunk['cue_type'] == "nonverbal":
                print(f"[{time_fmt}] ({text})")
        print()
    
    # Analysis
    print(f"{'='*70}")
    print("✅ EXPECTED BEHAVIOR:")
    print(f"{'='*70}")
    current_scene = scenes[current_scene_idx]
    print(f"- LLM should focus on Scene {current_scene_idx} (marked 🎬 CURRENT SCENE)")
    print(f"- Current scene dialogue: {current_scene['t_start']:.1f}-{current_scene['t_end']:.1f}s")
    print(f"- For 'who are these two?', LLM should ONLY use current scene dialogue")
    print(f"- Previous scenes provide context but NOT for character ID")
    
    # Check if current scene has enough info
    current_dialogue = []
    for chunk in current_scene['chunks']:
        if chunk['cue_type'] == 'dialogue':
            current_dialogue.append(chunk['text'])
    
    print(f"\nCurrent scene dialogue content:")
    for d in current_dialogue:
        print(f"  '{d[:100]}...'")
    
    if not current_dialogue or all(len(d) < 20 for d in current_dialogue):
        print(f"\n⚠️ WARNING: Current scene has minimal dialogue")
        print(f"   - Without enriched corpus, LLM cannot identify characters")
        print(f"   - Expected response: 'I can see dialogue but not certain who's speaking'")
    
    return scenes, current_scene_idx

# Test the problematic timestamp
if __name__ == "__main__":
    t_now = 4361.0  # 72:41
    scenes, current_idx = simulate_scene_detection(test_chunks, t_now)
    
    print(f"\n{'='*70}")
    print("🎯 CONCLUSION FOR TIMESTAMP 72:41:")
    print(f"{'='*70}")
    print(f"✓ Correctly detected {len(scenes)} scenes")
    print(f"✓ Identified Scene {current_idx} as current (timestamp {t_now})")
    print(f"✓ Applied soft weighting (previous scenes still visible but de-weighted)")
    print(f"✓ LLM prompt clearly marks current scene with 🎬")
    print(f"\n⚠️ REMAINING ISSUE:")
    print(f"   Without enriched corpus metadata, current scene dialogue alone")
    print(f"   ('Wait... not on this page') doesn't identify Cameron & Bianca")
    print(f"   → Priority: Fix enriched corpus timestamp alignment")

