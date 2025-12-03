#!/usr/bin/env python3
"""
Process "10 Things I Hate About You" through enrichment pipeline.

This script will:
1. Parse the screenplay
2. Fetch TMDB metadata (cast, runtime)
3. Extract character metadata via Azure OpenAI
4. Align scenes to subtitle timestamps
5. Generate scene summaries
6. Build enriched corpus
7. Save to corpus/ and load into vector store
"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from preprocessing.corpus_builder import MovieCorpusBuilder
from preprocessing.vector_store import MovieVectorStore


async def main():
    """Process 10 Things I Hate About You."""
    print("="*70)
    print("10 THINGS I HATE ABOUT YOU - Enriched Corpus Builder")
    print("="*70)
    print()
    print("This will use Azure OpenAI to build an enriched corpus with:")
    print("  • Character metadata (names, actors, roles)")
    print("  • Scene summaries")
    print("  • Timestamp alignment")
    print("  • TMDB integration")
    print()
    
    # Check if files exist
    script_path = Path("scripts/10thingsihateaboutyou_script.txt")
    subtitle_path = Path("data/10thingsihateaboutyou.srt")
    
    if not script_path.exists():
        print(f"❌ Script not found: {script_path}")
        return 1
    
    if not subtitle_path.exists():
        print(f"❌ Subtitles not found: {subtitle_path}")
        return 1
    
    print(f"✓ Script found: {script_path}")
    print(f"✓ Subtitles found: {subtitle_path}")
    print()
    
    # Initialize builder
    try:
        builder = MovieCorpusBuilder()
        print("✓ Corpus builder initialized")
        print()
    except ValueError as e:
        print(f"❌ Failed to initialize: {e}")
        print()
        print("Make sure your .env file has:")
        print("  - TMDB_API_KEY")
        print("  - AZURE_OPENAI_API_KEY")
        print("  - AZURE_OPENAI_ENDPOINT")
        return 1
    
    # Run the pipeline
    try:
        print("Starting enrichment pipeline...")
        print("(This may take 3-5 minutes)")
        print()
        
        corpus = await builder.build_corpus(
            movie_title="10 Things I Hate About You",
            script_path=str(script_path),
            subtitle_path=str(subtitle_path),
            release_year=1999,
            output_dir="corpus"
        )
        
        print()
        print("="*70)
        print("✅ Corpus building complete!")
        print("="*70)
        print()
        
        # Display summary
        print("Summary:")
        print(f"  Movie ID: {corpus['movie_id']}")
        print(f"  Scenes: {len(corpus['scenes'])}")
        print(f"  Characters: {len(corpus['characters'])}")
        print(f"  Processing time: {corpus['stats']['total_time']:.1f}s")
        print()
        
        # Show some characters
        main_chars = [(k, v) for k, v in corpus['characters'].items() if v.get('actor')][:5]
        if main_chars:
            print("Main characters:")
            for name, info in main_chars:
                print(f"  • {name}: {info['actor']}")
        print()
        
        # Store in vector database
        print("Storing in vector database...")
        vector_store = MovieVectorStore(persist_directory="./chroma_db")
        vector_store.store_movie_corpus(corpus)
        print("✓ Stored in ChromaDB")
        print()
        
        print("="*70)
        print("🎉 SUCCESS!")
        print("="*70)
        print()
        print("Your enriched corpus is ready!")
        print()
        print("Files created:")
        print(f"  • corpus/{corpus['movie_id']}_enriched.jsonl")
        print(f"  • corpus/{corpus['movie_id']}_metadata.json")
        print()
        print("Next steps:")
        print("  1. Restart the server to load the new corpus:")
        print("     uvicorn server.main:app --reload")
        print("  2. Open Netflix with '10 Things I Hate About You'")
        print("  3. Use the FilmBuddy extension to ask questions!")
        print()
        
        return 0
        
    except Exception as e:
        print()
        print(f"❌ Error during processing: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

