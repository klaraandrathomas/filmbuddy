# server/main.py
# pip install fastapi uvicorn[standard] sentence-transformers numpy pydantic ujson python-multipart openai python-dotenv

from fastapi import FastAPI, HTTPException,  Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import os, json, ujson, math
import numpy as np
from sentence_transformers import SentenceTransformer
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

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

# LLM Configuration (supports both OpenAI and LiteLLM)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
LITELLM_API_KEY = os.environ.get("LITELLM_API_KEY")
LITELLM_API_BASE = os.environ.get("LITELLM_API_BASE")
OPENAI_MODEL = os.environ.get("FILMBUDDY_LLM_MODEL", "gpt-4o")

# Determine which API key to use
api_key = LITELLM_API_KEY or OPENAI_API_KEY
LLM_ENABLED = api_key is not None

# Initialize OpenAI client (works with LiteLLM base_url too)
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
    global film_data, model
    
    if not os.path.exists(CORPUS_DIR):
        raise RuntimeError(f"Corpus directory not found at {CORPUS_DIR}")
    
    # Load embedding model once
    model = SentenceTransformer(EMB_MODEL)
    
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
    
    if LLM_ENABLED:
        print(f"[startup] LLM generation enabled with model: {OPENAI_MODEL}")
        if LITELLM_API_KEY:
            print(f"[startup] Using LiteLLM with base: {LITELLM_API_BASE}")
            print(f"[startup] LiteLLM API key: {LITELLM_API_KEY[:7]}...{LITELLM_API_KEY[-4:]}")
        elif OPENAI_API_KEY:
            print(f"[startup] Using OpenAI API key: sk-...{OPENAI_API_KEY[-4:]}")
    else:
        print("[startup] LLM generation disabled (no OPENAI_API_KEY or LITELLM_API_KEY set)")

# ---------- LLM Generation ----------
def get_temporal_context(film_id: str, t_now: float, window_seconds: float = 60) -> Dict[str, Any]:
    """Get recent dialogue and scene context around current timestamp."""
    if film_id not in film_data:
        return {"recent_dialogue": [], "characters_present": set()}
    
    payloads = film_data[film_id]["payloads"]
    
    # Get chunks from the last 60 seconds (or custom window)
    recent_chunks = []
    for chunk in payloads:
        # Only include chunks that END within our window before current time
        if t_now - window_seconds <= chunk["t_end"] <= t_now:
            recent_chunks.append(chunk)
    
    # Sort by timestamp
    recent_chunks.sort(key=lambda x: x["t_start"])
    
    # Extract character names from dialogue patterns
    # Look for patterns like "Character:" or "- Character -" or capitalized names at start
    characters_present = set()
    for chunk in recent_chunks[-10:]:  # Focus on last 10 chunks
        text = chunk.get("text", "")
        # Simple heuristic: extract capitalized words that might be names
        # This is basic - could be enhanced with NER or character list
        if chunk.get("cue_type") == "dialogue":
            # Look for dialogue attribution patterns
            lines = text.split('\n')
            for line in lines:
                # Skip stage directions in parentheses
                if line.strip().startswith('(') or line.strip().startswith('<i>('):
                    continue
                # Add actual dialogue as indication someone is speaking
                if line.strip() and not line.strip().startswith('-'):
                    characters_present.add("multiple characters")  # Generic placeholder
    
    return {
        "recent_dialogue": recent_chunks[-10:],  # Last 10 chunks
        "characters_present": characters_present
    }


def generate_response(query: str, hits: List[Hit], t_now: float, spoiler_mode: str, film_id: str = None) -> str:
    """Generate a conversational response using LLM based on retrieved chunks and temporal context."""
    if not LLM_ENABLED:
        print("[LLM] LLM_ENABLED is False - returning None")
        return None
    
    if not hits:
        print("[LLM] No hits provided - returning None")
        return None
    
    if not openai_client:
        print("[LLM] OpenAI client is None - returning error")
        return "⚠️ OpenAI client not initialized. Check server logs."

    # Get temporal context (recent scene info)
    temporal_ctx = get_temporal_context(film_id, t_now) if film_id else {"recent_dialogue": [], "characters_present": set()}
    
    # Build CURRENT SCENE CONTEXT (last 30-60 seconds of dialogue)
    current_scene_parts = []
    for chunk in temporal_ctx["recent_dialogue"][-8:]:  # Last 8 chunks from recent scene
        ts = chunk.get("t_start", 0)
        mins, secs = int(ts // 60), int(ts % 60)
        time_fmt = f"{mins}:{secs:02d}"
        text = chunk.get("text", "")
        cue_type = chunk.get("cue_type", "")
        
        # Format differently for dialogue vs non-verbal
        if cue_type == "dialogue":
            current_scene_parts.append(f"[{time_fmt}] {text}")
        elif cue_type == "nonverbal" and len(text) < 50:
            current_scene_parts.append(f"[{time_fmt}] ({text})")
    
    current_scene_context = "\n".join(current_scene_parts) if current_scene_parts else "No recent dialogue available."
    
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

    system_prompt = f"""You are FilmBuddy, a friendly and knowledgeable movie companion chatbot. You help viewers understand and engage with the movie they're watching.

Current playback time: {time_str} ({t_now:.0f} seconds into the film)
Spoiler mode: {spoiler_mode}

IMPORTANT RULES:
1. Use BOTH the current scene context AND relevant moments to answer questions
2. For vague references like "that guy" or "her" - use the CURRENT SCENE CONTEXT to identify who's on screen
3. The "Current Scene" shows what just happened (last 30-60 seconds) - this is what the viewer is seeing NOW
4. The "Relevant Moments" are semantically similar content that might provide additional context
5. {"Since spoiler mode is OFF, do NOT reveal any plot points, character fates, or events that happen after the current timestamp" if spoiler_mode.lower() == "off" else "Spoiler mode is ON, so you may discuss the full film"}
6. Be conversational and engaging, like a friend watching the movie with the viewer
7. If you can't identify who/what they're referring to, say so honestly - don't guess
8. Keep responses concise but informative (2-4 sentences typically)"""

    user_prompt = f"""CURRENT SCENE (what's happening right now):
{current_scene_context}

---

RELEVANT MOMENTS (semantic search results from the film):
{relevant_moments}

---

User's question: {query}

Please answer the question using the context above. Pay special attention to the CURRENT SCENE section for identifying "who" or "what" the user is referring to."""

    try:
        print(f"[LLM] Calling OpenAI API with model: {OPENAI_MODEL}")
        print(f"[LLM] System prompt length: {len(system_prompt)}, User prompt length: {len(user_prompt)}")
        
        response = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
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
            return "⚠️ OpenAI API key issue. Please check your .env file has a valid OPENAI_API_KEY."
        elif "rate" in error_msg.lower() or "quota" in error_msg.lower() or "429" in error_msg:
            return "⚠️ OpenAI API rate limit or quota exceeded. Here are the relevant movie moments I found:"
        elif "model" in error_msg.lower() or "404" in error_msg:
            return f"⚠️ Model '{OPENAI_MODEL}' not available. Please check your FILMBUDDY_LLM_MODEL setting."
        else:
            return f"⚠️ Error ({error_type}): {error_msg[:150]}. Here are the relevant movie moments I found:"

@app.get("/ping")
def ping():
    return {"ok": True, "llm_enabled": LLM_ENABLED, "available_films": list(film_data.keys())}

@app.get("/films")
def list_films():
    """List all available films with metadata"""
    films = []
    for film_id, data in film_data.items():
        payloads = data["payloads"]
        films.append({
            "film_id": film_id,
            "num_chunks": len(payloads),
            "duration_seconds": max(r["t_end"] for r in payloads) if payloads else 0
        })
    return {"films": films}

# ---------- Core search ----------
def compute_temporal_score(t_end: float, t_now: float) -> float:
    """Compute temporal proximity score using exponential decay."""
    time_diff = max(0, t_now - t_end)  # How long ago was this chunk
    return math.exp(-time_diff / TEMPORAL_DECAY)

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
        # spoiler time gate
        t_end = r.get("t_end", float("inf"))
        if spoiler_mode.lower() == "off" and t_end > t_now:
            continue

        # Compute combined score: semantic + temporal + cue_type
        semantic_score = float(sims[idx])
        temporal_score = compute_temporal_score(t_end, t_now)

        # Apply cue type weight (penalize nonverbal, boost dialogue)
        cue_type = r.get("cue_type", "dialogue")
        cue_weight = CUE_TYPE_WEIGHTS.get(cue_type, 0.5)

        # Combined score with cue type adjustment
        base_score = (1 - TEMPORAL_WEIGHT) * semantic_score + TEMPORAL_WEIGHT * temporal_score
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
        "all_t_end_le_t_now": all(h.t_end <= t_now for h in hits) if spoiler_mode.lower() == "off" else None,
        "temporal_weight": TEMPORAL_WEIGHT,
        "temporal_decay_seconds": TEMPORAL_DECAY
    }
    note = "spoiler_mode=off; kept only chunks with t_end ≤ t_now" if spoiler_mode.lower() == "off" else "spoiler_mode=on; future chunks allowed"

    # 6) Generate LLM response
    answer = generate_response(query, hits, t_now, spoiler_mode, film_id)

    return AskResponse(
        answer=answer,
        hits=hits,
        note=note,
        film_id=film_id,
        t_now=t_now,
        spoiler_mode=spoiler_mode,
        top_k=top_k,
        validation=validation,
        llm_enabled=LLM_ENABLED
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