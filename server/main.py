# server/main.py
# pip install fastapi uvicorn[standard] sentence-transformers numpy pydantic ujson python-multipart

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import os, json, ujson, math
import numpy as np
from sentence_transformers import SentenceTransformer

# ---------- Config ----------
CORPUS_PATH = os.environ.get("FILMBUDDY_CORPUS", "corpus/la_la_land_chunks.jsonl")
EMB_MODEL = os.environ.get("FILMBUDDY_EMB_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
TOPK_DEFAULT = int(os.environ.get("FILMBUDDY_TOPK", "6"))
MAX_CANDIDATES = int(os.environ.get("FILMBUDDY_MAXCANDS", "128"))  # search breadth before filtering

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
    hits: List[Hit]
    note: str
    film_id: str
    t_now: float
    spoiler_mode: str
    top_k: int
    validation: Dict[str, Any]

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

@app.get("/ping")
def ping():
    return {"ok": True}

# ---------- Core search ----------
def search(query: str, film_id: str, t_now: float, spoiler_mode: str, top_k: int) -> AskResponse:
    # 1) embed query
    q = model.encode([query], normalize_embeddings=True).astype("float32")[0]  # (d,)
    # 2) cosine similarities (dot product because normalized)
    sims = embeddings @ q  # shape (N,)
    # 3) take global top-N candidates
    cand_idx = np.argpartition(sims, -MAX_CANDIDATES)[-MAX_CANDIDATES:]
    # sort candidates by score desc
    cand_idx = cand_idx[np.argsort(sims[cand_idx])[::-1]]

    # 4) filter by film_id and spoiler gate
    hits: List[Hit] = []
    kept = 0
    for idx in cand_idx:
        r = payloads[idx]
        if r.get("film_id") != film_id:
            continue
        # spoiler time gate
        if spoiler_mode.lower() == "off" and r.get("t_end", float("inf")) > t_now:
            continue
        hit = Hit(
            t_start=float(r["t_start"]),
            t_end=float(r["t_end"]),
            source_type=r.get("source_type", "subtitles"),
            cue_type=r.get("cue_type"),
            text=r.get("text", ""),
            speakers=r.get("speakers", []),
            score=float(sims[idx]),
            film_id=r.get("film_id", ""),
            idx=int(idx),
        )
        hits.append(hit)
        kept += 1
        if kept >= top_k:
            break

    # 5) validation
    validation = {
        "num_candidates": int(len(cand_idx)),
        "num_hits": int(len(hits)),
        "time_gate_enforced": (spoiler_mode.lower() == "off"),
        "all_t_end_le_t_now": all(h.t_end <= t_now for h in hits) if spoiler_mode.lower() == "off" else None
    }
    note = "spoiler_mode=off; kept only chunks with t_end ≤ t_now" if spoiler_mode.lower() == "off" else "spoiler_mode=on; future chunks allowed"

    return AskResponse(
        hits=hits,
        note=note,
        film_id=film_id,
        t_now=t_now,
        spoiler_mode=spoiler_mode,
        top_k=top_k,
        validation=validation
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
