# FilmBuddy

A time-aware film companion chatbot that helps viewers understand movies without spoilers.

## Features

- **Time-aware RAG**: Retrieves context based on current playback timestamp
- **Spoiler prevention**: Filters responses to only include content up to current position
- **Deictic query handling**: Understands "who's that?" style questions using scene context
- **Enriched corpus**: Character metadata, scene summaries, and TMDB cast data
- **Chrome extension**: Content script overlay that appears on streaming sites

## Project Structure

```
filmbuddy/
├── server/              # FastAPI backend with RAG + LLM
├── extension/           # Chrome extension (content script overlay)
├── preprocessing/       # Corpus building pipeline
├── corpus/              # Processed movie corpora (.jsonl)
├── chroma_db/           # ChromaDB vector store
├── scripts/             # Movie script files
├── data/                # Raw subtitle files (.srt)
├── tests/               # Test suite
├── .env.example         # Environment template
└── requirements.txt     # Python dependencies
```

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your API keys (Azure OpenAI or OpenAI, TMDB)
```

### 3. Run the server

```bash
uvicorn server.main:app --reload --port 8000
```

### 4. Install the Chrome extension

1. Go to `chrome://extensions/`
2. Enable "Developer mode"
3. Click "Load unpacked" and select the `extension/` folder

## API

```bash
# Health check
curl http://localhost:8000/ping

# Ask a question
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"film_id":"la_la_land","t_now":1200,"query":"Who is that?","spoiler_mode":"off"}'
```

## Configuration

| Variable | Description |
|----------|-------------|
| `AZURE_OPENAI_API_KEY` | Azure OpenAI key |
| `AZURE_OPENAI_ENDPOINT` | Azure endpoint URL |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | Model deployment name |
| `OPENAI_API_KEY` | OpenAI key (alternative to Azure) |
| `TMDB_API_KEY` | TMDB API key for cast metadata |

## Tech Stack

- **Backend**: FastAPI
- **Vector Store**: ChromaDB
- **Embeddings**: sentence-transformers (all-MiniLM-L6-v2)
- **LLM**: Azure OpenAI / OpenAI GPT-4
- **Extension**: Chrome Manifest V3, content script

## License

MIT
