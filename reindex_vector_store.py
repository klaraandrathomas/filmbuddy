#!/usr/bin/env python3
"""
Re-index the vector store with the enriched corpus (including synthetic scenes).

This script simply loads the enriched corpus and stores it in ChromaDB,
without rebuilding the corpus from scratch.
"""

import sys
import os
import json
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from preprocessing.vector_store import MovieVectorStore

def main():
    print("="*70)
    print("RE-INDEXING VECTOR STORE WITH ENRICHED CORPUS")
    print("="*70)
    print()
    
    # Initialize vector store
    print("[1/3] Initializing ChromaDB vector store...")
    vs = MovieVectorStore('./chroma_db')
    print("  ✓ Vector store ready")
    print()
    
    # Load enriched corpus with synthetic scenes
    print("[2/3] Loading enriched corpus with synthetic scenes...")
    enriched_path = 'corpus/10_things_i_hate_about_you_1999_enriched_with_synthetic.jsonl'
    
    if not os.path.exists(enriched_path):
        print(f"  ✗ File not found: {enriched_path}")
        print("  Run fill_corpus_gaps.py first to generate synthetic scenes")
        return 1
    
    scenes = []
    with open(enriched_path, 'r', encoding='utf-8') as f:
        for line in f:
            scene = json.loads(line)
            scenes.append(scene)
    
    print(f"  ✓ Loaded {len(scenes)} scenes")
    
    # Count synthetic vs original
    synthetic_count = sum(1 for s in scenes if s.get('synthetic', False))
    print(f"    - Original scenes: {len(scenes) - synthetic_count}")
    print(f"    - Synthetic scenes: {synthetic_count}")
    print()
    
    # Load character metadata
    print("[3/3] Loading character metadata...")
    metadata_path = 'chroma_db/10_things_i_hate_about_you_1999_corpus_meta.json'
    
    characters = {}
    metadata = {}
    
    if os.path.exists(metadata_path):
        with open(metadata_path, 'r', encoding='utf-8') as f:
            meta = json.loads(f.read())
            characters = meta.get('characters', {})
            metadata = meta.get('metadata', {})
        print(f"  ✓ Loaded {len(characters)} characters")
    else:
        print(f"  ⚠ No metadata file found (will use empty characters)")
    print()
    
    # Build corpus object
    corpus = {
        'movie_id': '10_things_i_hate_about_you_1999',
        'scenes': scenes,
        'characters': characters,
        'metadata': metadata
    }
    
    # Store in vector database
    print("Storing corpus in ChromaDB...")
    print("  (This will delete and recreate the collection)")
    vs.store_movie_corpus(corpus)
    print()
    
    print("="*70)
    print("✅ RE-INDEXING COMPLETE!")
    print("="*70)
    print(f"  Movie: 10_things_i_hate_about_you_1999")
    print(f"  Total scenes indexed: {len(scenes)}")
    print(f"  Characters: {len(characters)}")
    print()
    print("Restart your server to use the updated vector store:")
    print("  uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())


