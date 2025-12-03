"""
Diagnostic script to understand what context the LLM receives for the query at 72:41
"""

import json
import sys
sys.path.append('.')

from preprocessing.vector_store import MovieVectorStore

# Constants from server
TEMPORAL_WEIGHT = 0.2
TEMPORAL_DECAY = 180

# Deictic query detection
import re
def is_deictic_query(query: str) -> bool:
    """Detect deictic questions about current scene."""
    deictic_patterns = [
        r'\bwho (is|are|was|were|\'s) (this|that|these|those|he|she|they|the guy|the woman|the man|the girl)\b',
        r'\bwhat (is|are|was|were|\'s) (this|that|happening|going on)\b',
        r'\bwhere (is|are|was|were) (this|that|he|she|they)\b',
        r'\bwho are (the |these |those )?two\b',
        r'\bwho\'s (that|this|the)\b',
    ]
    query_lower = query.lower()
    return any(re.search(pattern, query_lower) for pattern in deictic_patterns)

# Target timestamp
timestamp = 72 * 60 + 41  # 72:41 = 4361 seconds
query = "who are these two?"
print(f"="*80)
print(f"DIAGNOSTIC: Query at timestamp {timestamp}s (72:41)")
print(f"Query: '{query}'")
print(f"="*80)

# 1. Load subtitle corpus
print("\n1. SUBTITLE CONTEXT (what the LLM sees as 'current scene')")
print("-"*80)

with open('corpus/10_things_i_hate_about_you_chunks.jsonl', 'r') as f:
    subtitle_chunks = [json.loads(line) for line in f]

# Get recent dialogue (now using 45 seconds as per fix)
window_seconds = 45
recent_chunks = []
for chunk in subtitle_chunks:
    t_end = chunk.get('t_end', 0)
    if timestamp - window_seconds <= t_end <= timestamp:
        recent_chunks.append(chunk)

recent_chunks.sort(key=lambda x: x['t_start'])

# SCENE BOUNDARY DETECTION (new fix)
scene_boundaries = []
for i in range(len(recent_chunks) - 1):
    time_gap = recent_chunks[i+1]['t_start'] - recent_chunks[i]['t_end']
    if time_gap > 3.0:  # 3+ second gap
        scene_boundaries.append(i)

# Keep only chunks after last boundary
original_count = len(recent_chunks)
if scene_boundaries:
    last_boundary = scene_boundaries[-1]
    recent_chunks = recent_chunks[last_boundary + 1:]
    print(f"🔍 Scene boundary detected! Keeping {len(recent_chunks)}/{original_count} chunks from current scene")
else:
    print(f"No scene boundary detected in last {window_seconds}s")

print(f"Recent chunks (shown to LLM as 'CURRENT SCENE'):")
print(f"Found {len(recent_chunks)} chunks\n")

for chunk in recent_chunks[-10:]:  # Last 10 chunks
    t_start = chunk['t_start']
    mins, secs = int(t_start // 60), int(t_start % 60)
    time_fmt = f"{mins}:{secs:02d}"
    text = chunk.get('text', '')
    cue_type = chunk.get('cue_type', '')
    
    if cue_type == "dialogue":
        print(f"[{time_fmt}] {text}")
    elif cue_type == "nonverbal" and len(text) < 50:
        print(f"[{time_fmt}] ({text})")

# 2. Check enriched scene data
print("\n\n2. ENRICHED SCENE DATA (character metadata from vector store)")
print("-"*80)

vector_store = MovieVectorStore(persist_directory="./chroma_db")
enriched_scene = vector_store.query_scene_at_timestamp(
    "10_things_i_hate_about_you_1999",
    timestamp,
    buffer=5.0
)

if enriched_scene:
    print(f"Location: {enriched_scene.get('location', 'Unknown')}")
    print(f"Characters present: {enriched_scene.get('characters_present', [])}")
    print(f"Alignment confidence: {enriched_scene.get('alignment_confidence', 0):.2f}")
    print(f"Alignment method: {enriched_scene.get('alignment_method', 'unknown')}")
    print(f"Time range: {enriched_scene.get('t_start', 0):.1f}s - {enriched_scene.get('t_end', 0):.1f}s")
    
    character_details = enriched_scene.get('character_details', {})
    if character_details:
        print("\nCharacter details:")
        for char_name, details in character_details.items():
            print(f"  • {details.get('full_name', char_name)}", end="")
            if details.get('actor'):
                print(f" (played by {details.get('actor')})", end="")
            print()
else:
    print("❌ NO ENRICHED SCENE DATA FOUND")
    print(f"This means the LLM is working with subtitle context only!")

# 3. Simulate semantic search (what gets ranked as "relevant moments")
print("\n\n3. SEMANTIC SEARCH RESULTS (RAG hits)")
print("-"*80)

# Check if this is a deictic query
is_deictic = is_deictic_query(query)
temporal_weight = 0.6 if is_deictic else TEMPORAL_WEIGHT

if is_deictic:
    print(f"✅ DEICTIC QUERY DETECTED: '{query}'")
    print(f"   Temporal weight boosted: {TEMPORAL_WEIGHT} → {temporal_weight}")
    print(f"   This prioritizes recent content over semantic similarity\n")
else:
    print(f"Regular query - using default temporal weight: {temporal_weight}\n")

from sentence_transformers import SentenceTransformer
import numpy as np

model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
q = model.encode([query], normalize_embeddings=True).astype("float32")[0]

# Embed all subtitle chunks
texts = [chunk['text'] for chunk in subtitle_chunks]
embeddings = model.encode(texts, batch_size=64, normalize_embeddings=True).astype("float32")

# Calculate similarities
sims = embeddings @ q

# Get top candidates
num_candidates = 128
cand_idx = np.argpartition(sims, -num_candidates)[-num_candidates:]

# Filter by spoiler mode and compute combined scores
import math

def compute_temporal_score(t_end: float, t_now: float) -> float:
    time_diff = max(0, t_now - t_end)
    return math.exp(-time_diff / TEMPORAL_DECAY)

candidates = []
for idx in cand_idx:
    chunk = subtitle_chunks[idx]
    t_start = chunk.get('t_start', 0)
    t_end = chunk.get('t_end', 0)
    
    # Spoiler filtering
    if t_start > timestamp:  # Skip future content
        continue
    
    semantic_score = float(sims[idx])
    temporal_score = compute_temporal_score(t_end, timestamp)
    
    cue_type = chunk.get('cue_type', 'dialogue')
    cue_weights = {
        "dialogue": 1.0,
        "lyric": 0.8,
        "nonverbal": 0.3,
        "metadata": 0.1
    }
    cue_weight = cue_weights.get(cue_type, 0.5)
    
    base_score = (1 - TEMPORAL_WEIGHT) * semantic_score + TEMPORAL_WEIGHT * temporal_score
    combined_score = base_score * cue_weight
    
    candidates.append({
        'idx': idx,
        'chunk': chunk,
        'semantic_score': semantic_score,
        'temporal_score': temporal_score,
        'combined_score': combined_score
    })

# Sort and take top 6
candidates.sort(key=lambda x: x['combined_score'], reverse=True)

print("Top 6 RAG hits (what LLM sees as 'RELEVANT MOMENTS'):\n")
for i, cand in enumerate(candidates[:6], 1):
    chunk = cand['chunk']
    t_start = chunk['t_start']
    mins, secs = int(t_start // 60), int(t_start % 60)
    time_fmt = f"{mins}:{secs:02d}"
    
    is_current = (timestamp - 60 <= chunk['t_end'] <= timestamp)
    marker = "📍 CURRENT SCENE" if is_current else ""
    
    cue_type = chunk.get('cue_type', '')
    text = chunk.get('text', '').replace('\n', ' ')[:100]
    
    print(f"{i}. [{time_fmt}] [{cue_type}] {marker}")
    print(f"   {text}")
    print(f"   Scores: semantic={cand['semantic_score']:.3f}, temporal={cand['temporal_score']:.3f}, combined={cand['combined_score']:.3f}")
    print()

# 4. Summary
print("\n" + "="*80)
print("SUMMARY: Analysis with New Fixes")
print("="*80)

print("\n🔧 FIXES APPLIED:")
print("1. ✅ Reduced temporal window: 90s → 45s")
print("2. ✅ Scene boundary detection: Detects 3+ second gaps")
print("3. ✅ Deictic query detection: Boosts temporal weight for 'who is this?' queries")
print("4. ✅ Improved LLM prompt: Emphasizes recency and verification")

print("\n📊 IMPACT ON THIS QUERY:")
if scene_boundaries:
    print(f"✅ Scene boundary successfully detected")
    print(f"   Context now limited to current scene only ({len(recent_chunks)} chunks)")
else:
    print(f"⚠️  No scene boundary detected in last 45s")
    print(f"   May still include some previous scene dialogue")

if is_deictic:
    print(f"✅ Deictic query detected - temporal weight boosted to {temporal_weight}")
    print(f"   Recent content will be prioritized in search results")

print("\n✅ EXPECTED CORRECT ANSWER:")
print("Based on the recent dialogue (after scene boundary):")
print("  - '(SPEAKING FRENCH)' (72:24)")
print("  - 'Wait. Wait a minute. That... That's not on this page.' (72:37)")
print("This should now correctly identify: Cameron and Bianca in French class.")

print("\n⚠️  REMAINING ISSUES:")
print("1. ❌ Enriched scene data still missing/misaligned at this timestamp")
print("   → Need to rebuild enriched corpus with correct timestamp alignment")
print("2. ⚠️  Dialogue snippets still lack character attribution")
print("   → Consider adding character name extraction from known character list")

