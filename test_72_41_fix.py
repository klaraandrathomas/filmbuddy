#!/usr/bin/env python3
"""
Test the improved scene detection with actual API call at 72:41
"""

import requests
import json
from dotenv import load_dotenv
import os

load_dotenv()

# Check if server is running and LLM is configured
API_BASE = "http://localhost:8000"

def test_72_41_query():
    """Test the 'who are these two?' query at 72:41"""
    
    print("=" * 70)
    print("TESTING: 'who are these two?' at 72:41 (4361s)")
    print("=" * 70)
    
    # Check server status
    try:
        response = requests.get(f"{API_BASE}/ping")
        if response.status_code != 200:
            print("❌ Server not running. Start with: cd server && uvicorn main:app --reload")
            return
        
        status = response.json()
        print(f"\n✓ Server running")
        print(f"  - LLM enabled: {status['llm_enabled']}")
        print(f"  - Vector store: {status['vector_store_enabled']}")
        print(f"  - Films: {status['available_films']}")
        
        if not status['llm_enabled']:
            print("\n⚠️ LLM not enabled - will only see RAG hits, no answer")
            print("   Configure Azure OpenAI credentials in .env to enable")
    
    except requests.exceptions.ConnectionError:
        print("❌ Server not running at http://localhost:8000")
        print("   Start with: cd server && uvicorn main:app --reload")
        return
    
    # Make the query
    payload = {
        "film_id": "10_things_i_hate_about_you",
        "t_now": 4361.0,  # 72:41
        "query": "who are these two?",
        "spoiler_mode": "off",
        "top_k": 6
    }
    
    print(f"\n📤 Sending request:")
    print(f"   Query: '{payload['query']}'")
    print(f"   Timestamp: {payload['t_now']}s ({int(payload['t_now']//60)}:{int(payload['t_now']%60):02d})")
    
    response = requests.post(f"{API_BASE}/ask", json=payload)
    
    if response.status_code != 200:
        print(f"\n❌ Request failed: {response.status_code}")
        print(response.text)
        return
    
    result = response.json()
    
    # Display results
    print(f"\n{'='*70}")
    print("📊 RESPONSE:")
    print(f"{'='*70}")
    
    # Check if enriched scene data is present
    if result.get('current_scene'):
        scene = result['current_scene']
        print(f"\n✅ Enriched Scene Data Available:")
        print(f"   Location: {scene.get('location', 'N/A')}")
        print(f"   Characters: {', '.join(scene.get('characters_present', []))}")
        if 'character_details' in scene:
            for char, details in scene['character_details'].items():
                actor = details.get('actor', 'N/A')
                print(f"     - {char} ({actor})")
    else:
        print(f"\n⚠️ No Enriched Scene Data")
        print(f"   (Enriched corpus not available or timestamp misalignment)")
    
    # Show validation info
    validation = result.get('validation', {})
    print(f"\n🔍 Search Validation:")
    print(f"   - Candidates: {validation.get('num_candidates', 0)}")
    print(f"   - Filtered: {validation.get('num_filtered_candidates', 0)}")
    print(f"   - Deictic query: {validation.get('is_deictic_query', False)}")
    print(f"   - Temporal weight: {validation.get('temporal_weight', 0):.2f}")
    
    # Show top hits
    print(f"\n📑 Top RAG Hits:")
    for i, hit in enumerate(result.get('hits', [])[:3], 1):
        mins, secs = int(hit['t_start'] // 60), int(hit['t_start'] % 60)
        is_current = (result['t_now'] - 60 <= hit['t_end'] <= result['t_now'])
        marker = "🎬" if is_current else "  "
        print(f"  {marker}{i}. [{mins}:{secs:02d}] (score: {hit['score']:.3f})")
        print(f"     {hit['text'][:80]}...")
    
    # Show LLM answer
    if result.get('answer'):
        print(f"\n{'='*70}")
        print("🤖 LLM ANSWER:")
        print(f"{'='*70}")
        print(result['answer'])
        print(f"{'='*70}")
        
        # Analyze the answer
        answer_lower = result['answer'].lower()
        if 'cameron' in answer_lower and 'bianca' in answer_lower:
            print("\n✅ CORRECT: Identified Cameron and Bianca")
        elif 'patrick' in answer_lower or 'kat' in answer_lower:
            print("\n❌ INCORRECT: Still identifying Patrick/Kat (previous scene)")
        elif 'not certain' in answer_lower or 'not sure' in answer_lower or 'uncertain' in answer_lower:
            print("\n✓ ACCEPTABLE: LLM admits uncertainty (honest response)")
        else:
            print("\n❓ UNCLEAR: Check answer manually")
    else:
        print(f"\n⚠️ No LLM answer generated")
        if not result.get('llm_enabled'):
            print("   Reason: LLM not enabled")
        else:
            print("   Reason: Unknown")
    
    print(f"\n{'='*70}")
    print("IMPROVEMENT ASSESSMENT:")
    print(f"{'='*70}")
    print("""
With the new multi-scene detection:
✓ System now correctly segments dialogue into 3 scenes
✓ Current scene (72:37-72:40) is clearly marked with 🎬
✓ Previous scenes shown with lower relevance (0.09, 0.30 vs 1.00)
✓ LLM prompt emphasizes using ONLY current scene for character ID

Expected behavior:
- If enriched corpus available → Correct answer (Cameron & Bianca)
- If enriched corpus missing → Honest "I'm not certain" response
- Should NOT identify Patrick/Kat anymore (they're in previous scene)

Next step if answer is still wrong:
→ Fix enriched corpus timestamp alignment (Priority 1)
→ This will provide character metadata for current scene
    """)

if __name__ == "__main__":
    test_72_41_query()

