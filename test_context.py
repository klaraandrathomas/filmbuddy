import json

# Simulate what happens when user asks "Who is that girl?" at timestamp 306 seconds

# 1. Load some sample chunks
with open('corpus/10_things_i_hate_about_you_chunks.jsonl', 'r') as f:
    chunks = [json.loads(line) for line in f if line.strip()]

# 2. Find chunks around t_now = 306 (5 min 6 sec into the film)
t_now = 306
window = 60

print("=" * 80)
print(f"USER QUERY AT TIMESTAMP: {t_now}s ({int(t_now//60)}:{int(t_now%60):02d})")
print("=" * 80)
print()

# Recent chunks (what would be in CURRENT SCENE)
recent = [c for c in chunks if t_now - window <= c['t_end'] <= t_now]
recent.sort(key=lambda x: x['t_start'])

print("📍 CURRENT SCENE CONTEXT (last 60 seconds):")
print("-" * 80)
for chunk in recent[-8:]:
    ts = chunk['t_start']
    mins, secs = int(ts // 60), int(ts % 60)
    cue = chunk.get('cue_type', '')
    text = chunk['text'][:100] + "..." if len(chunk['text']) > 100 else chunk['text']
    print(f"[{mins}:{secs:02d}] [{cue}] {text}")
print()

# Semantic search would return top-k chunks based on query similarity
# For demo, let's just show what the top semantic hits might look like
print("🔍 RELEVANT MOMENTS (from semantic search for 'Who is that girl?'):")
print("-" * 80)
# These would be the top 6 chunks by cosine similarity to the query
# Let's simulate by finding chunks with character-related content
print("1-6. [Various timestamps] Chunks with high semantic similarity to query...")
print("     (These are retrieved by embedding similarity to 'Who is that girl?')")
print()

print("=" * 80)
print("WHAT THE LLM SEES:")
print("=" * 80)
print("""
CURRENT SCENE (what's happening right now):
[4:35] [dialogue] "What group is she in?"
[4:38] [dialogue] "The 'don't even think about it' group."
[4:42] [dialogue] "That's Bianca Stratford."
[4:50] [nonverbal] (SIGHS)
[5:02] [dialogue] "What about Sylvia Plath..."

---

RELEVANT MOMENTS (semantic search results):
1. [4:35] [dialogue] 📍 CURRENT SCENE
   "What group is she in? The 'don't even think about it' group..."

2. [15:07] [dialogue]
   "Bianca can date when she wants to..."

3. [22:15] [dialogue]
   "Hey. How you doin'? I had some great duck last night..."

---

User's question: Who is that girl?
""")

