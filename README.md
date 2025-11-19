# FilmBuddy

An interactive, time-aware film companion chatbot that helps viewers engage with movies without spoilers.

## Features

- **Time-aware RAG**: Retrieves relevant movie context based on current playback timestamp
- **Spoiler prevention**: Filters responses to only include content up to current viewing position
- **LLM-powered responses**: Generates conversational answers using GPT-4o
- **Semantic search**: Uses sentence-transformers for intelligent content retrieval
- **Browser extension**: Chrome sidebar that extracts video timestamps automatically

## Project Structure

```
filmbuddy/
├── server/
│   └── main.py                 # FastAPI backend with RAG + LLM generation
├── extension/                  # Chrome browser extension
│   ├── manifest.json           # Extension configuration
│   ├── sidepanel.html/js/css   # Sidebar UI
│   ├── content.js              # Video timestamp extraction
│   ├── background.js           # Service worker (message routing)
│   └── icons/                  # Extension icons
├── scripts/
│   └── build_time_aware_corpus.py  # Subtitle parser and corpus builder
├── corpus/
│   └── la_la_land_chunks.jsonl     # Processed subtitle corpus
├── data/
│   └── *.srt                   # Raw subtitle files
├── .env.example                # Environment template
├── .env                        # Your local config (not in git)
└── requirements.txt            # Python dependencies
```

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and add your OpenAI API key
# OPENAI_API_KEY=sk-your-api-key-here
```

### 3. Run the server

```bash
uvicorn server.main:app --reload --port 8000
```

### 4. Install the browser extension

1. Open Chrome and go to `chrome://extensions/`
2. Enable "Developer mode" (toggle in top right)
3. Click "Load unpacked"
4. Select the `extension/` folder from this project
5. The FilmBuddy icon will appear in your toolbar

**Note:** You need to create icon files (see `extension/icons/README.md`)

### 5. Use the extension

1. Make sure the backend server is running
2. Navigate to a video page (Netflix, YouTube, etc.)
3. Click the FilmBuddy icon to open the sidebar
4. Ask questions about what you're watching!

## API Usage

### Health check
```bash
curl http://localhost:8000/ping
```

### Ask a question
```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "film_id": "la_la_land",
    "t_now": 1200,
    "query": "What just happened?",
    "spoiler_mode": "off"
  }'
```

### Response format
```json
{
  "answer": "LLM-generated conversational response...",
  "hits": [...],
  "llm_enabled": true,
  "spoiler_mode": "off",
  "t_now": 1200
}
```

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `OPENAI_API_KEY` | (required) | Your OpenAI API key |
| `FILMBUDDY_LLM_MODEL` | `gpt-4o` | LLM model for generation |
| `FILMBUDDY_CORPUS` | `corpus/la_la_land_chunks.jsonl` | Path to corpus file |
| `FILMBUDDY_TOPK` | `6` | Number of chunks to retrieve |

## Building a Corpus

To process a new movie's subtitles:

```bash
python scripts/build_time_aware_corpus.py \
  --input data/movie.srt \
  --output corpus/movie_chunks.jsonl \
  --film-id movie_name
```

## Tech Stack

- **Backend**: FastAPI + Uvicorn
- **Frontend**: Chrome Extension (Manifest V3, Side Panel API)
- **Embeddings**: sentence-transformers (all-MiniLM-L6-v2)
- **LLM**: OpenAI GPT-4o
- **Data**: JSONL corpus with timestamps

## License

MIT
