# server/main.py
# pip install fastapi uvicorn[standard] sentence-transformers numpy pydantic ujson python-multipart openai python-dotenv

from fastapi import FastAPI, HTTPException,  Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import os, json, ujson, math
import numpy as np
from sentence_transformers import SentenceTransformer
from openai import OpenAI, AzureOpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import MovieVectorStore for enriched corpus support
try:
    from preprocessing.vector_store import MovieVectorStore
    VECTOR_STORE_AVAILABLE = True
except ImportError:
    MovieVectorStore = None  # Define as None so type hints don't fail
    VECTOR_STORE_AVAILABLE = False
    print("[startup] Warning: MovieVectorStore not available. Enriched corpus features disabled.")

# ---------- Config ----------
CORPUS_DIR = os.environ.get("FILMBUDDY_CORPUS_DIR", "corpus")
EMB_MODEL = os.environ.get("FILMBUDDY_EMB_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
TOPK_DEFAULT = int(os.environ.get("FILMBUDDY_TOPK", "6"))
MAX_CANDIDATES = int(os.environ.get("FILMBUDDY_MAXCANDS", "128"))  # search breadth before filtering
EPS = 1e-6  # tolerance for float comparisons
STRICT_START_GATE = os.environ.get("FILMBUDDY_STRICT_START_GATE", "0") == "1"

# Temporal boosting configuration
TEMPORAL_WEIGHT = float(os.environ.get("FILMBUDDY_TEMPORAL_WEIGHT", "0.2"))  # Weight for temporal proximity (0-1)
TEMPORAL_DECAY = float(os.environ.get("FILMBUDDY_TEMPORAL_DECAY", "180"))  # Decay window in seconds (3 min)

# Cue type scoring penalties (reduce score for less useful content types)
CUE_TYPE_WEIGHTS = {
    "dialogue": 1.0,      # Full score for dialogue
    "lyric": 0.8,         # Slightly lower for lyrics
    "nonverbal": 0.3,     # Heavy penalty for sound effects
    "metadata": 0.1,      # Almost ignore metadata
}

# LLM Configuration (supports OpenAI, Azure OpenAI, and LiteLLM)
# Azure OpenAI settings
AZURE_OPENAI_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21")
AZURE_OPENAI_DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4")

# Standard OpenAI / LiteLLM settings
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
LITELLM_API_KEY = os.environ.get("LITELLM_API_KEY")
LITELLM_API_BASE = os.environ.get("LITELLM_API_BASE")
OPENAI_MODEL = os.environ.get("FILMBUDDY_LLM_MODEL", "gpt-4o")

# Determine which provider to use (Azure takes priority if configured)
USE_AZURE = AZURE_OPENAI_API_KEY is not None and AZURE_OPENAI_ENDPOINT is not None

if USE_AZURE:
    # Use Azure OpenAI
    LLM_ENABLED = True
    LLM_MODEL = AZURE_OPENAI_DEPLOYMENT
    openai_client = AzureOpenAI(
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
        azure_endpoint=AZURE_OPENAI_ENDPOINT
    )
else:
    # Use standard OpenAI or LiteLLM
    api_key = LITELLM_API_KEY or OPENAI_API_KEY
    LLM_ENABLED = api_key is not None
    LLM_MODEL = OPENAI_MODEL

    if LLM_ENABLED:
        if LITELLM_API_BASE:
            openai_client = OpenAI(api_key=api_key, base_url=LITELLM_API_BASE)
        else:
            openai_client = OpenAI(api_key=api_key)
    else:
        openai_client = None

# ---------- Data structures ----------
class AskRequest(BaseModel):
    film_id: str = Field(..., example="la_la_land")
    t_now: float = Field(..., example=4230.0, description="Playback time in seconds")
    query: str = Field(..., example="Why is she mad?")
    spoiler_mode: str = Field("off", description='"off" to enforce t_end ≤ t_now; "on" to allow future context')
    profile: Optional[str] = Field("novice")
    top_k: Optional[int] = Field(None, ge=1, le=20, description="How many chunks to return (default 6)")

class Hit(BaseModel):
    t_start: float
    t_end: float
    source_type: str
    cue_type: Optional[str] = None
    text: str
    speakers: Optional[List[str]] = None
    score: float
    film_id: str
    idx: int  # internal index, useful for debugging

class AskResponse(BaseModel):
    answer: Optional[str] = None  # LLM-generated conversational response
    hits: List[Hit]
    note: str
    film_id: str
    t_now: float
    spoiler_mode: str
    top_k: int
    validation: Dict[str, Any]
    llm_enabled: bool = False
    current_scene: Optional[Dict[str, Any]] = None  # Enriched scene data if available

# ---------- App ----------
app = FastAPI(title="FilmBuddy Minimal Backend", version="0.1.0")

# Allow your extension & localhost to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten later (e.g., chrome-extension://<id>, http://localhost:3000)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Load corpus & build embeddings ----------
# Store data per film
film_data = {}  # film_id -> {"payloads": [...], "embeddings": np.ndarray}
model: SentenceTransformer = None

# Vector store for enriched corpus (optional, enhanced features)
vector_store: Optional[MovieVectorStore] = None

# Mapping from subtitle corpus film_id to enriched corpus movie_id
# This handles cases where naming differs (e.g., "la_la_land" -> "la_la_land_2016")
film_id_to_enriched_id = {}

def load_jsonl(path: str) -> List[Dict[str, Any]]:
    data = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # ujson for speed; fall back to json if needed
            try:
                data.append(ujson.loads(line))
            except Exception:
                data.append(json.loads(line))
    return data

def normalize_rows(x: np.ndarray) -> np.ndarray:
    # Avoid division by zero
    norms = np.linalg.norm(x, axis=1, keepdims=True) + 1e-12
    return x / norms

@app.on_event("startup")
def startup():
    global film_data, model, vector_store
    
    if not os.path.exists(CORPUS_DIR):
        raise RuntimeError(f"Corpus directory not found at {CORPUS_DIR}")
    
    # Load embedding model once
    model = SentenceTransformer(EMB_MODEL)
    
    # Initialize vector store if available
    if VECTOR_STORE_AVAILABLE:
        try:
            vector_store = MovieVectorStore(persist_directory="./chroma_db")
            print(f"[startup] ✓ Vector store initialized")
        except Exception as e:
            print(f"[startup] Warning: Failed to initialize vector store: {e}")
            vector_store = None
    
    # Find all corpus files
    corpus_files = [f for f in os.listdir(CORPUS_DIR) if f.endswith('_chunks.jsonl')]
    
    if not corpus_files:
        raise RuntimeError(f"No corpus files found in {CORPUS_DIR}")
    
    print(f"[startup] Found {len(corpus_files)} corpus file(s)")
    
    # Load each film's corpus
    for corpus_file in corpus_files:
        corpus_path = os.path.join(CORPUS_DIR, corpus_file)
        payloads = load_jsonl(corpus_path)
        
        if not payloads:
            print(f"[startup] Warning: {corpus_file} is empty, skipping")
            continue
        
        # Get film_id from first record
        film_id = payloads[0].get("film_id")
        if not film_id:
            print(f"[startup] Warning: {corpus_file} has no film_id, skipping")
            continue
        
        # Validate records
        for i, r in enumerate(payloads):
            if not (isinstance(r.get("t_start"), (int, float)) and isinstance(r.get("t_end"), (int, float))):
                raise RuntimeError(f"Record {i} in {corpus_file} missing t_start/t_end")
        
        # Create embeddings for this film
        texts = [r["text"] for r in payloads]
        print(f"[startup] Encoding {len(texts)} chunks for {film_id}...")
        embs = model.encode(texts, batch_size=64, show_progress_bar=True, normalize_embeddings=True)
        embeddings = embs.astype("float32")
        
        # Store film data
        film_data[film_id] = {
            "payloads": payloads,
            "embeddings": embeddings
        }
        
        print(f"[startup] ✓ Loaded {len(payloads)} chunks for '{film_id}' (dim={embeddings.shape[1]})")
    
    print(f"[startup] Total films loaded: {len(film_data)}")
    print(f"[startup] Available film_ids: {list(film_data.keys())}")
    
    # Check for enriched corpora in vector store and build mapping
    if vector_store:
        enriched_movies = vector_store.list_movies()
        if enriched_movies:
            print(f"[startup] ✓ Found {len(enriched_movies)} enriched corpus(es) in vector store:")
            for movie_id in enriched_movies:
                print(f"[startup]   - {movie_id} (with character metadata)")
                
                # Try to match to loaded films (fuzzy matching)
                # e.g., "la_la_land_2016" matches "la_la_land"
                for film_id in film_data.keys():
                    # Simple heuristic: enriched ID often starts with film_id
                    if movie_id.startswith(film_id) or film_id.startswith(movie_id.rsplit('_', 1)[0]):
                        film_id_to_enriched_id[film_id] = movie_id
                        print(f"[startup]   → Mapped '{film_id}' to enriched corpus '{movie_id}'")
                        break
        else:
            print(f"[startup] No enriched corpora found in vector store yet")
            print(f"[startup] Run corpus builder to create enriched versions")
    
    if LLM_ENABLED:
        print(f"[startup] LLM generation enabled")
        if USE_AZURE:
            print(f"[startup] Provider: Azure OpenAI")
            print(f"[startup] Endpoint: {AZURE_OPENAI_ENDPOINT}")
            print(f"[startup] Deployment: {LLM_MODEL}")
        else:
            print(f"[startup] Provider: OpenAI" + (" (via LiteLLM)" if LITELLM_API_BASE else ""))
            print(f"[startup] Model: {LLM_MODEL}")
            if LITELLM_API_BASE:
                print(f"[startup] Base URL: {LITELLM_API_BASE}")
    else:
        print("[startup] LLM generation disabled (no API keys configured)")

# ---------- LLM Generation ----------
def get_temporal_context(film_id: str, t_now: float, window_seconds: float = 60) -> Dict[str, Any]:
    """Get recent dialogue and scene context around current timestamp.
    
    Uses soft scene boundary detection: identifies multiple scenes but de-weights
    older scenes rather than removing them completely.
    """
    if film_id not in film_data:
        return {"recent_dialogue": [], "characters_present": set(), "scenes": []}
    
    payloads = film_data[film_id]["payloads"]
    
    # Get chunks from the last window_seconds
    recent_chunks = []
    for chunk in payloads:
        # Only include chunks that END within our window before current time
        if t_now - window_seconds <= chunk["t_end"] <= t_now:
            recent_chunks.append(chunk.copy())  # Copy to avoid modifying original
    
    # Sort by timestamp
    recent_chunks.sort(key=lambda x: x["t_start"])
    
    # SCENE BOUNDARY DETECTION
    # Detect scene changes by looking for time gaps (>3 seconds indicates scene cut)
    scene_boundaries = []
    for i in range(len(recent_chunks) - 1):
        time_gap = recent_chunks[i+1]['t_start'] - recent_chunks[i]['t_end']
        if time_gap > 3.0:  # 3+ second gap indicates scene change
            scene_boundaries.append(i)
    
    # Segment chunks into scenes
    scenes = []
    start_idx = 0
    for boundary_idx in scene_boundaries:
        scene_chunks = recent_chunks[start_idx:boundary_idx + 1]
        if scene_chunks:
            scenes.append({
                'chunks': scene_chunks,
                't_start': scene_chunks[0]['t_start'],
                't_end': scene_chunks[-1]['t_end'],
                'is_current': False  # Will update below
            })
        start_idx = boundary_idx + 1
    
    # Add the final scene (after last boundary, or all chunks if no boundaries)
    final_scene_chunks = recent_chunks[start_idx:]
    if final_scene_chunks:
        scenes.append({
            'chunks': final_scene_chunks,
            't_start': final_scene_chunks[0]['t_start'],
            't_end': final_scene_chunks[-1]['t_end'],
            'is_current': True  # Most recent scene
        })
    
    # If no boundaries detected, all chunks are one scene
    if not scenes and recent_chunks:
        scenes.append({
            'chunks': recent_chunks,
            't_start': recent_chunks[0]['t_start'],
            't_end': recent_chunks[-1]['t_end'],
            'is_current': True
        })
    
    # SOFT WEIGHTING: Add recency weight to each chunk
    # Current scene gets weight 1.0, previous scenes get exponentially lower weights
    for scene_idx, scene in enumerate(scenes):
        is_current = scene['is_current']
        # Current scene: full weight, previous scenes: decreasing weight
        if is_current:
            scene_weight = 1.0
        else:
            # Exponential decay: older scenes get lower weight
            scenes_ago = len(scenes) - 1 - scene_idx
            scene_weight = 0.3 ** scenes_ago  # e.g., 0.3 for previous scene, 0.09 for 2 scenes ago
        
        scene['weight'] = scene_weight
        # Add weight metadata to each chunk
        for chunk in scene['chunks']:
            chunk['scene_weight'] = scene_weight
            chunk['scene_idx'] = scene_idx
    
    # Identify which scene the current timestamp (t_now) belongs to
    # This helps match dialogue to the correct scene
    current_scene_idx = len(scenes) - 1  # Default to most recent
    for idx, scene in enumerate(scenes):
        if scene['t_start'] <= t_now <= scene['t_end'] + 5:  # 5s buffer
            current_scene_idx = idx
            scene['is_current'] = True
        else:
            scene['is_current'] = False
    
    # Extract character names from dialogue patterns (focus on current scene)
    characters_present = set()
    current_scene = scenes[current_scene_idx] if scenes else None
    if current_scene:
        for chunk in current_scene['chunks']:
            text = chunk.get("text", "")
            if chunk.get("cue_type") == "dialogue":
                # Look for name mentions in dialogue (e.g., "Answer the question, Patrick")
                import re
                # Common name patterns - capitalize words that might be names
                potential_names = re.findall(r'\b([A-Z][a-z]+)\b', text)
                for name in potential_names:
                    if name not in ['I', 'A', 'The', 'And', 'Or', 'But', 'So', 'If']:
                        characters_present.add(name)
    
    # Flatten all chunks with their weights for LLM context
    all_weighted_chunks = []
    for scene in scenes:
        all_weighted_chunks.extend(scene['chunks'])
    
    print(f"[temporal_context] Detected {len(scenes)} scene(s) in {window_seconds}s window")
    if len(scenes) > 1:
        print(f"[temporal_context] Current scene: {current_scene_idx}, spans {current_scene['t_start']:.1f}-{current_scene['t_end']:.1f}s")
    
    return {
        "recent_dialogue": all_weighted_chunks,  # All chunks with scene_weight metadata
        "characters_present": characters_present,
        "scene_boundary_detected": len(scene_boundaries) > 0,
        "scenes": scenes,
        "current_scene_idx": current_scene_idx
    }


def generate_response(query: str, hits: List[Hit], t_now: float, spoiler_mode: str, film_id: str = None, enriched_scene: dict = None) -> str:
    """Generate a conversational response using LLM based on retrieved chunks and temporal context.
    
    Args:
        query: User's question
        hits: List of retrieved subtitle chunks
        t_now: Current playback time
        spoiler_mode: "on" or "off"
        film_id: Film identifier
        enriched_scene: Optional enriched scene data from vector store (can answer even without hits)
    """
    if not LLM_ENABLED:
        print("[LLM] LLM_ENABLED is False - returning None")
        return None
    
    # Allow LLM call if we have either hits OR enriched scene data
    if not hits and not enriched_scene:
        print("[LLM] No hits and no enriched scene - returning None")
        return None
    
    if not openai_client:
        print("[LLM] OpenAI client is None - returning error")
        return "⚠️ OpenAI client not initialized. Check server logs."

    # Use the enriched_scene passed as parameter (already fetched in search)
    # This avoids double-fetching the same scene data
    
    # Build CURRENT SCENE CONTEXT
    # IMPORTANT: Prioritize subtitle-based context (temporally accurate)
    # Use enriched data as supplementary info only
    
    # Always build subtitle context (temporal ground truth)
    # Use 45-second window to reduce cross-scene contamination
    temporal_ctx = get_temporal_context(film_id, t_now, window_seconds=45) if film_id else {"recent_dialogue": [], "characters_present": set(), "scenes": []}
    
    # Build scene-aware subtitle context
    scenes = temporal_ctx.get("scenes", [])
    current_scene_idx = temporal_ctx.get("current_scene_idx", 0)
    
    if scenes:
        # Multi-scene context: show each scene separately
        scene_parts = []
        for idx, scene in enumerate(scenes):
            is_current = (idx == current_scene_idx)
            scene_marker = "🎬 CURRENT SCENE" if is_current else f"📽️ Previous Scene ({scene['weight']:.1f} relevance)"
            
            scene_lines = []
            for chunk in scene['chunks'][-10:]:  # Last 10 chunks per scene
                ts = chunk.get("t_start", 0)
                mins, secs = int(ts // 60), int(ts % 60)
                time_fmt = f"{mins}:{secs:02d}"
                text = chunk.get("text", "")
                cue_type = chunk.get("cue_type", "")
                
                # Format differently for dialogue vs non-verbal
                if cue_type == "dialogue":
                    scene_lines.append(f"[{time_fmt}] {text}")
                elif cue_type == "nonverbal" and len(text) < 50:
                    scene_lines.append(f"[{time_fmt}] ({text})")
            
            if scene_lines:
                scene_parts.append(f"{scene_marker}:\n" + "\n".join(scene_lines))
        
        subtitle_context = "\n\n".join(scene_parts)
    else:
        # Fallback: single scene or no scenes
        current_scene_parts = []
        for chunk in temporal_ctx["recent_dialogue"][-10:]:
            ts = chunk.get("t_start", 0)
            mins, secs = int(ts // 60), int(ts % 60)
            time_fmt = f"{mins}:{secs:02d}"
            text = chunk.get("text", "")
            cue_type = chunk.get("cue_type", "")
            
            if cue_type == "dialogue":
                current_scene_parts.append(f"[{time_fmt}] {text}")
            elif cue_type == "nonverbal" and len(text) < 50:
                current_scene_parts.append(f"[{time_fmt}] ({text})")
        
        subtitle_context = "\n".join(current_scene_parts) if current_scene_parts else "No recent dialogue available."
    
    # Add enriched character data if available and relevant
    if enriched_scene:
        location = enriched_scene.get('location', 'Unknown')
        characters_present = enriched_scene.get('characters_present', [])
        character_details = enriched_scene.get('character_details', {})
        
        # Format character information
        character_info_parts = []
        for char_name in characters_present:
            if char_name in character_details:
                details = character_details[char_name]
                full_name = details.get('full_name', char_name)
                actor = details.get('actor')
                
                char_line = f"  • {full_name}"
                if actor:
                    char_line += f" (played by {actor})"
                character_info_parts.append(char_line)
        
        character_info = "\n".join(character_info_parts) if character_info_parts else ""
        
        # Combine: Subtitle context (primary) + Enriched data (supplementary)
        current_scene_context = f"""RECENT DIALOGUE (what's actually happening now):
{subtitle_context}

ADDITIONAL CHARACTER INFO (from script analysis):
Location in script: {location}
{character_info if character_info else "(No character details available for this moment)"}"""
        
        print(f"[LLM] Using hybrid context: Subtitles + enriched data ({location})")
        
    else:
        # Fall back to subtitle context only (no enriched data)
        current_scene_context = subtitle_context
        print(f"[LLM] Using subtitle context only (no enriched data)")
    
    # Build SEMANTIC SEARCH RESULTS (RAG hits)
    relevant_moments_parts = []
    for i, hit in enumerate(hits[:6], 1):  # Use top 6 hits
        mins, secs = int(hit.t_start // 60), int(hit.t_start % 60)
        time_fmt = f"{mins}:{secs:02d}"
        
        # Check if this is from the current scene (within last 60s)
        is_current = (t_now - 60 <= hit.t_end <= t_now)
        marker = "📍 CURRENT SCENE" if is_current else ""
        
        cue_info = f"[{hit.cue_type}]" if hit.cue_type else ""
        relevant_moments_parts.append(f"{i}. [{time_fmt}] {cue_info} {marker}\n{hit.text}")
    
    relevant_moments = "\n\n".join(relevant_moments_parts)

    # Format current time for context
    minutes = int(t_now // 60)
    seconds = int(t_now % 60)
    time_str = f"{minutes}:{seconds:02d}"

    # Enhanced system prompt with character awareness
    if enriched_scene:
        character_context_note = """
CHARACTERS IN CURRENT SCENE - Use this to identify "that guy", "her", "the woman", etc.:
The "Characters in this scene" section shows EXACTLY who is on screen right now with their full details.
When someone asks "who's that guy?" or similar vague questions, check the character list for the current scene."""
    else:
        character_context_note = """
Note: This film uses basic subtitle context (no character metadata available).
Do your best to identify characters from dialogue patterns."""

    # Check if multi-scene context is present
    has_multiple_scenes = len(scenes) > 1
    scene_context_note = ""
    if has_multiple_scenes:
        scene_context_note = f"""
MULTI-SCENE CONTEXT:
The dialogue below shows {len(scenes)} different scenes from the last 45 seconds.
The viewer is currently watching the scene marked "🎬 CURRENT SCENE" at {time_str}.
Previous scenes are shown with lower relevance weights - use them for context but NOT for "who is this?" questions."""
    
    system_prompt = f"""You are FilmBuddy, a friendly and knowledgeable movie companion chatbot. You help viewers understand and engage with the movie they're watching.

Current playback time: {time_str} ({t_now:.0f} seconds into the film)
Spoiler mode: {spoiler_mode}

{character_context_note}
{scene_context_note}

CRITICAL: SCENE AWARENESS AND RECENCY
⚠️ For character identification questions ("who is this?", "who are they?", "who are these two?"):
- ONLY use dialogue marked "🎬 CURRENT SCENE" - this is what the viewer sees RIGHT NOW
- If you see multiple scenes, IGNORE previous scenes (📽️) for character identification
- Look at the LAST 2-3 dialogue entries in the CURRENT SCENE only
- The current scene may only have 5-10 seconds of dialogue - that's okay, focus on it
- If the current scene dialogue lacks clear character indicators, check "Characters in this scene" metadata
- If BOTH current dialogue AND metadata are unclear, say you're uncertain rather than guessing

IMPORTANT RULES:
1. **Prioritize Current Scene**: When you see "🎬 CURRENT SCENE", that's the ONLY dialogue happening right now
2. For vague references like "that guy", "her", "the woman", "these two":
   - Find the "🎬 CURRENT SCENE" section
   - Read ONLY the dialogue in that current scene
   - Check if character names are mentioned there
   - Use "Characters in this scene" metadata if available AND it matches the timing
   - Be specific: "That's [Character Name], played by [Actor], who is [role]"
3. Previous scenes (📽️) provide context for plot/backstory questions but NOT for "who is this?" questions
4. The "Relevant Moments" provide additional context but may be from different scenes - use them for plot/theme questions, not "who is this" questions
5. {"Since spoiler mode is OFF, do NOT reveal any plot points, character fates, or events that happen after the current timestamp" if spoiler_mode.lower() == "off" else "Spoiler mode is ON, so you may discuss the full film"}
6. Be conversational and engaging, like a friend watching the movie with the viewer
7. **If you can't confidently identify characters from CURRENT SCENE dialogue, say so honestly** - don't use previous scenes to guess
8. Keep responses concise but informative (2-4 sentences typically)
9. When identifying characters, mention both their character name AND the actor's name"""

    user_prompt = f"""CURRENT SCENE (what's happening right now):
{current_scene_context}

---

RELEVANT MOMENTS (semantic search results from the film):
{relevant_moments}

---

User's question: {query}

Please answer the question using the context above. Pay special attention to the CURRENT SCENE section for identifying "who" or "what" the user is referring to."""

    try:
        print(f"[LLM] Calling Azure OpenAI with deployment: {OPENAI_MODEL}")
        print(f"[LLM] System prompt length: {len(system_prompt)}, User prompt length: {len(user_prompt)}")
        
        response = openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        
        answer = response.choices[0].message.content
        print(f"[LLM] Success! Generated response length: {len(answer)}")
        return answer
        
    except Exception as e:
        error_msg = str(e)
        error_type = type(e).__name__
        print(f"[LLM Error] {error_type}: {error_msg}")
        
        # Return a more informative error message
        if "api_key" in error_msg.lower() or "authentication" in error_msg.lower() or "401" in error_msg:
            key_name = "AZURE_OPENAI_API_KEY" if USE_AZURE else "OPENAI_API_KEY"
            return f"⚠️ Authentication failed (401). Check your {key_name} in .env file."
        elif "rate" in error_msg.lower() or "quota" in error_msg.lower() or "429" in error_msg:
            return "⚠️ API rate limit or quota exceeded. Try again later."
        elif "model" in error_msg.lower() or "deployment" in error_msg.lower() or "404" in error_msg:
            setting_name = "AZURE_OPENAI_DEPLOYMENT_NAME" if USE_AZURE else "FILMBUDDY_LLM_MODEL"
            return f"⚠️ Model/Deployment '{LLM_MODEL}' not found. Check your {setting_name} setting."
        else:
            return f"⚠️ LLM Error ({error_type}): {error_msg[:150]}..."

@app.get("/ping")
def ping():
    enriched_films = vector_store.list_movies() if vector_store else []
    return {
        "ok": True,
        "llm_enabled": LLM_ENABLED,
        "vector_store_enabled": vector_store is not None,
        "available_films": list(film_data.keys()),
        "enriched_films": enriched_films
    }

@app.get("/films")
def list_films():
    """List all available films with metadata"""
    films = []
    for film_id, data in film_data.items():
        payloads = data["payloads"]
        # Try to get a display name from the film_id
        display_name = film_id.replace('_', ' ').title()
        has_enriched = vector_store and vector_store.has_movie(film_id)
        films.append({
            "film_id": film_id,
            "display_name": display_name,
            "num_chunks": len(payloads),
            "duration_seconds": max(r["t_end"] for r in payloads) if payloads else 0,
            "has_enriched_corpus": has_enriched
        })
    return {"films": films}

@app.get("/movie/{movie_id}/scene")
def get_scene_at_timestamp(
    movie_id: str,
    timestamp: float = Query(..., description="Playback time in seconds"),
    buffer: float = Query(5.0, description="Timestamp tolerance in seconds")
):
    """
    Get the enriched scene at a specific timestamp.
    
    Returns scene with:
    - Location and scene header
    - Characters present with full details (name, actor, gender, role)
    - Scene summary
    - Dialogue excerpt
    - Alignment metadata
    """
    if not vector_store:
        raise HTTPException(
            status_code=503,
            detail="Vector store not available. Enriched corpus features disabled."
        )
    
    scene = vector_store.query_scene_at_timestamp(movie_id, timestamp, buffer)
    
    if not scene:
        raise HTTPException(
            status_code=404,
            detail=f"No scene found at timestamp {timestamp}s for movie '{movie_id}'"
        )
    
    return scene

@app.get("/movie/{movie_id}/characters")
def get_movie_characters(movie_id: str):
    """
    Get all character metadata for a movie.
    
    Returns dict of character_name → character_details including:
    - Full name
    - Actor name
    - Gender
    - Role (protagonist/antagonist/supporting/minor)
    - Description
    - Occupation
    """
    if not vector_store:
        raise HTTPException(
            status_code=503,
            detail="Vector store not available. Enriched corpus features disabled."
        )
    
    characters = vector_store.get_all_characters(movie_id)
    
    if not characters:
        raise HTTPException(
            status_code=404,
            detail=f"No character data found for movie '{movie_id}'. May not have enriched corpus."
        )
    
    return {"movie_id": movie_id, "characters": characters}

# ---------- Movie Title Matching ----------
def normalize_title(title: str) -> str:
    """Normalize a title for comparison."""
    import re
    # Lowercase
    title = title.lower()
    # Remove punctuation except spaces
    title = re.sub(r'[^\w\s]', '', title)
    # Remove extra whitespace
    title = ' '.join(title.split())
    return title

def compute_title_similarity(title1: str, title2: str) -> float:
    """Compute similarity between two titles using simple token overlap."""
    tokens1 = set(normalize_title(title1).split())
    tokens2 = set(normalize_title(title2).split())

    if not tokens1 or not tokens2:
        return 0.0

    # Jaccard similarity
    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)

    return intersection / union if union > 0 else 0.0

@app.get("/match-title")
def match_title(title: str = Query(..., description="The movie title to match")):
    """
    Fuzzy match a detected movie title against available films in the corpus.
    Returns the best matching film_id and confidence score.
    """
    if not title or not title.strip():
        return {"matched_film_id": None, "confidence": 0.0, "display_name": None}

    title = title.strip()
    best_match = None
    best_score = 0.0
    best_display_name = None

    for film_id in film_data.keys():
        # Convert film_id to display name for comparison
        display_name = film_id.replace('_', ' ').title()

        # Compute similarity
        score = compute_title_similarity(title, display_name)

        # Also try matching against the raw film_id
        score_raw = compute_title_similarity(title, film_id.replace('_', ' '))
        score = max(score, score_raw)

        if score > best_score:
            best_score = score
            best_match = film_id
            best_display_name = display_name

    # Only return a match if confidence is above threshold
    CONFIDENCE_THRESHOLD = 0.4

    if best_score >= CONFIDENCE_THRESHOLD:
        return {
            "matched_film_id": best_match,
            "confidence": round(best_score, 3),
            "display_name": best_display_name
        }
    else:
        return {
            "matched_film_id": None,
            "confidence": round(best_score, 3) if best_score > 0 else 0.0,
            "display_name": None
        }

# ---------- General Chat (No RAG) ----------
class ChatRequest(BaseModel):
    query: str = Field(..., example="What are some good romantic comedies?")
    context: Optional[str] = Field(None, description="Optional context about what the user is watching")

class ChatResponse(BaseModel):
    answer: str
    llm_enabled: bool

@app.post("/chat", response_model=ChatResponse)
def general_chat(req: ChatRequest):
    """
    General film discussion without RAG context.
    Used when the user is watching an unknown/unsupported movie.
    """
    if not LLM_ENABLED or not openai_client:
        return ChatResponse(
            answer="LLM is not configured. Please set OPENAI_API_KEY in your .env file.",
            llm_enabled=False
        )

    system_prompt = """You are FilmBuddy, a friendly and knowledgeable movie companion chatbot.
You help viewers understand and engage with movies and TV shows.

Since you don't have specific context about what the user is currently watching,
provide helpful general information about films, actors, directors, genres, and filmmaking.

Be conversational and engaging, like a film-enthusiast friend. Keep responses concise but informative."""

    user_prompt = req.query
    if req.context:
        user_prompt = f"Context: {req.context}\n\nQuestion: {req.query}"

    try:
        response = openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )

        answer = response.choices[0].message.content
        return ChatResponse(answer=answer, llm_enabled=True)

    except Exception as e:
        error_msg = str(e)
        return ChatResponse(
            answer=f"Sorry, I encountered an error: {error_msg[:100]}",
            llm_enabled=True
        )

# ---------- Core search ----------
def compute_temporal_score(t_end: float, t_now: float) -> float:
    """Compute temporal proximity score using exponential decay."""
    time_diff = max(0, t_now - t_end)  # How long ago was this chunk
    return math.exp(-time_diff / TEMPORAL_DECAY)

def is_deictic_query(query: str) -> bool:
    """
    Detect deictic questions - queries about current scene ("who is this?", "what's happening here?").
    These require strong temporal grounding.
    """
    import re
    deictic_patterns = [
        r'\bwho (is|are|was|were|\'s) (this|that|these|those|he|she|they|the guy|the woman|the man|the girl)\b',
        r'\bwhat (is|are|was|were|\'s) (this|that|happening|going on)\b',
        r'\bwhere (is|are|was|were) (this|that|he|she|they)\b',
        r'\bwho are (the |these |those )?two\b',
        r'\bwho\'s (that|this|the)\b',
    ]
    query_lower = query.lower()
    return any(re.search(pattern, query_lower) for pattern in deictic_patterns)

def search(query: str, film_id: str, t_now: float, spoiler_mode: str, top_k: int) -> AskResponse:
    # Check if film exists
    if film_id not in film_data:
        raise HTTPException(
            status_code=404, 
            detail=f"Film '{film_id}' not found. Available: {list(film_data.keys())}"
        )
    
    # Get film-specific data
    payloads = film_data[film_id]["payloads"]
    embeddings = film_data[film_id]["embeddings"]
    
    # Detect deictic queries ("who is this?") and adjust temporal weighting
    is_deictic = is_deictic_query(query)
    temporal_weight = 0.6 if is_deictic else TEMPORAL_WEIGHT  # Boost temporal for deictic queries
    
    if is_deictic:
        print(f"[search] Deictic query detected: '{query}' - boosting temporal weight to {temporal_weight}")
    
    # 1) embed query
    q = model.encode([query], normalize_embeddings=True).astype("float32")[0]  # (d,)
    # 2) cosine similarities (dot product because normalized)
    sims = embeddings @ q  # shape (N,)
    # 3) take global top-N candidates
    num_candidates = min(MAX_CANDIDATES, len(payloads))
    cand_idx = np.argpartition(sims, -num_candidates)[-num_candidates:]

    # 4) filter by spoiler gate and compute combined scores
    candidates = []
    for idx in cand_idx:
        r = payloads[idx]
        # spoiler time gate - use t_start instead of t_end
        # A chunk is a spoiler if it STARTS after the current time
        t_start = r.get("t_start", 0)
        t_end = r.get("t_end", 0)
        if spoiler_mode.lower() == "off" and t_start > t_now:
            continue

        # Compute combined score: semantic + temporal + cue_type
        semantic_score = float(sims[idx])
        temporal_score = compute_temporal_score(t_end, t_now)

        # Apply cue type weight (penalize nonverbal, boost dialogue)
        cue_type = r.get("cue_type", "dialogue")
        cue_weight = CUE_TYPE_WEIGHTS.get(cue_type, 0.5)

        # Combined score with cue type adjustment (use dynamic temporal_weight)
        base_score = (1 - temporal_weight) * semantic_score + temporal_weight * temporal_score
        combined_score = base_score * cue_weight

        candidates.append({
            "idx": idx,
            "r": r,
            "semantic_score": semantic_score,
            "temporal_score": temporal_score,
            "cue_weight": cue_weight,
            "combined_score": combined_score
        })

    # 5) Sort by combined score and take top_k
    candidates.sort(key=lambda x: x["combined_score"], reverse=True)

    hits: List[Hit] = []
    for cand in candidates[:top_k]:
        r = cand["r"]
        hit = Hit(
            t_start=float(r["t_start"]),
            t_end=float(r["t_end"]),
            source_type=r.get("source_type", "subtitles"),
            cue_type=r.get("cue_type"),
            text=r.get("text", ""),
            speakers=r.get("speakers", []),
            score=cand["combined_score"],  # Now reflects combined score
            film_id=r.get("film_id", ""),
            idx=int(cand["idx"]),
        )
        hits.append(hit)

    # 6) validation
    validation = {
        "num_candidates": int(len(cand_idx)),
        "num_filtered_candidates": len(candidates),
        "num_hits": int(len(hits)),
        "time_gate_enforced": (spoiler_mode.lower() == "off"),
        "all_t_start_le_t_now": all(h.t_start <= t_now for h in hits) if spoiler_mode.lower() == "off" else None,
        "temporal_weight": temporal_weight,  # Use actual weight (may be boosted for deictic)
        "temporal_decay_seconds": TEMPORAL_DECAY,
        "is_deictic_query": is_deictic
    }
    note = "spoiler_mode=off; kept only chunks with t_start ≤ t_now" if spoiler_mode.lower() == "off" else "spoiler_mode=on; future chunks allowed"

    # 6) Get enriched scene data if available
    enriched_scene = None
    if vector_store:
        # Map film_id to enriched movie_id
        enriched_id = film_id_to_enriched_id.get(film_id, film_id)
        if vector_store.has_movie(enriched_id):
            try:
                enriched_scene = vector_store.query_scene_at_timestamp(enriched_id, t_now)
                if enriched_scene:
                    # Validate enriched scene against subtitle hits
                    # If alignment confidence is low, don't use it
                    confidence = enriched_scene.get('alignment_confidence', 0)
                    if confidence < 0.5:
                        print(f"[search] ⚠ Enriched scene has low confidence ({confidence:.2f}), skipping")
                        enriched_scene = None
                    else:
                        print(f"[search] ✓ Retrieved enriched scene: {enriched_scene.get('location', 'unknown')} (confidence: {confidence:.2f})")
            except Exception as e:
                print(f"[search] Warning: Could not retrieve enriched scene: {e}")
    
    # 7) Generate LLM response (pass enriched scene so LLM can answer even without subtitle hits)
    answer = generate_response(query, hits, t_now, spoiler_mode, film_id, enriched_scene)

    return AskResponse(
        answer=answer,
        hits=hits,
        note=note,
        film_id=film_id,
        t_now=t_now,
        spoiler_mode=spoiler_mode,
        top_k=top_k,
        validation=validation,
        llm_enabled=LLM_ENABLED,
        current_scene=enriched_scene
    )

@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    k = req.top_k or TOPK_DEFAULT
    if k < 1 or k > 20:
        raise HTTPException(status_code=400, detail="top_k must be between 1 and 20")
    return search(
        query=req.query,
        film_id=req.film_id,
        t_now=float(req.t_now),
        spoiler_mode=req.spoiler_mode,
        top_k=int(k),
    )

@app.get("/debug/window")
def debug_window(
    film_id: str,
    t_now: float = Query(..., description="center time (s)"),
    delta: float = Query(10.0, description="+/- window in seconds"),
    limit: int = Query(50, description="max rows")
):
    if film_id not in film_data:
        raise HTTPException(
            status_code=404, 
            detail=f"Film '{film_id}' not found. Available: {list(film_data.keys())}"
        )
    
    payloads = film_data[film_id]["payloads"]
    rows = []
    lo, hi = t_now - delta, t_now + delta
    for i, r in enumerate(payloads):
        ts = float(r.get("t_start", -1e18)); te = float(r.get("t_end", 1e18))
        if (ts <= hi + EPS) and (te >= lo - EPS):
            rows.append({
                "idx": i,
                "t_start": ts,
                "t_end": te,
                "cue_type": r.get("cue_type"),
                "text": r.get("text", "")[:140] + ("…" if len(r.get("text","")) > 140 else "")
            })
    rows.sort(key=lambda x: x["t_start"])
    return {"film_id": film_id, "t_now": t_now, "window": [lo, hi], "rows": rows[:limit]}