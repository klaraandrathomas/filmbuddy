"""
FilmBuddy Preprocessing Pipeline

This module provides tools for building enriched movie corpora by combining:
- Movie scripts (scene structure, characters, dialogue)
- TMDB API data (cast, metadata, actor-character mapping)
- Subtitle files (timestamp alignment)
- LLM extraction (character metadata, scene summaries)

The enriched corpus enables FilmBuddy to answer vague deictic questions
like "who's that guy?" by knowing which characters are present in each scene.
"""

__all__ = []

# Import implemented modules (others will be added as they are implemented)
try:
    from preprocessing.tmdb_client import TMDBClient
    __all__.append("TMDBClient")
except ImportError:
    pass

try:
    from preprocessing.script_parser import ScriptParser
    __all__.append("ScriptParser")
except ImportError:
    pass

try:
    from preprocessing.character_extractor import CharacterExtractor
    __all__.append("CharacterExtractor")
except ImportError:
    pass

try:
    from preprocessing.timestamp_aligner import TimestampAligner
    __all__.append("TimestampAligner")
except ImportError:
    pass

try:
    from preprocessing.corpus_builder import MovieCorpusBuilder
    __all__.append("MovieCorpusBuilder")
except ImportError:
    pass

try:
    from preprocessing.vector_store import MovieVectorStore
    __all__.append("MovieVectorStore")
except ImportError:
    pass

