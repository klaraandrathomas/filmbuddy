# FilmBuddy Enriched Corpus Implementation Guide

## Overview

This guide outlines the implementation of an enriched preprocessing pipeline that combines movie scripts with TMDB API data to create scene-aware, character-rich corpus chunks. The goal is to enable the FilmBuddy agent to answer vague deictic questions like "who's that guy?" by knowing which characters are present in the current scene.

---

## Current State Summary

### What Already Works

| Component | Location | Functionality |
|-----------|----------|---------------|
| **Subtitle Parser** | `scripts/build_time_aware_corpus.py` | Parses SRT files into timestamped chunks with cue type classification (dialogue/lyric/nonverbal), speaker extraction, and merging |
| **Backend API** | `server/main.py` | FastAPI server with semantic search, temporal boosting, LLM response generation via OpenAI |
| **Browser Extension** | `extension/` | Chrome side panel that gets video timestamp and queries the backend |
| **Corpus Files** | `corpus/*.jsonl` | Timestamped chunks for "La La Land" and "10 Things I Hate About You" |

### Current Limitations

1. **No scene structure** - Only subtitles, no scene headers (INT./EXT.)
2. **No character metadata** - Don't know who's in each scene, their gender, role, or relationships
3. **No TMDB integration** - No cast info, no actor→character mapping
4. **Can't answer deictic questions** - "Who's that guy?" fails because agent lacks spatial context

### Target Architecture

```
Movie Script (.txt) ─┬─→ ScriptParser ─→ Scenes with headers, locations, characters
                     │
TMDB API ────────────┼─→ TMDBClient ─→ Cast, character metadata, runtime
                     │
Subtitles (.srt) ────┼─→ TimestampAligner ─→ Aligned scenes with timestamps
                     │
Claude API ──────────┴─→ CharacterExtractor ─→ Character metadata, scene summaries
                     │
                     ▼
              MovieCorpusBuilder ─→ Enriched corpus ─→ ChromaDB
```

---

## Step 1: Environment Setup & Dependencies

### Files to Create/Modify
- `preprocessing/__init__.py`
- `requirements.txt` (update)
- `.env` (create template)

### Implementation Details

```bash
# Create preprocessing directory structure
mkdir -p preprocessing
touch preprocessing/__init__.py
touch preprocessing/tmdb_client.py
touch preprocessing/script_parser.py
touch preprocessing/character_extractor.py
touch preprocessing/timestamp_aligner.py
touch preprocessing/corpus_builder.py
touch preprocessing/vector_store.py
```

### Dependencies to Add

```
# Add to requirements.txt
requests>=2.31.0         # TMDB API calls
chromadb>=0.4.0          # Vector database
aiofiles>=23.0.0         # Async file operations
python-multipart>=0.0.6  # File uploads
rapidfuzz>=3.0.0         # Fuzzy string matching for alignment
# Note: openai package already in requirements.txt (used with LiteLLM)
```

### Environment Variables Template

```bash
# .env.template
TMDB_API_KEY=your_tmdb_key_here

# LiteLLM configuration (already in use)
LITELLM_API_KEY=your_litellm_key_here
LITELLM_API_BASE=your_litellm_base_url

# Optional: Model selection (defaults to "gpt-4o" if not set)
# FILMBUDDY_LLM_MODEL=claude-3-5-sonnet-20241022
```

### Acceptance Criteria
- [ ] All new packages install successfully
- [ ] Preprocessing directory structure exists
- [ ] `.env.template` created with all required keys
- [ ] Import statements work: `from preprocessing import TMDBClient`

---

## Step 2: TMDB Client

### File to Create
`preprocessing/tmdb_client.py`

### Class: `TMDBClient`

#### Purpose
Fetch movie metadata from TMDB including cast, runtime, and character-to-actor mapping.

#### Methods

```python
class TMDBClient:
    """Client for The Movie Database (TMDB) API."""
    
    def __init__(self, api_key: str = None):
        """Initialize with API key from env or parameter."""
        pass
    
    async def search_movie(self, title: str, year: int = None) -> dict:
        """
        Search for a movie by title and optional year.
        
        Args:
            title: Movie title (e.g., "La La Land")
            year: Release year for disambiguation (e.g., 2016)
        
        Returns:
            dict with keys: id, title, release_date, overview, poster_path
        """
        pass
    
    async def get_movie_details(self, movie_id: int) -> dict:
        """
        Get full movie details including runtime.
        
        Args:
            movie_id: TMDB movie ID
        
        Returns:
            dict with keys: id, title, runtime, release_date, genres, overview
        """
        pass
    
    async def get_cast(self, movie_id: int, limit: int = 20) -> list[dict]:
        """
        Get top billed cast members.
        
        Args:
            movie_id: TMDB movie ID
            limit: Max number of cast members to return
        
        Returns:
            list of dicts with keys: actor_name, character_name, order, gender, profile_path
        """
        pass
    
    async def get_movie_metadata(self, title: str, year: int = None) -> dict:
        """
        Convenience method to get all movie data in one call.
        
        Returns:
            dict with keys:
                - movie_id: int
                - title: str
                - runtime_seconds: int
                - release_year: int
                - characters: list[dict] with actor_name, character_name, gender
        """
        pass
```

#### Data Model

```python
@dataclass
class TMDBCharacter:
    character_name: str      # e.g., "Mia Dolan"
    actor_name: str          # e.g., "Emma Stone"
    gender: str              # "female" | "male" | "unknown"
    billing_order: int       # 0 = lead, higher = smaller role
    profile_image_url: str   # Optional headshot URL
```

### Test Script

```python
# test_tmdb.py
import asyncio
from preprocessing.tmdb_client import TMDBClient

async def test_tmdb():
    client = TMDBClient()
    
    # Test 1: Search for movie
    result = await client.search_movie("La La Land", 2016)
    assert result["title"] == "La La Land"
    print(f"✓ Found movie: {result['title']} (ID: {result['id']})")
    
    # Test 2: Get cast
    metadata = await client.get_movie_metadata("La La Land", 2016)
    assert "Mia" in str(metadata["characters"])
    print(f"✓ Found {len(metadata['characters'])} characters")
    
    # Test 3: Verify character data structure
    mia = next((c for c in metadata["characters"] if "Mia" in c["character_name"]), None)
    assert mia is not None
    assert mia["actor_name"] == "Emma Stone"
    assert mia["gender"] == "female"
    print(f"✓ Mia Dolan played by {mia['actor_name']}")
    
    print("\n✅ All TMDB tests passed!")

if __name__ == "__main__":
    asyncio.run(test_tmdb())
```

### Acceptance Criteria
- [ ] Can search for any movie by title
- [ ] Returns correct runtime in seconds
- [ ] Returns at least top 10 cast members with character names
- [ ] Gender is extracted correctly (TMDB uses 1=female, 2=male, 0=unknown)
- [ ] Handles movies not found gracefully (returns None or raises clear error)

---

## Step 3: Script Parser

### File to Create
`preprocessing/script_parser.py`

### Class: `ScriptParser`

#### Purpose
Parse movie screenplay files into structured scenes with headers, locations, characters, dialogue, and action lines.

#### Input Format (Standard Screenplay)
```
INT. COFFEE SHOP - DAY

MIA enters, looking harried. She's late for her shift.

                         MIA
          Sorry I'm late. Traffic was insane.

                         MANAGER
          This is the third time this week.
```

#### Methods

```python
class ScriptParser:
    """Parser for standard screenplay format."""
    
    def parse_script(self, script_text: str) -> list[dict]:
        """
        Parse screenplay text into structured scenes.
        
        Args:
            script_text: Full screenplay as string
        
        Returns:
            list of scene dicts with keys:
                - scene_id: int (1-indexed)
                - scene_header: str (e.g., "INT. COFFEE SHOP - DAY")
                - location: str (e.g., "COFFEE SHOP")
                - time_of_day: str (e.g., "DAY", "NIGHT", "CONTINUOUS")
                - int_ext: str ("INT" | "EXT" | "INT/EXT")
                - characters: list[str] (e.g., ["MIA", "MANAGER"])
                - dialogue: list[dict] with character, text, parenthetical
                - action_lines: list[str]
                - raw_text: str (original scene text)
        """
        pass
    
    def _is_scene_header(self, line: str) -> bool:
        """
        Detect if line is a scene header.
        
        Scene headers typically start with:
        - INT. / EXT. / INT./EXT.
        - I/E. (shorthand)
        
        Examples:
        - "INT. COFFEE SHOP - DAY"
        - "EXT. BEACH - SUNSET"
        - "INT./EXT. CAR - MOVING - NIGHT"
        """
        pass
    
    def _extract_location(self, header: str) -> str:
        """
        Extract location from scene header.
        
        "INT. COFFEE SHOP - DAY" → "COFFEE SHOP"
        "EXT. LOS ANGELES SKYLINE - NIGHT" → "LOS ANGELES SKYLINE"
        """
        pass
    
    def _extract_time_of_day(self, header: str) -> str:
        """
        Extract time of day from scene header.
        
        Returns: "DAY", "NIGHT", "DUSK", "DAWN", "CONTINUOUS", "LATER", "SAME", or None
        """
        pass
    
    def _is_character_name(self, line: str) -> bool:
        """
        Detect if line is a character name (dialogue cue).
        
        Character names are:
        - ALL CAPS
        - Centered (significant leading whitespace)
        - May have extensions: (V.O.), (O.S.), (CONT'D)
        
        Examples:
        - "          MIA"
        - "          SEBASTIAN (V.O.)"
        - "          MIA (CONT'D)"
        """
        pass
    
    def _clean_character_name(self, line: str) -> str:
        """
        Clean character name by removing extensions.
        
        "MIA (V.O.)" → "MIA"
        "SEBASTIAN (CONT'D)" → "SEBASTIAN"
        """
        pass
    
    def _is_parenthetical(self, line: str) -> bool:
        """
        Detect parenthetical direction.
        
        Parentheticals are in parentheses and describe how to deliver:
        - "(softly)"
        - "(to Sebastian)"
        - "(laughing)"
        """
        pass
    
    def _is_action_line(self, line: str) -> bool:
        """
        Detect action/description lines.
        
        Action lines:
        - Left-aligned (no leading whitespace)
        - Not all caps (unless shouting)
        - Describe what we SEE
        """
        pass
```

#### Output Format

```python
{
    "scene_id": 1,
    "scene_header": "INT. COFFEE SHOP - DAY",
    "location": "COFFEE SHOP",
    "time_of_day": "DAY",
    "int_ext": "INT",
    "characters": ["MIA", "MANAGER", "CUSTOMER"],
    "dialogue": [
        {
            "character": "MIA",
            "text": "Sorry I'm late. Traffic was insane.",
            "parenthetical": None
        },
        {
            "character": "MANAGER",
            "text": "This is the third time this week.",
            "parenthetical": None
        }
    ],
    "action_lines": [
        "MIA enters, looking harried. She's late for her shift.",
        "The MANAGER crosses his arms."
    ],
    "raw_text": "INT. COFFEE SHOP - DAY\n\nMIA enters..."
}
```

### Test Script

```python
# test_script_parser.py
from preprocessing.script_parser import ScriptParser

SAMPLE_SCRIPT = """
INT. COFFEE SHOP - DAY

MIA enters, looking harried. She's late for her shift.

                         MIA
          Sorry I'm late. Traffic was insane.

                         MANAGER
          This is the third time this week.

EXT. BEACH - SUNSET

Sebastian walks along the shore, lost in thought.

                         SEBASTIAN (V.O.)
          I never thought I'd end up here.
"""

def test_parser():
    parser = ScriptParser()
    scenes = parser.parse_script(SAMPLE_SCRIPT)
    
    # Test 1: Correct number of scenes
    assert len(scenes) == 2, f"Expected 2 scenes, got {len(scenes)}"
    print(f"✓ Found {len(scenes)} scenes")
    
    # Test 2: Scene header parsing
    assert scenes[0]["location"] == "COFFEE SHOP"
    assert scenes[0]["time_of_day"] == "DAY"
    assert scenes[0]["int_ext"] == "INT"
    print(f"✓ Scene 1: {scenes[0]['location']} ({scenes[0]['int_ext']})")
    
    # Test 3: Character extraction
    assert "MIA" in scenes[0]["characters"]
    assert "MANAGER" in scenes[0]["characters"]
    print(f"✓ Scene 1 characters: {scenes[0]['characters']}")
    
    # Test 4: Dialogue parsing
    assert len(scenes[0]["dialogue"]) == 2
    assert scenes[0]["dialogue"][0]["character"] == "MIA"
    print(f"✓ Scene 1 has {len(scenes[0]['dialogue'])} dialogue lines")
    
    # Test 5: V.O. handling
    assert "SEBASTIAN" in scenes[1]["characters"]
    print(f"✓ V.O. character extracted: SEBASTIAN")
    
    print("\n✅ All parser tests passed!")

if __name__ == "__main__":
    test_parser()
```

### Edge Cases to Handle
- Dual dialogue (two characters speaking simultaneously)
- INTERCUT sequences
- Montage scenes
- Flashbacks
- Title cards / chyrons
- Songs/lyrics (may be formatted differently)

### Acceptance Criteria
- [ ] Correctly splits script into scenes at INT./EXT. markers
- [ ] Extracts location from all scene headers
- [ ] Finds all speaking characters in each scene
- [ ] Handles V.O., O.S., CONT'D extensions correctly
- [ ] Action lines captured separately from dialogue
- [ ] Parentheticals associated with correct dialogue line

---

## Step 4: Character Extractor (LLM-Powered)

### File to Create
`preprocessing/character_extractor.py`

### Class: `CharacterExtractor`

#### Purpose
Use LLM (via LiteLLM) to extract rich character metadata and generate scene summaries.

#### Methods

```python
from openai import OpenAI
import os

class CharacterExtractor:
    """LLM-powered character metadata extraction using LiteLLM."""
    
    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        """
        Initialize with LiteLLM configuration.
        
        Args:
            api_key: LiteLLM API key (defaults to LITELLM_API_KEY env var)
            base_url: LiteLLM base URL (defaults to LITELLM_API_BASE env var)
            model: Model name (defaults to FILMBUDDY_LLM_MODEL env var, or "gpt-4o" if not set)
        
        Note: Uses the same configuration as your existing server/main.py
        """
        self.api_key = api_key or os.environ.get("LITELLM_API_KEY")
        self.base_url = base_url or os.environ.get("LITELLM_API_BASE")
        self.model = model or os.environ.get("FILMBUDDY_LLM_MODEL", "gpt-4o")
        
        # Initialize OpenAI client (compatible with LiteLLM)
        if self.base_url:
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        else:
            self.client = OpenAI(api_key=self.api_key)
        
        print(f"[CharacterExtractor] Using model: {self.model}")
        if self.base_url:
            print(f"[CharacterExtractor] LiteLLM base URL: {self.base_url}")
    
    async def extract_character_metadata(
        self, 
        script_text: str, 
        character_names: list[str]
    ) -> dict[str, dict]:
        """
        Extract character metadata from script using LLM.
        
        Args:
            script_text: Full script or first N pages
            character_names: List of character names found by parser
        
        Returns:
            dict mapping character names to metadata:
            {
                "MIA": {
                    "full_name": "Mia Dolan",
                    "gender": "female",
                    "role": "protagonist",  # protagonist | antagonist | supporting | minor
                    "description": "Aspiring actress working as a barista...",
                    "occupation": "Barista / Actress",
                    "relationships": {
                        "SEBASTIAN": "love interest, later boyfriend"
                    },
                    "first_appearance_scene": 1
                },
                ...
            }
        
        Implementation Notes:
            - Use first 15-20 pages of script for context (characters are usually introduced early)
            - Send single prompt with all characters to avoid multiple API calls
            - Use JSON mode or structured output for reliable parsing
            - Example call:
              response = self.client.chat.completions.create(
                  model=self.model,
                  messages=[{"role": "user", "content": prompt}],
                  response_format={"type": "json_object"},
                  temperature=0.3
              )
        """
        pass
    
    async def generate_scene_summary(
        self, 
        scene: dict, 
        character_metadata: dict = None
    ) -> str:
        """
        Generate 1-2 sentence summary of a scene.
        
        Args:
            scene: Parsed scene dict from ScriptParser
            character_metadata: Optional character info for context
        
        Returns:
            str: Concise summary, e.g., 
            "Mia and Sebastian argue about their relationship at the Griffith Observatory, 
             leading to their decision to pursue their individual dreams."
        
        Implementation Notes:
            - Keep summaries factual and concise
            - Mention key characters and main action
            - Avoid spoilers if possible (just describe what happens, not why it matters)
            - Example call:
              response = self.client.chat.completions.create(
                  model=self.model,
                  messages=[{"role": "user", "content": prompt}],
                  temperature=0.5,
                  max_tokens=150
              )
        """
        pass
    
    async def batch_generate_summaries(
        self, 
        scenes: list[dict], 
        character_metadata: dict = None,
        batch_size: int = 5
    ) -> list[str]:
        """
        Generate summaries for multiple scenes efficiently.
        
        Args:
            scenes: List of parsed scenes
            character_metadata: Character info dict
            batch_size: Number of scenes per API call
        
        Returns:
            list[str]: Summaries in same order as input scenes
        
        Implementation Notes:
            - Batch 5 scenes per API call to reduce costs
            - Use asyncio.gather for parallel batches
            - Total API calls = ceil(num_scenes / batch_size)
        """
        pass
```

#### Prompt Templates

**Character Extraction Prompt:**
```python
# Use with response_format={"type": "json_object"} for reliable JSON parsing

prompt = f"""You are analyzing a movie script to extract character information.

SCRIPT EXCERPT (first 20 pages):
{script_text}

CHARACTERS TO ANALYZE:
{', '.join(character_list)}

For each character, provide:
1. full_name - Their complete name if mentioned
2. gender - "male", "female", or "unknown"
3. role - "protagonist", "antagonist", "supporting", or "minor"
4. description - 1-2 sentence description of who they are
5. occupation - Their job or role in life (if known)
6. relationships - Key relationships to other characters in this list

Return ONLY valid JSON in this exact format:
{{
  "CHARACTER_NAME": {{
    "full_name": "...",
    "gender": "...",
    "role": "...",
    "description": "...",
    "occupation": "...",
    "relationships": {{"OTHER_CHAR": "relationship description"}}
  }}
}}
"""
```

**Scene Summary Prompt:**
```python
prompt = f"""Summarize this movie scene in 1-2 sentences. Focus on what happens, who's involved, 
and any key emotional beats. Be concise and factual.

LOCATION: {scene['location']}
CHARACTERS: {', '.join(scene['characters'])}

SCENE:
{scene['raw_text'][:1000]}  # Truncate very long scenes

Summary:"""
```

### Test Script

```python
# test_character_extractor.py
import asyncio
from preprocessing.character_extractor import CharacterExtractor

SAMPLE_SCRIPT = """
INT. COFFEE SHOP - DAY

MIA DOLAN, 25, an aspiring actress with a warm smile but tired eyes, 
wipes down tables. She's working the early shift again.

                         MIA
          Why do I do this to myself?

SEBASTIAN, 30s, a jazz pianist with a stubborn streak, enters. 
He orders without looking up from his phone.

                         SEBASTIAN
          Black coffee.

Their eyes meet. Something sparks.

                         MIA
          Do I know you?
"""

async def test_extractor():
    # Initialize with your LiteLLM configuration
    extractor = CharacterExtractor()
    
    print(f"[Test] Using model: {extractor.model}")
    
    # Test 1: Character extraction
    print("\n[Test 1] Extracting character metadata...")
    metadata = await extractor.extract_character_metadata(
        SAMPLE_SCRIPT, 
        ["MIA", "SEBASTIAN"]
    )
    
    assert "MIA" in metadata, "MIA not found in metadata"
    assert metadata["MIA"]["gender"] == "female", f"Expected female, got {metadata['MIA']['gender']}"
    print(f"✓ Extracted MIA: {metadata['MIA']['description'][:50]}...")
    
    # Test 2: Scene summary
    print("\n[Test 2] Generating scene summary...")
    scene = {
        "location": "COFFEE SHOP",
        "characters": ["MIA", "SEBASTIAN"],
        "raw_text": SAMPLE_SCRIPT
    }
    summary = await extractor.generate_scene_summary(scene, metadata)
    assert len(summary) > 20, f"Summary too short: {summary}"
    print(f"✓ Summary: {summary}")
    
    print("\n✅ All extractor tests passed!")

if __name__ == "__main__":
    asyncio.run(test_extractor())
```

### Cost Optimization Notes
- Character extraction: ~1 API call per movie (first 20 pages only)
- Scene summaries: ~N/5 API calls where N = number of scenes (batch 5 scenes per call)
- Estimated cost per movie: Depends on your LiteLLM model choice
  - GPT-4o: ~$0.50-$1.50 per movie
  - Claude Sonnet: ~$0.50-$2.00 per movie
  - Claude Haiku: ~$0.10-$0.30 per movie (cheaper option)

### Acceptance Criteria
- [ ] Returns structured JSON for all characters
- [ ] Gender detection is accurate (from script descriptions)
- [ ] Role classification distinguishes main characters
- [ ] Relationships extracted when explicit in script
- [ ] Scene summaries are concise (< 200 characters typically)
- [ ] Batch processing reduces API calls

---

## Step 5: Timestamp Aligner

### File to Create
`preprocessing/timestamp_aligner.py`

### Class: `TimestampAligner`

#### Purpose
Align script scenes to subtitle timestamps using fuzzy dialogue matching.

#### Strategy
1. Extract unique dialogue phrases from each scene
2. Search for matching phrases in subtitle text
3. When match found, use subtitle timestamp as scene timestamp
4. For scenes without matches, interpolate from neighboring scenes

#### Methods

```python
class TimestampAligner:
    """Align script scenes to subtitle timestamps."""
    
    def __init__(self, match_threshold: float = 0.75):
        """
        Args:
            match_threshold: Minimum similarity ratio for fuzzy match (0-1)
        """
        self.match_threshold = match_threshold
    
    def align_scenes_to_subtitles(
        self, 
        scenes: list[dict], 
        subtitles: list[dict]
    ) -> list[dict]:
        """
        Add timestamp fields to each scene.
        
        Args:
            scenes: Parsed scenes from ScriptParser
            subtitles: Parsed subtitle cues (from existing build_time_aware_corpus.py)
        
        Returns:
            list of scenes with added fields:
                - t_start: float (seconds)
                - t_end: float (seconds)
                - alignment_confidence: float (0-1)
                - alignment_method: str ("dialogue_match" | "interpolated")
        
        Implementation:
            1. Build search index from subtitle text
            2. For each scene, extract key dialogue lines
            3. Search subtitles for matching dialogue
            4. If match found, use subtitle timestamp ± buffer
            5. If no match, interpolate from neighbors or use proportional estimate
        """
        pass
    
    def _extract_key_dialogue(self, scene: dict) -> list[str]:
        """
        Extract searchable dialogue phrases from scene.
        
        - Prefer first and last dialogue lines (more distinctive)
        - Clean punctuation and normalize whitespace
        - Skip very short lines (< 4 words)
        
        Returns:
            list of 3-5 key phrases to search for
        """
        pass
    
    def _fuzzy_match_in_subtitles(
        self, 
        phrase: str, 
        subtitles: list[dict],
        time_window: tuple[float, float] = None
    ) -> tuple[float, float, float] | None:
        """
        Find phrase in subtitles using fuzzy matching.
        
        Args:
            phrase: Dialogue to search for
            subtitles: Subtitle list
            time_window: Optional (start, end) to narrow search
        
        Returns:
            (t_start, t_end, confidence) if found, else None
        
        Implementation:
            - Use rapidfuzz.fuzz.partial_ratio for similarity
            - Normalize both strings (lowercase, remove punctuation)
            - Return subtitle cue with highest match above threshold
        """
        pass
    
    def _interpolate_timestamp(
        self, 
        scene_idx: int, 
        scenes: list[dict], 
        total_duration: float
    ) -> tuple[float, float]:
        """
        Estimate timestamp when no dialogue match found.
        
        Strategy:
            1. If neighbors have timestamps, interpolate between them
            2. Otherwise, use proportional estimate:
               t_start = (scene_idx / total_scenes) * total_duration
        """
        pass
    
    @staticmethod
    def parse_srt(srt_path: str) -> list[dict]:
        """
        Parse SRT file into list of subtitle cues.
        
        Returns:
            list of dicts with keys: t_start, t_end, text
        
        Note: Can reuse logic from build_time_aware_corpus.py
        """
        pass
```

### Matching Strategy Details

```
Scene Dialogue:                    Subtitle Text:
"Why do I do this to myself?"  →   "Why do I do this to myself?" at 03:24
"Black coffee."                →   "Black coffee." at 03:28

Result:
Scene timestamp: 03:24 - 03:35 (with 7s buffer after last match)
Confidence: 0.95 (2/2 key phrases matched)
```

### Test Script

```python
# test_timestamp_aligner.py
from preprocessing.timestamp_aligner import TimestampAligner

def test_aligner():
    aligner = TimestampAligner()
    
    # Load real subtitle data
    subtitles = aligner.parse_srt("data/lalaland.srt")
    
    # Create mock scenes with known dialogue
    scenes = [
        {
            "scene_id": 1,
            "location": "CAR",
            "dialogue": [
                {"text": "It's another hot, sunny day today here in Southern California"}
            ]
        },
        {
            "scene_id": 2,
            "location": "COFFEE SHOP",
            "dialogue": [
                {"text": "I mean, we could not believe what was happening"}
            ]
        }
    ]
    
    # Test alignment
    aligned = aligner.align_scenes_to_subtitles(scenes, subtitles)
    
    # Check timestamps were added
    assert "t_start" in aligned[0]
    assert "t_end" in aligned[0]
    assert aligned[0]["alignment_confidence"] >= 0.7
    
    print(f"✓ Scene 1 aligned to {aligned[0]['t_start']:.1f}s - {aligned[0]['t_end']:.1f}s")
    print(f"  Confidence: {aligned[0]['alignment_confidence']:.2f}")
    
    print("\n✅ Aligner tests passed!")

if __name__ == "__main__":
    test_aligner()
```

### Handling Edge Cases
- **No dialogue scenes**: Use runtime proportional estimate
- **Musical numbers**: Match lyrics instead of dialogue
- **Montages**: Assign reasonable duration, low confidence
- **Director's cut differences**: Accept lower confidence matches

### Acceptance Criteria
- [ ] 80%+ of scenes get "dialogue_match" alignment
- [ ] Interpolated scenes have reasonable timestamps
- [ ] Confidence scores reflect match quality
- [ ] Handles scenes without dialogue gracefully
- [ ] Works with existing SRT parsing code

---

## Step 6: Corpus Builder (Orchestrator)

### File to Create
`preprocessing/corpus_builder.py`

### Class: `MovieCorpusBuilder`

#### Purpose
Orchestrate the full preprocessing pipeline: TMDB → Script → Characters → Alignment → Enrichment.

#### Methods

```python
class MovieCorpusBuilder:
    """Orchestrates the full corpus building pipeline."""
    
    def __init__(self):
        self.tmdb = TMDBClient()
        self.parser = ScriptParser()
        self.extractor = CharacterExtractor()
        self.aligner = TimestampAligner()
    
    async def build_corpus(
        self,
        movie_title: str,
        script_path: str,
        subtitle_path: str,
        release_year: int = None,
        output_dir: str = "corpus"
    ) -> dict:
        """
        Build complete enriched corpus for a movie.
        
        Args:
            movie_title: Movie title for TMDB lookup
            script_path: Path to screenplay .txt file
            subtitle_path: Path to .srt file
            release_year: Optional year for TMDB disambiguation
            output_dir: Where to save output files
        
        Returns:
            dict with keys:
                - movie_id: str (e.g., "la_la_land_2016")
                - metadata: dict (from TMDB)
                - characters: dict (merged TMDB + LLM extraction)
                - scenes: list[dict] (fully enriched scenes)
                - stats: dict (processing statistics)
        
        Pipeline:
            1. Fetch TMDB metadata (cast, runtime)
            2. Parse script into scenes
            3. Extract character metadata via LLM (using LiteLLM)
            4. Merge TMDB cast with script characters
            5. Load and parse subtitles
            6. Align scenes to timestamps
            7. Generate scene summaries (LLM, batched for efficiency)
            8. Build final enriched chunks
            9. Save to JSONL and return
        """
        pass
    
    def _merge_character_data(
        self, 
        script_characters: dict,  # From LLM extraction
        tmdb_cast: list[dict]     # From TMDB
    ) -> dict:
        """
        Merge character info from both sources.
        
        Challenges:
            - Script may use nickname (MIA), TMDB has full name (Mia Dolan)
            - Script may have minor characters not in TMDB top 20
            - Need fuzzy matching for character names
        
        Strategy:
            1. For each TMDB character, fuzzy match to script characters
            2. Merge fields: script gets priority for description/role
            3. TMDB adds: actor_name, profile_image, billing_order
            4. Script-only characters: keep with "unknown" actor
        
        Returns:
            dict[str, MergedCharacter]
        """
        pass
    
    def _build_enriched_chunk(
        self, 
        scene: dict, 
        characters: dict,
        summary: str
    ) -> dict:
        """
        Build final chunk format for vector storage.
        
        Returns:
            {
                "chunk_id": "la_la_land_2016_scene_001",
                "movie_id": "la_la_land_2016",
                "source_type": "script",
                "t_start": 204.5,
                "t_end": 287.3,
                
                # Scene info
                "scene_id": 1,
                "scene_header": "INT. COFFEE SHOP - DAY",
                "location": "COFFEE SHOP",
                "time_of_day": "DAY",
                
                # Content
                "summary": "Mia arrives late to her barista job...",
                "dialogue_text": "MIA: Sorry I'm late...",
                "action_text": "Mia enters looking harried...",
                
                # Characters (key for deictic questions!)
                "characters_present": ["MIA", "MANAGER"],
                "character_details": {
                    "MIA": {
                        "full_name": "Mia Dolan",
                        "actor": "Emma Stone",
                        "gender": "female",
                        "role": "protagonist"
                    },
                    ...
                },
                
                # Alignment metadata
                "alignment_confidence": 0.92,
                "alignment_method": "dialogue_match"
            }
        """
        pass
    
    def save_corpus(self, corpus: dict, output_dir: str) -> str:
        """
        Save corpus to JSONL file.
        
        File naming: {movie_id}_enriched.jsonl
        
        Returns:
            Path to saved file
        """
        pass
```

### Output File Format

```jsonl
{"chunk_id":"la_la_land_2016_scene_001","movie_id":"la_la_land_2016","source_type":"script","t_start":204.5,"t_end":287.3,"scene_id":1,"location":"COFFEE SHOP","characters_present":["MIA","MANAGER"],"character_details":{"MIA":{"full_name":"Mia Dolan","actor":"Emma Stone","gender":"female","role":"protagonist"}},"summary":"Mia arrives late to her barista job and gets reprimanded by her manager.","alignment_confidence":0.92}
```

### Test Script

```python
# test_corpus_builder.py
import asyncio
from preprocessing.corpus_builder import MovieCorpusBuilder

async def test_full_pipeline():
    builder = MovieCorpusBuilder()
    
    # This test requires actual script and subtitle files
    corpus = await builder.build_corpus(
        movie_title="La La Land",
        script_path="scripts/lalaland_script.txt",  # You'll need to obtain this
        subtitle_path="data/lalaland.srt",
        release_year=2016
    )
    
    # Validate output
    assert corpus["movie_id"] == "la_la_land_2016"
    assert len(corpus["scenes"]) > 50  # La La Land has ~100 scenes
    assert "MIA" in corpus["characters"]
    assert corpus["characters"]["MIA"]["actor"] == "Emma Stone"
    
    print(f"✓ Built corpus: {len(corpus['scenes'])} scenes")
    print(f"✓ Characters: {list(corpus['characters'].keys())[:5]}...")
    print(f"✓ Sample scene: {corpus['scenes'][0]['summary'][:50]}...")
    
    # Check enriched chunk format
    scene = corpus["scenes"][0]
    assert "t_start" in scene
    assert "characters_present" in scene
    assert "character_details" in scene
    
    print("\n✅ Full pipeline test passed!")

if __name__ == "__main__":
    asyncio.run(test_full_pipeline())
```

### Acceptance Criteria
- [ ] Full pipeline completes in < 5 minutes per movie
- [ ] All scenes have timestamps (matched or interpolated)
- [ ] Characters merged from TMDB and script
- [ ] Summaries generated for all scenes
- [ ] Output JSONL is valid and loadable
- [ ] Stats include success rates and timing

---

## Step 7: Vector Store (ChromaDB)

### File to Create
`preprocessing/vector_store.py`

### Class: `MovieVectorStore`

#### Purpose
Store enriched corpus in ChromaDB with efficient timestamp-based retrieval.

#### Methods

```python
class MovieVectorStore:
    """ChromaDB-backed vector store for movie corpora."""
    
    def __init__(self, persist_directory: str = "./chroma_db"):
        """Initialize ChromaDB client with persistence."""
        pass
    
    def store_movie_corpus(self, corpus: dict) -> None:
        """
        Store enriched corpus in vector database.
        
        Creates two collections:
            1. {movie_id}_scenes - Scene chunks with embeddings
            2. {movie_id}_characters - Character metadata (no embeddings needed)
        
        Scene documents include:
            - Full text for embedding (summary + key dialogue)
            - Metadata for filtering (t_start, t_end, characters, location)
        """
        pass
    
    def query_scene_at_timestamp(
        self, 
        movie_id: str, 
        timestamp: float,
        buffer: float = 30.0
    ) -> dict | None:
        """
        Retrieve the scene containing a specific timestamp.
        
        Args:
            movie_id: Movie identifier
            timestamp: Playback time in seconds
            buffer: Tolerance window in seconds
        
        Returns:
            Scene dict or None if not found
        
        Implementation:
            Use metadata filtering: t_start <= timestamp <= t_end
        """
        pass
    
    def query_characters_in_scene(
        self, 
        movie_id: str, 
        scene_id: int
    ) -> list[dict]:
        """
        Get character details for a specific scene.
        
        Returns:
            list of character dicts with full metadata
        """
        pass
    
    def semantic_search(
        self, 
        movie_id: str, 
        query: str,
        timestamp: float = None,
        top_k: int = 5,
        spoiler_mode: str = "off"
    ) -> list[dict]:
        """
        Semantic search with optional temporal constraints.
        
        Args:
            movie_id: Movie identifier
            query: Search query
            timestamp: Current playback time (for spoiler filtering)
            top_k: Number of results
            spoiler_mode: "off" filters future content
        
        Returns:
            list of scene dicts sorted by relevance
        """
        pass
    
    def list_movies(self) -> list[str]:
        """List all movies in the store."""
        pass
    
    def delete_movie(self, movie_id: str) -> bool:
        """Remove a movie from the store."""
        pass
```

### Integration with Existing Server

The vector store should be compatible with the existing `server/main.py`. Key integration points:

```python
# In server/main.py, update to use new vector store for enriched content

from preprocessing.vector_store import MovieVectorStore

vector_store = MovieVectorStore()

@app.post("/ask")
async def ask(req: AskRequest):
    # 1. Get current scene context from enriched corpus
    current_scene = vector_store.query_scene_at_timestamp(
        req.film_id, 
        req.t_now
    )
    
    # 2. Format character context for LLM
    if current_scene:
        character_context = format_character_details(current_scene)
    
    # 3. Semantic search for additional context
    hits = vector_store.semantic_search(
        req.film_id,
        req.query,
        timestamp=req.t_now,
        top_k=6,
        spoiler_mode=req.spoiler_mode
    )
    
    # 4. Generate response with enriched context
    answer = await generate_response_with_scene_context(
        query=req.query,
        current_scene=current_scene,
        hits=hits
    )
```

### Test Script

```python
# test_vector_store.py
from preprocessing.vector_store import MovieVectorStore
import json

def test_vector_store():
    store = MovieVectorStore()
    
    # Load a sample corpus
    with open("corpus/la_la_land_enriched.jsonl") as f:
        scenes = [json.loads(line) for line in f]
    
    corpus = {
        "movie_id": "la_la_land_2016",
        "scenes": scenes
    }
    
    # Test 1: Store corpus
    store.store_movie_corpus(corpus)
    print("✓ Stored corpus")
    
    # Test 2: Query by timestamp
    scene = store.query_scene_at_timestamp("la_la_land_2016", 845.0)
    assert scene is not None
    print(f"✓ Found scene at 845s: {scene['location']}")
    
    # Test 3: Get characters in scene
    chars = scene.get("character_details", {})
    print(f"✓ Characters: {list(chars.keys())}")
    
    # Test 4: Semantic search
    results = store.semantic_search(
        "la_la_land_2016", 
        "Who is the girl at the coffee shop?",
        timestamp=400.0
    )
    assert len(results) > 0
    print(f"✓ Semantic search returned {len(results)} results")
    
    print("\n✅ Vector store tests passed!")

if __name__ == "__main__":
    test_vector_store()
```

### Acceptance Criteria
- [ ] Corpus stored with correct metadata
- [ ] Timestamp queries return correct scene
- [ ] Character details accessible per scene
- [ ] Semantic search works with spoiler filtering
- [ ] Persistence works across restarts
- [ ] Compatible with existing server code

---

## Step 8: API Integration & Server Updates

### Files to Modify
- `server/main.py`

### New Endpoints

```python
# Add to server/main.py

from preprocessing.corpus_builder import MovieCorpusBuilder
from preprocessing.vector_store import MovieVectorStore

# Initialize vector store alongside existing film_data
vector_store = MovieVectorStore()

@router.post("/process-movie")
async def process_movie(
    movie_title: str = Form(...),
    release_year: int = Form(None),
    script_file: UploadFile = File(...),
    subtitle_file: UploadFile = File(None)
):
    """
    Process a new movie through the enrichment pipeline.
    
    This endpoint:
    1. Saves uploaded files
    2. Runs the full corpus builder pipeline
    3. Stores result in vector database
    4. Returns processing stats
    """
    # Implementation here
    pass

@router.get("/movie/{movie_id}/scene")
async def get_scene_at_timestamp(
    movie_id: str,
    timestamp: float = Query(..., description="Playback time in seconds")
):
    """
    Get the enriched scene at a specific timestamp.
    
    Returns scene with:
    - Location and header
    - Characters present with full details
    - Scene summary
    - Dialogue excerpt
    """
    scene = vector_store.query_scene_at_timestamp(movie_id, timestamp)
    if not scene:
        raise HTTPException(404, "Scene not found at timestamp")
    return scene

@router.get("/movie/{movie_id}/characters")
async def get_movie_characters(movie_id: str):
    """
    Get all character metadata for a movie.
    
    Returns dict of character_name → character_details
    """
    # Implementation here
    pass
```

### Updated `/ask` Endpoint

```python
@app.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest):
    """
    Enhanced query endpoint with scene context.
    """
    # Check if we have enriched data for this film
    has_enriched = vector_store.has_movie(req.film_id)
    
    if has_enriched:
        # Use new enriched context
        current_scene = vector_store.query_scene_at_timestamp(
            req.film_id, req.t_now
        )
        
        # Build rich context with character details
        context = build_enriched_context(current_scene, req.t_now)
        
        # Semantic search on enriched corpus
        hits = vector_store.semantic_search(
            req.film_id,
            req.query,
            timestamp=req.t_now if req.spoiler_mode == "off" else None,
            top_k=req.top_k or 6
        )
    else:
        # Fall back to existing subtitle-only logic
        return existing_search_logic(req)
    
    # Generate response with enriched context
    answer = await generate_enriched_response(
        query=req.query,
        scene_context=context,
        hits=hits,
        spoiler_mode=req.spoiler_mode
    )
    
    return AskResponse(
        answer=answer,
        hits=convert_to_hits(hits),
        current_scene=current_scene,  # New field!
        ...
    )
```

### Updated LLM Prompt

```python
def generate_enriched_response(query, scene_context, hits, spoiler_mode):
    """Generate response with full scene awareness."""
    
    system_prompt = f"""You are FilmBuddy, a movie companion chatbot.

CURRENT SCENE CONTEXT:
Location: {scene_context['location']}
Time: {format_time(scene_context['t_start'])} - {format_time(scene_context['t_end'])}

CHARACTERS IN THIS SCENE:
{format_characters(scene_context['character_details'])}

SCENE SUMMARY:
{scene_context['summary']}

IMPORTANT: When the user asks "who's that guy?" or similar vague questions,
use the CHARACTERS IN THIS SCENE section to identify who they're likely 
referring to. If there are multiple possibilities, list them.

Spoiler mode: {spoiler_mode}
"""
    
    # Rest of LLM call...
```

### Acceptance Criteria
- [ ] `/process-movie` accepts script + subtitle uploads
- [ ] `/movie/{id}/scene` returns enriched scene data
- [ ] `/ask` uses enriched context when available
- [ ] Falls back gracefully when enriched data not available
- [ ] LLM prompt includes character details
- [ ] Response time < 3 seconds

---

## Step 9: Testing & Validation

### Test Categories

#### 1. Unit Tests

```python
# tests/test_unit.py

def test_script_parser_scene_detection():
    """Test scene header detection edge cases."""
    pass

def test_character_name_cleaning():
    """Test removal of V.O., CONT'D, etc."""
    pass

def test_fuzzy_matching():
    """Test subtitle alignment fuzzy matching."""
    pass

def test_timestamp_interpolation():
    """Test gap filling for unmatched scenes."""
    pass
```

#### 2. Integration Tests

```python
# tests/test_integration.py

async def test_full_pipeline_la_la_land():
    """End-to-end test with real La La Land data."""
    builder = MovieCorpusBuilder()
    corpus = await builder.build_corpus(
        "La La Land",
        "scripts/lalaland.txt",
        "data/lalaland.srt",
        2016
    )
    
    # Validate
    assert len(corpus["scenes"]) > 80
    assert corpus["characters"]["MIA"]["actor"] == "Emma Stone"
    
async def test_vector_store_retrieval():
    """Test timestamp and semantic queries."""
    pass

async def test_api_endpoints():
    """Test all new REST endpoints."""
    pass
```

#### 3. Vague Question Tests

```python
# tests/test_deictic_questions.py

VAGUE_QUESTIONS = [
    ("Who's that guy?", 845, ["Should mention character name"]),
    ("What's this girl's name?", 400, ["Should identify Mia"]),
    ("Who's her boyfriend?", 2400, ["Should mention Sebastian"]),
    ("What did he just say?", 1200, ["Should quote recent dialogue"]),
    ("Who are they?", 650, ["Should list visible characters"]),
]

async def test_vague_questions():
    """Test accuracy on deictic/vague questions."""
    for question, timestamp, expected_content in VAGUE_QUESTIONS:
        response = await query_api(question, timestamp)
        
        for expected in expected_content:
            assert_in_response(expected, response)
```

#### 4. Performance Tests

```python
# tests/test_performance.py

async def test_preprocessing_time():
    """Corpus building should complete in < 5 minutes."""
    start = time.time()
    corpus = await builder.build_corpus(...)
    elapsed = time.time() - start
    assert elapsed < 300, f"Preprocessing took {elapsed:.1f}s"

async def test_query_latency():
    """Queries should respond in < 3 seconds."""
    start = time.time()
    response = await query_api("Who's that?", 845)
    elapsed = time.time() - start
    assert elapsed < 3, f"Query took {elapsed:.2f}s"
```

### Manual Testing Checklist

- [ ] Process La La Land through full pipeline
- [ ] Process 10 Things I Hate About You through full pipeline
- [ ] Test 10 different vague questions at various timestamps
- [ ] Verify character details are correct against IMDB
- [ ] Test spoiler mode blocks future content
- [ ] Test with browser extension end-to-end

### Success Metrics

| Metric | Before | After Target |
|--------|--------|--------------|
| Vague question accuracy | ~40% | ~85% |
| Query response time | 1-2s | < 3s |
| Preprocessing time | N/A | < 5 min |
| Character identification | 0% | 90%+ |

---

## Summary: File Structure

After implementation, your project should have:

```
filmbuddy/
├── preprocessing/
│   ├── __init__.py
│   ├── tmdb_client.py        # Step 2
│   ├── script_parser.py      # Step 3
│   ├── character_extractor.py # Step 4
│   ├── timestamp_aligner.py  # Step 5
│   ├── corpus_builder.py     # Step 6
│   └── vector_store.py       # Step 7
├── server/
│   └── main.py               # Step 8 (updated)
├── tests/
│   ├── test_unit.py
│   ├── test_integration.py
│   ├── test_deictic_questions.py
│   └── test_performance.py
├── corpus/
│   ├── la_la_land_chunks.jsonl      # Existing
│   ├── la_la_land_enriched.jsonl    # New!
│   └── ...
├── chroma_db/                       # New! Vector store persistence
├── .env                             # API keys
├── requirements.txt                 # Updated
└── scripts/
    ├── build_time_aware_corpus.py   # Existing
    └── process_movie.py             # New CLI for preprocessing
```

---

## Delegation Instructions

Each step can be delegated to an agent with the following instructions:

1. **Step 1 (Setup)**: "Set up the preprocessing module structure and update dependencies"
2. **Step 2 (TMDB)**: "Implement TMDBClient class with methods for fetching movie metadata"
3. **Step 3 (Parser)**: "Implement ScriptParser class to parse screenplays into structured scenes"
4. **Step 4 (LLM)**: "Implement CharacterExtractor using Claude API for metadata and summaries"
5. **Step 5 (Aligner)**: "Implement TimestampAligner to match script scenes to subtitle timestamps"
6. **Step 6 (Builder)**: "Implement MovieCorpusBuilder to orchestrate the full pipeline"
7. **Step 7 (Vector)**: "Implement MovieVectorStore with ChromaDB for storage and retrieval"
8. **Step 8 (API)**: "Update server/main.py to integrate enriched corpus and add new endpoints"
9. **Step 9 (Testing)**: "Create comprehensive test suite and validate end-to-end functionality"

Each agent should:
- Read the relevant section of this guide
- Implement the specified class/methods
- Write and run the test script
- Report success/failure and any issues

---

## Obtaining Movie Scripts

**Important**: Movie scripts are copyrighted. For development:

1. **Free sources** (may have formatting issues):
   - IMSDb (imsdb.com)
   - Script Slug
   - SimplyScripts

2. **Recommended approach**:
   - Download scripts manually for testing
   - Store in `scripts/` directory (gitignored)
   - Parser should handle various formatting quirks

3. **For production**:
   - Consider script transcription services
   - Or build subtitle-only fallback mode

