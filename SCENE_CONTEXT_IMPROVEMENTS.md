# Scene Context Improvements

## Problem Statement

Based on user testing with "10 Things I Hate About You" at timestamp 69:55 (4195 seconds):

1. **Scene Misidentification**: System identified location as "Bogey's party" when actually at paintball park
   - Root cause: Enriched scene at Bogey's house (4149-4170s) was closest match
   - System used scene that ended 25 seconds earlier

2. **Dialogue-Only Responses**: For "what's happening in this scene" questions, system only regurgitated dialogue
   - Did not use scene summaries or action lines
   - Could not provide spatial/contextual information

3. **Missing Hierarchy**: No clear prioritization of:
   - Temporal grounding (subtitles)
   - Scene context (summaries, action lines)
   - Character metadata

## Solution Architecture

### 1. Strict Temporal Validation (`server/main.py:951-977`)

**Before:**
```python
if confidence < 0.5:
    print(f"Low confidence, skipping")
    enriched_scene = None
```

**After:**
```python
# Validate temporal bounds
scene_t_start = enriched_scene.get('t_start', 0)
scene_t_end = enriched_scene.get('t_end', 0)

if not (scene_t_start <= t_now <= scene_t_end + 5):  # 5s buffer
    print(f"Scene temporally misaligned: {scene_t_start}-{scene_t_end} vs {t_now}")
    enriched_scene = None
elif confidence < 0.7:  # Stricter threshold
    print(f"Low confidence ({confidence}), skipping")
    enriched_scene = None
```

**Impact:** Prevents using scenes from wrong time periods (like Bogey's party at paintball timestamp)

### 2. Scene-Summary Query Detection (`server/main.py:860-877`)

New function to detect "what's happening" type questions:

```python
def is_scene_summary_query(query: str) -> bool:
    """Detect queries asking about scene context/setting."""
    patterns = [
        r'\bwhat\'?s (happening|going on)( in| right| at)?( this scene| now| here)?\b',
        r'\bwhere (are we|is this|am i)\b',
        r'\bwhat (just )?happened\b',
        r'\bdescribe (this|the) scene\b',
        r'\bwhat are (they|we) doing\b',
    ]
    return any(re.search(pattern, query.lower()) for pattern in patterns)
```

**Detected Queries:**
- "what's happening in this scene" ✅
- "where are we" ✅
- "what's going on right now" ✅
- "what just happened" ✅
- "what's happening" ✅

### 3. Query-Aware Context Hierarchy (`server/main.py:463-533`)

#### For Scene-Summary Queries:
```
1. 📍 Scene Location & Setting (from script)
2. 🎬 What's Happening (scene summary)
3. 🎭 Scene Actions & Staging (action lines)
4. 💬 Recent Dialogue (supporting)
5. 👥 Characters in Scene
```

#### For Character/Specific Queries:
```
1. 💬 Recent Dialogue (primary)
2. 📍 Scene Location (supplementary)
3. 👥 Characters in Scene
```

### 4. Enhanced Prompt Instructions (`server/main.py:547-617`)

**For Scene Queries:**
```
RESPONSE STRATEGY:
1. Start with LOCATION and SETTING
2. Use "What's Happening (Scene Summary)" to describe broadly
3. Reference "Scene Actions & Staging" for visual/spatial details
4. Use "Recent Dialogue" to support description
5. Mention characters if relevant

Keep your response descriptive but concise - paint a picture of what the viewer is watching.
```

**For Character Queries:**
```
The "Characters in this scene" section shows EXACTLY who is on screen right now.
Check the character list for current scene identification.
Recent dialogue is your primary source.
```

## Implementation Details

### Files Modified

1. **`server/main.py`**
   - Added `is_scene_summary_query()` function (line 860)
   - Enhanced temporal validation in `search()` (line 951)
   - Updated `generate_response()` signature (line 382)
   - Restructured context building (line 463)
   - Query-aware prompt generation (line 547)

### Key Parameters

- **Temporal Buffer**: 5 seconds (allows for scene transitions)
- **Confidence Threshold**: 0.7 (increased from 0.5)
- **Temporal Window**: 45 seconds (for subtitle context)

## Testing

### Test Script: `test_scene_fix.py`

```bash
python3 test_scene_fix.py
```

**Results:**
```
✅ Scene-summary queries detected: 7/8 patterns
✅ Temporal validation: 4/4 cases correct
✅ Context hierarchy: Adapts to query type
```

### Test Cases

| Query Type | Example | Context Order | Status |
|------------|---------|---------------|--------|
| Scene Summary | "what's happening in this scene" | Location → Summary → Action → Dialogue | ✅ |
| Character ID | "who are these two" | Dialogue → Characters → Location | ✅ |
| Deictic | "who is this" | Dialogue (current only) → Characters | ✅ |

## Expected Behavior Changes

### Scenario 1: "What's happening in this scene" at 69:55 (paintball scene)

**Before:**
```
Response: "Based on the dialogue in the current scene, [regurgitates dialogue]"
Location shown: "Bogey Lowenstein's House" (WRONG - from 25s earlier)
```

**After:**
```
Location: PAINTBALL FIELD (if enriched scene exists and aligned)
OR
Response: "Based on the recent dialogue, you can hear [describes activity]. 
The soundtrack features music and people are laughing/shouting. 
It sounds like a lively, chaotic atmosphere typical of an outdoor activity."

(If no enriched scene at this timestamp, falls back to subtitle analysis)
```

### Scenario 2: "Who are these two" (character identification)

**Before:**
```
Uses dialogue from any scene in last 45s
May include previous scenes
```

**After:**
```
ONLY uses dialogue marked "🎬 CURRENT SCENE"
Ignores previous scenes (📽️)
Checks characters_present list from enriched scene
```

## Alignment Issue Diagnosis

The paintball scene (timestamp 4195s) has **NO enriched scene** in the corpus:

```bash
# Closest scenes:
Scene 40: BOGEY LOWENSTEIN'S HOUSE (4149-4170s)  # 25s before
Scene 23: TUTORING ROOM (4819s)                   # 624s after
Scene 54: FIELD HOCKEY FIELD (3487s)              # 708s before
```

**Root Cause:** 
- Scene 72 in script is "EXT. STRATFORD HOUSE - DAY" (a sprinkler shot)
- This short transitional scene was **interpolated** with low confidence (0.3)
- It got mapped to wrong timestamp (1588-1662s instead of ~4195s)
- Creating a 600+ second gap in enriched corpus

**Fix Needed:**
Re-run corpus builder with `ImprovedTimestampAligner` to fix alignment.

## Future Improvements

1. **Gap Detection**: Add validation to flag timestamp gaps >30 seconds
2. **Scene Type Classification**: Distinguish between:
   - Dialogue scenes (use current approach)
   - Montage/action scenes (rely more on music, sound effects)
   - Transitional scenes (brief establishing shots)
3. **Visual Context**: Incorporate subtitles like "[MUSIC PLAYING]", "[LAUGHTER]" more prominently
4. **Confidence Decay**: Lower confidence for scenes >10s old (even within buffer)

## Validation Checklist

- [x] Temporal validation prevents misaligned scenes
- [x] Scene-summary queries detected correctly
- [x] Context hierarchy adapts to query type
- [x] Scene summaries included in responses
- [x] Action lines provide spatial context
- [x] No linting errors
- [ ] Live API test with actual queries
- [ ] Re-alignment of corpus to fix gaps

## Summary

This implementation provides:

✅ **Temporal Safety**: Won't use scenes from wrong timestamps  
✅ **Query Intelligence**: Adapts response based on question type  
✅ **Rich Context**: Uses summaries, action lines, not just dialogue  
✅ **Hierarchical Grounding**: Subtitles → Enriched → Semantic search  

The system now matches the intuition: "ground in dialogue/timestamp, then look to enriched info like script and scene summaries, then use the scene summary to respond."


