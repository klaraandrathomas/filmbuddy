# FilmBuddy

## Quick Start

### Prerequisites

- Python

### Installation

```bash
# Clone repository 
git clone 

# Install dependencies
pip install fastapi "uvicorn[standard]" sentence-transformers numpy pydantic ujson
```

### Run Pipeline Test

```bash
# Generate test data
python scripts/build_time_aware_corpus.py

# backend
uvicorn server.main:app --reload --port 8000
