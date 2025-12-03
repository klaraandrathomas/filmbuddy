# Diagnosis: Character Misidentification at 72:41

## The Problem

**User Query:** "who are these two?" at timestamp 72:41

**System Response:** "Kat Stratford (Julia Stiles) and Patrick Verona (Heath Ledger) talking about prom"

**Actual Scene:** Cameron and Bianca flirting in French class at the library

## Step-by-Step: How the LLM Got It Wrong

### 1. Context Assembly (What Data the LLM Received)

The server constructs context in this order:

#### A) **Recent Dialogue (90-second window before 72:41)**

The system retrieves ALL dialogue from 70:51 - 72:41 (90 seconds). This includes:

```
[70:56] - Tell me something true.
- Something true. I hate peas. No. Something real.
Something no one else knows. Okay. You're sweet, and sexy,
[71:14] ((KISSES NECK))
[71:16] And completely hot for me. You are amazingly self-assured.
Has anyone ever told you that? I tell myself that every day, actually. - Go to the prom with me.
- Is that a request or a command? Come on. Go with me. - No.
- No? Why not? Because I don't want to.
Because it's a stupid tradition. Come on.
People won't expect you to go. Why are you pushing this? What's in it for you? Oh. So now I need to have a motive
to want to be with you? You tell me. You need therapy, you know that? Has anyone ever told you that? - Answer the question, Patrick.
- Nothing! There is nothing in it for me, just the pleasure of your company.
Okay?
[72:13] ((SCOFFS))
[72:24] ((SPEAKING FRENCH))
[72:37] Wait. Wait a minute.
That... That's not on this page. ⭐ ACTUAL CURRENT MOMENT
```

**Problem:** The Patrick/Kat prom scene (70:56-72:13) is 77 seconds of dense romantic dialogue with character names mentioned ("Patrick"). The Cameron/Bianca scene (72:37-72:41) is only 4 seconds of vague dialogue with no character names.

#### B) **Enriched Scene Data (Character Metadata)**

```
❌ NO ENRICHED SCENE DATA FOUND
```

The enriched corpus has timestamp alignment issues - most scenes have incorrect timestamps like "26:06 - 26:27" repeated across multiple different scenes. At timestamp 72:41, there is NO enriched scene data available.

**Problem:** Without enriched character metadata, the LLM has no way to know which characters are in the current scene.

#### C) **Semantic Search Results (RAG Hits)**

Top 6 semantic matches for "who are these two?":

1. [12:22] "Yeah, whoo!" (score: 0.194)
2. [47:41] "Whoo!" (score: 0.178)
3. [66:59] "The... Think about it. Um, they're looking left..." (score: 0.175)
4. [3:37] "Hello! Michael Eckman. I'm supposed to show you around..." (score: 0.174)
5. [60:35] "(SINGING) I'm not the sort of person..." (score: 0.173)
6. [42:12] "Oh. Must be Nigel with the Brie." (score: 0.167)

**Problem:** None of these are relevant. The semantic search finds random dialogue snippets that don't help identify characters.

### 2. LLM Reasoning Process

Given this context, the LLM:

1. **Looks at the "Current Scene"** section → Sees 90% of it is Patrick/Kat prom conversation
2. **Sees the name "Patrick" explicitly mentioned** in the dialogue
3. **Recognizes romantic context** (kissing, prom invitation, intimacy)
4. **Finds no enriched character data** to verify who's in the scene at 72:41
5. **Makes logical inference:** "The user is asking about the two people in this romantic conversation → Must be Patrick and Kat"
6. **Overlooks the tiny snippet at 72:37-72:41** because it's:
   - Only 4 seconds vs 77 seconds of Patrick/Kat dialogue
   - Has no character names
   - Has no obvious context clues

### 3. Why the Answer Was Wrong

**Scene Boundary Problem:** The 90-second window spans TWO different scenes:
- **70:56 - 72:13:** Patrick & Kat having an intimate conversation outside (prom invitation scene)
- **72:24 - 72:41:** Cameron & Bianca flirting in French class at the library (completely different scene)

The LLM weighted the longer, more dialogue-rich scene as "current" instead of the actual moment at 72:41.

## Root Causes

### 1. **Enriched Corpus Timestamp Misalignment** (Critical)
- The enriched corpus has broken timestamps
- Many scenes show duplicate times (26:06-26:27 for 20+ different scenes)
- No enriched data available at 72:41
- This is the PRIMARY blocker for accurate character identification

### 2. **Temporal Context Window Too Large** (Major)
- 90-second window is too broad for scene changes
- Includes dialogue from previous scene that dominates the context
- No scene boundary detection

### 3. **No Character Attribution in Subtitles** (Major)
- Subtitles lack speaker labels (e.g., "CAMERON:", "BIANCA:")
- LLM must infer characters from context alone
- When context is mixed (multiple scenes), inference fails

### 4. **Semantic Search Retrieves Irrelevant Content** (Moderate)
- Query "who are these two?" is too vague for semantic matching
- Retrieves random short snippets that happen to match linguistically
- RAG hits don't help with character identification

### 5. **No Verification Step** (Moderate)
- LLM doesn't verify that enriched metadata matches subtitle timestamps
- No sanity check: "Does this scene description match the dialogue I'm seeing?"

## Recommended Fixes (Priority Order)

### 🔴 Priority 1: Fix Enriched Corpus Timestamp Alignment

**Problem:** The enriched corpus has completely broken timestamps.

**Solution:**
```python
# In preprocessing/timestamp_aligner.py or corpus_builder.py
# Need to properly align script scenes to subtitle timestamps

# Current approach is failing. Try:
1. Use dialogue matching: Find script dialogue that matches subtitle text
2. Use character mentions: When subtitles mention a character name, use that as anchor
3. Build scene index: Map script scenes to subtitle time ranges
4. Validate: Ensure each scene has unique, non-overlapping timestamps
```

**Action:** Rebuild the enriched corpus with correct timestamp alignment.

### 🟡 Priority 2: Implement Smart Temporal Context

**Problem:** 90-second window spans multiple scenes.

**Solution:**
```python
# In server/main.py → get_temporal_context()

def get_temporal_context(film_id: str, t_now: float, window_seconds: float = 60):
    """
    Enhanced version that detects scene boundaries.
    """
    chunks = get_chunks_in_window(film_id, t_now - window_seconds, t_now)
    
    # Detect scene breaks (large time gaps or scene change indicators)
    scene_boundaries = []
    for i in range(len(chunks) - 1):
        time_gap = chunks[i+1]['t_start'] - chunks[i]['t_end']
        if time_gap > 5.0:  # 5+ second gap indicates scene change
            scene_boundaries.append(i)
    
    # If scene change detected, only use chunks AFTER the last break
    if scene_boundaries:
        last_boundary = scene_boundaries[-1]
        chunks = chunks[last_boundary + 1:]
    
    return chunks  # Now only includes current scene
```

**Alternative:** Reduce window to 30-45 seconds to minimize cross-scene contamination.

### 🟡 Priority 3: Add Character Name Extraction to Subtitles

**Problem:** Subtitles don't have speaker labels.

**Solution:**
```python
# In preprocessing/character_extractor.py or corpus_builder.py

def extract_character_mentions(subtitle_text: str, known_characters: list) -> list:
    """
    Detect when character names are mentioned in dialogue.
    Example: "Answer the question, Patrick." → Patrick is present
    """
    mentioned = []
    for char in known_characters:
        if char.lower() in subtitle_text.lower():
            mentioned.append(char)
    return mentioned

# Add to each subtitle chunk:
chunk['mentioned_characters'] = extract_character_mentions(chunk['text'], all_characters)
```

**Enhancement:** Use NER (Named Entity Recognition) to find character names even if they're not in the known character list.

### 🟢 Priority 4: Add Verification/Grounding Step

**Problem:** LLM doesn't verify its answer against subtitle evidence.

**Solution:**
```python
# In server/main.py → generate_response()

# Add to system prompt:
"""
VERIFICATION REQUIREMENT:
Before answering character identification questions ("who is X?"):
1. Look at the MOST RECENT dialogue (last 10 seconds)
2. Check if character names are mentioned in that dialogue
3. Look for contextual clues (location, actions, topics)
4. If enriched data is available, verify it matches the subtitle dialogue
5. If you cannot confidently identify characters from RECENT dialogue, say:
   "I can see dialogue but I'm not certain who's speaking. The conversation includes..."

DO NOT identify characters based solely on dialogue from 60+ seconds ago.
"""
```

### 🟢 Priority 5: Improve Deictic Query Handling

**Problem:** "who are these two?" retrieves semantically irrelevant content.

**Solution:**
```python
# In server/main.py → search()

def is_deictic_query(query: str) -> bool:
    """Detect questions about current scene (who/what/where is this?)"""
    deictic_patterns = [
        r'\bwho (is|are) (this|that|these|those|he|she|they)\b',
        r'\bwhat (is|are) (this|that|these|those)\b',
        r'\bwhere (is|are) (this|that)\b',
    ]
    import re
    return any(re.search(pattern, query.lower()) for pattern in deictic_patterns)

# In search():
if is_deictic_query(query):
    # For deictic queries, prioritize temporal over semantic
    TEMPORAL_WEIGHT = 0.8  # Much higher weight on recent content
    # Also reduce search window to last 30 seconds only
```

## Testing Plan

### Test Cases to Add

```python
# test_character_identification.py

def test_scene_boundary_detection():
    """Ensure context doesn't span multiple scenes"""
    # Query at 72:41 should only get 72:24-72:41 context, not 70:56-72:41
    
def test_deictic_queries():
    """Test 'who is this' type questions"""
    test_cases = [
        (4361, "who are these two?", ["Cameron", "Bianca"]),
        (3850, "who is this guy?", ["Patrick"]),
    ]
    
def test_character_verification():
    """Ensure LLM grounds answers in recent dialogue"""
    # Answer should cite specific dialogue/timestamps
    # Should say "I'm not sure" if evidence is ambiguous
```

## Summary: The Chain of Failures

```
User Query: "who are these two?" at 72:41 (Cameron & Bianca in French class)
    ↓
❌ Enriched corpus has NO data at this timestamp (alignment broken)
    ↓
❌ System fetches 90-second window (70:51 - 72:41)
    ↓
❌ Window includes PREVIOUS scene (Patrick & Kat, 70:56-72:13) - 77 seconds
❌ Window includes CURRENT scene (Cameron & Bianca, 72:37-72:41) - 4 seconds
    ↓
❌ Patrick/Kat dialogue dominates context (95% of text, mentions "Patrick" by name)
    ↓
❌ Semantic search retrieves irrelevant content (no character info)
    ↓
❌ LLM has no character metadata for current scene
    ↓
❌ LLM infers from dominant context: "Must be Patrick and Kat"
    ↓
❌ Wrong answer: "Patrick and Kat talking about prom"
```

## Immediate Action Items

1. **Fix enriched corpus timestamp alignment** (run corpus builder with improved aligner)
2. **Reduce temporal context window** from 90s → 45s (quick config change)
3. **Add scene boundary detection** (moderate coding effort)
4. **Add verification prompt** to LLM system instructions (quick prompt change)
5. **Test with known failure cases** (this 72:41 query, others user mentioned)

## Expected Impact

After implementing Priority 1-3 fixes:
- ✅ Enriched corpus provides accurate character metadata at 72:41
- ✅ Temporal context limited to current scene only (72:24-72:41)
- ✅ LLM sees: "BIANCA and CAMERON in LIBRARY, speaking French"
- ✅ Correct answer: "Cameron and Bianca in French class"

## Notes for User

Your intuition is exactly right:
> "it should be grounded in the dialogue/timestamp, then look to enriched info like script and scene summaries, then verify that the script and scene its pulling info from matches the characteristics of the subtitles/dialogue"

The current implementation tries to do this, but fails because:
1. Enriched info is missing/misaligned (biggest issue)
2. Temporal grounding is too broad (includes previous scene)
3. No verification step (LLM doesn't sanity-check its answer)

Fixing these three things will dramatically improve character identification accuracy.

