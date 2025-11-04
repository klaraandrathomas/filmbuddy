# FilmBuddy 
An interactive, time-aware film companion chatbot.

## Structure
- `scripts/build_time_aware_corpus.py`: parses `.srt` subtitle files into timestamped JSONL chunks.
- `corpus/`: contains the processed subtitle corpora.
- `server/main.py`: FastAPI backend providing `/ask` endpoint for RAG retrieval.

## Run locally
```bash
uvicorn server.main:app --reload --port 8000
