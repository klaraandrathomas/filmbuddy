# Improved Timestamp Aligner - Implementation Guide

## What Was Implemented

I've created a new **`ImprovedTimestampAligner`** class that eliminates the timestamp duplication problem in the original aligner. This is the **#1 priority fix** from the diagnosis document.

### Files Created

1. **`preprocessing/improved_aligner.py`** - The new aligner implementation
2. **`test_improved_aligner.py`** - Quick test script (no LLM required)
3. **`compare_aligners.py`** - Side-by-side comparison tool
4. **`rebuild_corpus_improved.py`** - Full corpus rebuild script (with LLM)

### Files Modified

1. **`preprocessing/corpus_builder.py`** - Updated to support improved aligner

---

## Key Improvements

### Problem Solved: 33% Timestamp Duplication

**Before (Original Aligner):**
- 26 out of 79 scenes had duplicate timestamp 26:06-26:27
- Multiple other duplicates across the corpus
- Query at 72:41 found NO scene → wrong character identification

**After (Improved Aligner):**
- 0% duplicate timestamps (guaranteed by uniqueness constraint)
- Better coverage with anchor + interpolation approach
- Query at 72:41 should find correct scene (Cameron & Bianca)

### Algorithm Changes

| Feature | Original | Improved |
|---------|----------|----------|
| **Matching** | Fuzzy match any subtitle | Anchor-based sequential |
| **Uniqueness** | ❌ None (causes duplicates) | ✅ Each subtitle used once |
| **Temporal Order** | ❌ Not enforced | ✅ Strictly enforced |
| **Phrase Selection** | First/last lines | Distinctiveness-scored |
| **Interpolation** | Basic proportional | Smart between-anchor |
| **Validation** | ❌ None | ✅ Multi-pass validation |

### How It Works

```
Step 1: Build word frequency index
  → Identify rare vs common words in subtitles

Step 2: Extract distinctive phrases from scenes
  → Score by: length, rarity, proper nouns, generic words
  → "Answer the question, Patrick" scores high
  → "Hey what" scores low

Step 3: Find anchor scenes (sequential, no reuse)
  → Match distinctive phrases with high confidence
  → Track which subtitles are used
  → Enforce temporal ordering (can't go backwards)
  → Result: ~50-70% of scenes become anchors

Step 4: Interpolate non-anchor scenes
  → Find nearest anchors before and after
  → Distribute time evenly between them
  → Result: Complete coverage, no gaps

Step 5: Validate and enforce ordering
  → Check for overlaps
  → Adjust if needed
  → Final pass ensures consistency
```

---

## How to Use

### Option 1: Quick Test (Recommended First Step)

Test the aligner without running the full LLM-based pipeline:

```bash
# Activate virtual environment
source venv/bin/activate

# Run quick test (takes ~30 seconds)
python test_improved_aligner.py
```

**What it tests:**
- ✅ No duplicate timestamps
- ✅ Temporal ordering correct
- ✅ Anchor rate in expected range (50-70%)
- ✅ Scene found at 72:41 (test case)
- ✅ Confidence scores acceptable

**Expected output:**
```
✅ ALL TESTS PASSED!
The improved aligner eliminates duplicate timestamps and provides
better coverage. Ready to rebuild full corpus with LLM enrichment.
```

### Option 2: Compare Aligners

See side-by-side comparison of original vs improved:

```bash
python compare_aligners.py
```

**Shows:**
- Duplicate timestamp reduction
- Anchor vs interpolation breakdown
- Test case results (72:41)
- Confidence score comparison

### Option 3: Rebuild Full Corpus

Once testing confirms the aligner works, rebuild the full enriched corpus:

```bash
# This takes 10-20 minutes (requires Azure OpenAI API)
python rebuild_corpus_improved.py
```

**What it does:**
1. Parses script into scenes
2. Fetches TMDB metadata
3. Extracts character metadata via LLM
4. **Uses improved aligner for timestamps** ⭐
5. Generates scene summaries via LLM
6. Stores in ChromaDB

**Output:**
- `corpus/10_things_i_hate_about_you_1999_enriched.jsonl` (updated)
- `corpus/10_things_i_hate_about_you_1999_metadata.json` (updated)
- ChromaDB updated with new timestamps

---

## Testing the Fix

### Before Testing

The current enriched corpus has broken timestamps:

```bash
# Check current state
python -c "
import json
with open('corpus/10_things_i_hate_about_you_1999_enriched.jsonl', 'r') as f:
    scenes = [json.loads(line) for line in f]

ts_map = {}
for s in scenes:
    key = f\"{s['t_start']:.1f}-{s['t_end']:.1f}\"
    ts_map[key] = ts_map.get(key, []) + [s['scene_id']]

dups = {k:v for k,v in ts_map.items() if len(v) > 1}
print(f'Duplicate timestamps: {len(dups)}')
print(f'Worst offender: 26 scenes at 26:06-26:27')
"
```

### After Rebuilding

1. **Test timestamp quality:**
```bash
python -c "
import json
with open('corpus/10_things_i_hate_about_you_1999_enriched.jsonl', 'r') as f:
    scenes = [json.loads(line) for line in f]

ts_map = {}
for s in scenes:
    key = f\"{s['t_start']:.1f}-{s['t_end']:.1f}\"
    ts_map[key] = ts_map.get(key, []) + [s['scene_id']]

dups = {k:v for k,v in ts_map.items() if len(v) > 1}
print(f'Duplicate timestamps: {len(dups)} (should be 0)')
"
```

2. **Test 72:41 query:**
```bash
# Restart server
uvicorn server.main:app --reload --port 8000

# In browser/Postman, test:
POST http://localhost:8000/ask
{
  "film_id": "10_things_i_hate_about_you",
  "t_now": 4361.0,
  "query": "who are these two?",
  "spoiler_mode": "off"
}
```

**Expected result:**
```json
{
  "answer": "Cameron and Bianca, who are studying French together in the library...",
  "current_scene": {
    "location": "LIBRARY",
    "characters_present": ["CAMERON", "BIANCA"],
    "alignment_confidence": 0.87,
    "alignment_method": "anchor_match"
  }
}
```

### Validation Checklist

After rebuilding:

- [ ] No duplicate timestamps (run validation script)
- [ ] Scene found at 72:41 with Cameron & Bianca
- [ ] 50-70% scenes are anchor matches (high confidence)
- [ ] 30-50% scenes are interpolated (medium confidence)
- [ ] Average confidence >= 0.6
- [ ] All scenes in temporal order (no overlaps)
- [ ] Test query returns correct characters

---

## Configuration Options

The improved aligner has tunable parameters:

```python
aligner = ImprovedTimestampAligner(
    anchor_threshold=0.85,      # Min score for anchor (default: 0.85)
    fuzzy_threshold=0.75,       # Min fuzzy similarity (default: 0.75)
    min_phrase_words=4          # Min words in phrase (default: 4)
)
```

**Tuning guide:**

- **More anchors needed?** Lower `anchor_threshold` to 0.80
- **Too many false matches?** Raise `fuzzy_threshold` to 0.80
- **Short phrases not matching?** Lower `min_phrase_words` to 3

---

## Troubleshooting

### Issue: Low anchor rate (<40%)

**Cause:** Script dialogue doesn't match subtitles well

**Solution:**
1. Lower `anchor_threshold` to 0.80
2. Check if script and subtitle versions match
3. Consider character name anchoring (see alternative approach below)

### Issue: Still finding duplicates

**Cause:** Bug in uniqueness constraint

**Solution:**
1. Check `used_subtitles` set is being populated
2. Verify subtitles aren't being matched twice
3. Review logs from aligner for debugging

### Issue: Test case (72:41) not found

**Cause:** Scene might be interpolated with low confidence

**Solution:**
1. Check if nearby scenes are anchors
2. Verify scene has dialogue in script
3. Try lowering `anchor_threshold`

---

## Alternative: Character Name Anchoring

If the improved aligner still struggles, consider this enhancement:

```python
def find_character_name_anchors(scenes, subtitles, character_list):
    """
    Find scenes where character names are explicitly mentioned.
    Very high confidence matches.
    
    Example:
    Script: Patrick says "Answer the question, Patrick"
    Subtitle at 71:16: "Answer the question, Patrick"
    Match: "Patrick" is in both → Anchor at 71:16
    """
    # Extract dialogue mentioning character names
    # Search for those names in subtitles
    # Much higher precision than generic phrase matching
    pass
```

This could achieve 80-90% anchor rate instead of 50-70%.

---

## Next Steps

1. **Run quick test:** `python test_improved_aligner.py`
2. **Compare with original:** `python compare_aligners.py`
3. **If tests pass, rebuild corpus:** `python rebuild_corpus_improved.py`
4. **Validate results** (see checklist above)
5. **Test 72:41 query** in the extension
6. **If successful, apply to other films** (La La Land, etc.)

---

## Performance Notes

**Test Aligner** (no LLM):
- Runtime: ~30 seconds
- CPU only
- No API costs

**Compare Aligners** (no LLM):
- Runtime: ~1 minute
- CPU only
- No API costs

**Full Corpus Rebuild** (with LLM):
- Runtime: 10-20 minutes
- Requires Azure OpenAI API
- Cost: ~$1-2 for character extraction + summaries
- CPU + API calls

---

## Success Criteria

The improved aligner is working correctly if:

1. ✅ Zero duplicate timestamps
2. ✅ 50-70% anchor matches (high confidence)
3. ✅ Scene found at 72:41 (Cameron & Bianca)
4. ✅ All scenes in temporal order
5. ✅ Average confidence >= 0.6
6. ✅ Test query returns correct answer

Once these criteria are met, the enriched corpus will provide accurate character metadata for deictic queries like "who are these two?"

---

## Questions?

See also:
- `DIAGNOSIS_72_41_ERROR.md` - Root cause analysis
- `TIMESTAMP_ALIGNMENT_ANALYSIS.md` - Deep dive into algorithm
- Code comments in `preprocessing/improved_aligner.py`

