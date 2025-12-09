"""
Diagnostic tool to understand why searches return 0 hits
"""

from fastapi.testclient import TestClient
from server.main import app
import json

def diagnose_query(film_id, t_now, query):
    """Diagnose a specific query."""
    print(f"\n{'='*60}")
    print(f"Diagnosing: '{query}' at {t_now}s")
    print(f"{'='*60}")
    
    with TestClient(app) as client:
        response = client.post("/ask", json={
            "film_id": film_id,
            "t_now": t_now,
            "query": query,
            "spoiler_mode": "off",
            "top_k": 10
        })
        
        if response.status_code == 200:
            data = response.json()
            
            print(f"\n✓ Status: {response.status_code}")
            print(f"✓ Hits returned: {len(data['hits'])}")
            
            if data['hits']:
                print(f"\nTop 3 hits:")
                for i, hit in enumerate(data['hits'][:3], 1):
                    print(f"\n  {i}. Score: {hit['score']:.4f}")
                    print(f"     Time: {hit['t_start']:.1f}s - {hit['t_end']:.1f}s")
                    print(f"     Type: {hit['cue_type']}")
                    print(f"     Text: {hit['text'][:80]}...")
            else:
                print("\n⚠️  No hits found!")
                print(f"\nPossible reasons:")
                print(f"  1. Query doesn't semantically match subtitle text")
                print(f"  2. Spoiler filter removed all results (t_end > t_now)")
                print(f"  3. Semantic similarity scores too low")
                
            # Check enriched scene
            current_scene = data.get('current_scene')
            if current_scene:
                print(f"\n✓ Enriched scene available:")
                print(f"  Location: {current_scene.get('location')}")
                print(f"  Characters: {', '.join(current_scene.get('characters_present', []))}")
            else:
                print(f"\n⚠️  No enriched scene data")
                
            # Check validation info
            validation = data.get('validation', {})
            print(f"\nValidation info:")
            print(f"  Candidates checked: {validation.get('num_candidates')}")
            print(f"  After filtering: {validation.get('num_filtered_candidates')}")
            print(f"  Final hits: {validation.get('num_hits')}")
            print(f"  Spoiler gate: {validation.get('time_gate_enforced')}")
            
        else:
            print(f"✗ Error: {response.status_code}")
            print(f"  {response.json()}")


def main():
    print("\n" + "="*70)
    print("Search Diagnostic Tool")
    print("="*70)
    
    # Test cases that had issues
    test_cases = [
        ("la_la_land", 50.0, "Who is in this scene?"),
        ("la_la_land", 50.0, "What's happening?"),  # Try different query
        ("la_la_land", 200.0, "Who's that guy?"),
        ("la_la_land", 500.0, "Where are they?"),
    ]
    
    for film_id, t_now, query in test_cases:
        diagnose_query(film_id, t_now, query)
    
    print("\n" + "="*70)
    print("Diagnostic Summary")
    print("="*70)
    print("""
If searches return 0 hits:

1. Check semantic matching:
   - Query may not match subtitle text well
   - Try more specific queries about dialogue/events
   
2. Check spoiler filtering:
   - With spoiler_mode="off", only returns t_end <= t_now
   - May filter out most results early in film
   
3. Check corpus:
   - Ensure subtitle corpus has data at that timestamp
   - Check that embeddings were generated correctly

If enriched scene data missing:
   - Ensure enriched corpus in vector store
   - Check film ID mapping (e.g., la_la_land → la_la_land_2016)
""")


if __name__ == "__main__":
    main()


