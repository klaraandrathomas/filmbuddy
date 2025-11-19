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
CORPUS_PATH = os.environ.get("FILMBUDDY_CORPUS", "corpus/la_la_land_chunks.jsonl")
EMB_MODEL = os.environ.get("FILMBUDDY_EMB_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
TOPK_DEFAULT = int(os.environ.get("FILMBUDDY_TOPK", "6"))
MAX_CANDIDATES = int(os.environ.get("FILMBUDDY_MAXCANDS", "128"))  # search breadth before filtering
EPS = 1e-6  # tolerance for float comparisons
STRICT_START_GATE = os.environ.get("FILMBUDDY_STRICT_START_GATE", "0") == "1"

# Temporal boosting configuration
TEMPORAL_WEIGHT = float(os.environ.get("FILMBUDDY_TEMPORAL_WEIGHT", "0.5"))  # Weight for temporal proximity (0-1)
TEMPORAL_DECAY = float(os.environ.get("FILMBUDDY_TEMPORAL_DECAY", "180"))  # Decay window in seconds (3 min)

# Cue type scoring penalties (reduce score for less useful content types)
CUE_TYPE_WEIGHTS = {
    "dialogue": 1.0,      # Full score for dialogue
    "lyric": 0.8,         # Slightly lower for lyrics
    "nonverbal": 0.3,     # Heavy penalty for sound effects
    "metadata": 0.1,      # Almost ignore metadata
}

# OpenAI Configuration
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL = os.environ.get("FILMBUDDY_LLM_MODEL", "gpt-4o")
LLM_ENABLED = OPENAI_API_KEY is not None

# Initialize OpenAI client
openai_client = OpenAI(api_key=OPENAI_API_KEY) if LLM_ENABLED else None

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
payloads: List[Dict[str, Any]] = []
embeddings: np.ndarray = None
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
    global payloads, embeddings, model
    if not os.path.exists(CORPUS_PATH):
        raise RuntimeError(f"Corpus JSONL not found at {CORPUS_PATH}")
    payloads = load_jsonl(CORPUS_PATH)
    texts = [r["text"] for r in payloads]
    model = SentenceTransformer(EMB_MODEL)
    embs = model.encode(texts, batch_size=64, show_progress_bar=True, normalize_embeddings=True)
    embeddings = embs.astype("float32")
    # Optional: sanity check order
    for i, r in enumerate(payloads):
        if not (isinstance(r.get("t_start"), (int, float)) and isinstance(r.get("t_end"), (int, float))):
            raise RuntimeError(f"Record {i} missing t_start/t_end")
    print(f"[startup] Loaded {len(payloads)} chunks from {CORPUS_PATH}. Embedding dim={embeddings.shape[1]}")
    if LLM_ENABLED:
        print(f"[startup] LLM generation enabled with model: {OPENAI_MODEL}")
    else:
        print("[startup] LLM generation disabled (no OPENAI_API_KEY set)")

# ---------- LLM Generation ----------
def generate_response(query: str, hits: List[Hit], t_now: float, spoiler_mode: str) -> str:
    """Generate a conversational response using GPT-4o based on retrieved chunks."""
    if not LLM_ENABLED or not hits:
        return None

    # Build context from retrieved chunks
    context_parts = []
    for i, hit in enumerate(hits[:5], 1):  # Use top 5 hits for context
        timestamp = f"[{hit.t_start:.0f}s - {hit.t_end:.0f}s]"
        speakers = f" ({', '.join(hit.speakers)})" if hit.speakers else ""
        cue_info = f" [{hit.cue_type}]" if hit.cue_type else ""
        context_parts.append(f"{i}. {timestamp}{speakers}{cue_info}\n{hit.text}")

    context = "\n\n".join(context_parts)

    # Format current time for context
    minutes = int(t_now // 60)
    seconds = int(t_now % 60)
    time_str = f"{minutes}:{seconds:02d}"

    system_prompt = f"""You are FilmBuddy, a friendly and knowledgeable movie companion chatbot. You help viewers understand and engage with the movie they're watching.

Current playback time: {time_str} ({t_now:.0f} seconds into the film)
Spoiler mode: {spoiler_mode}

IMPORTANT RULES:
1. Only use information from the provided context - do not make up details
2. {"Since spoiler mode is OFF, do NOT reveal any plot points, character fates, or events that happen after the current timestamp" if spoiler_mode.lower() == "off" else "Spoiler mode is ON, so you may discuss the full film"}
3. Be conversational and engaging, like a friend watching the movie with the viewer
4. Reference specific moments with timestamps when helpful (e.g., "Around 2:30...")
5. If the context doesn't contain enough information to answer, say so honestly
6. Keep responses concise but informative (2-4 sentences typically)"""

    user_prompt = f"""Context from the movie (timestamps shown):

{context}

User's question: {query}

Please provide a helpful, conversational response based on the context above."""

    try:
        response = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"[LLM Error] {e}")
        return f"I encountered an error generating a response. Here are the relevant movie moments I found."

@app.get("/ping")
def ping():
    return {"ok": True, "llm_enabled": LLM_ENABLED}

# ---------- Core search ----------
def compute_temporal_score(t_end: float, t_now: float) -> float:
    """Compute temporal proximity score using exponential decay."""
    time_diff = max(0, t_now - t_end)  # How long ago was this chunk
    return math.exp(-time_diff / TEMPORAL_DECAY)

def search(query: str, film_id: str, t_now: float, spoiler_mode: str, top_k: int) -> AskResponse:
    # 1) embed query
    q = model.encode([query], normalize_embeddings=True).astype("float32")[0]  # (d,)
    # 2) cosine similarities (dot product because normalized)
    sims = embeddings @ q  # shape (N,)
    # 3) take global top-N candidates
    cand_idx = np.argpartition(sims, -MAX_CANDIDATES)[-MAX_CANDIDATES:]

    # 4) filter by film_id and spoiler gate, then compute combined scores
    candidates = []
    for idx in cand_idx:
        r = payloads[idx]
        if r.get("film_id") != film_id:
            continue
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
    answer = generate_response(query, hits, t_now, spoiler_mode)

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
    rows = []
    lo, hi = t_now - delta, t_now + delta
    for i, r in enumerate(payloads):
        if r.get("film_id") != film_id:
            continue
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