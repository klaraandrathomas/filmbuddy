#!/usr/bin/env python3
"""
Generalized movie corpus builder with optimizations.

Runs both pipelines for adding a new movie to FilmBuddy:
  1. Subtitle chunk generation (for server semantic search)
  2. Enriched corpus building (for character metadata + scene summaries)

Usage:
    python -m preprocessing.process_movie \
        --title "Forrest Gump" \
        --script scripts/forrestgump_script.txt \
        --subtitles data/forrestgump.srt \
        --year 1994

    python -m preprocessing.process_movie --batch movies.json

    python -m preprocessing.process_movie \
        --title "Forrest Gump" \
        --script scripts/forrestgump_script.txt \
        --subtitles data/forrestgump.srt \
        --year 1994 \
        --force

Optimizations:
    - Command-line arguments instead of hardcoded movie data
    - Incremental update detection via file checksums
    - Corpus quality validation with detailed metrics
    - Batch processing from JSON config
    - Configurable temporal parameters
"""

import asyncio
import argparse
import sys
import os
import glob as globmod
import hashlib
import json
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from preprocessing.corpus_builder import MovieCorpusBuilder
from preprocessing.vector_store import MovieVectorStore
from scripts.build_time_aware_corpus import parse_srt_file, chunk_cues, write_jsonl


def compute_file_hash(filepath: str) -> str:
    """Compute SHA256 hash of file for change detection."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def check_incremental_update(
    title_slug: str,
    movie_id: str,
    script_hash: str,
    subtitle_hash: str,
    cache_dir: str = "corpus",
) -> bool:
    """Check if corpus needs rebuilding based on file hashes.

    Searches for cache files matching both the exact movie_id and any
    file matching the title slug (e.g. .forrest_gump_*_cache.json) so
    that a TMDB-resolved year cache is found even when --year is omitted.

    Returns True if rebuild needed, False if cached version is valid.
    """
    exact = os.path.join(cache_dir, f".{movie_id}_cache.json")
    # Match only {title_slug}_{4-digit-year} and {title_slug}_unknown to
    # avoid prefix collisions (e.g. the_matrix matching the_matrix_reloaded).
    glob_matches = sorted(
        globmod.glob(os.path.join(cache_dir, f".{title_slug}_[0-9][0-9][0-9][0-9]_cache.json"))
        + globmod.glob(os.path.join(cache_dir, f".{title_slug}_unknown_cache.json"))
    )
    candidates = list(dict.fromkeys([exact] + glob_matches))

    for cache_file in candidates:
        if not os.path.exists(cache_file):
            continue
        try:
            with open(cache_file, "r") as f:
                cache = json.load(f)
            if (
                cache.get("script_hash") == script_hash
                and cache.get("subtitle_hash") == subtitle_hash
            ):
                cached_id = os.path.basename(cache_file)[1:].replace(
                    "_cache.json", ""
                )
                print(f"Cache valid for {cached_id}, skipping rebuild")
                return False
        except Exception:
            continue

    return True


def save_cache(
    movie_id: str, script_hash: str, subtitle_hash: str, cache_dir: str = "corpus"
) -> None:
    """Save file hashes to cache for incremental update detection."""
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f".{movie_id}_cache.json")
    with open(cache_file, "w") as f:
        json.dump(
            {"script_hash": script_hash, "subtitle_hash": subtitle_hash},
            f,
        )


def validate_corpus_quality(corpus: dict) -> dict:
    """Validate corpus quality and return metrics.

    Checks for duplicate timestamps, low-confidence alignments,
    and alignment method distribution.
    """
    scenes = corpus["scenes"]

    timestamp_map: dict[str, int] = {}
    duplicates: list[tuple[str, int, int]] = []
    for scene in scenes:
        ts_key = f"{scene['t_start']:.1f}-{scene['t_end']:.1f}"
        if ts_key in timestamp_map:
            duplicates.append((ts_key, timestamp_map[ts_key], scene["scene_id"]))
        timestamp_map[ts_key] = scene["scene_id"]

    confidences = [s.get("alignment_confidence", 0) for s in scenes]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0
    low_confidence_scenes = [
        s for s in scenes if s.get("alignment_confidence", 0) < 0.6
    ]

    anchor_count = sum(
        1 for s in scenes if s.get("alignment_method") == "anchor_match"
    )
    interpolated_count = sum(
        1 for s in scenes if s.get("alignment_method") == "interpolated"
    )

    metrics = {
        "total_scenes": len(scenes),
        "duplicate_timestamps": len(duplicates),
        "avg_confidence": avg_confidence,
        "low_confidence_count": len(low_confidence_scenes),
        "anchor_matches": anchor_count,
        "interpolated": interpolated_count,
        "anchor_rate": anchor_count / len(scenes) * 100 if scenes else 0,
    }

    print()
    print("=" * 70)
    print("QUALITY VALIDATION")
    print("=" * 70)

    if duplicates:
        print(f"WARNING: {len(duplicates)} duplicate timestamps found")
        for ts, s1, s2 in duplicates[:3]:
            print(f"   {ts}: Scene {s1} and Scene {s2}")
    else:
        print("No duplicate timestamps")

    print(f"\nAlignment Statistics:")
    print(f"   Anchor matches: {anchor_count} ({metrics['anchor_rate']:.1f}%)")
    print(f"   Interpolated: {interpolated_count}")
    print(f"   Avg confidence: {avg_confidence:.3f}")

    if low_confidence_scenes:
        print(
            f"\n{len(low_confidence_scenes)} scenes with low confidence (<0.6):"
        )
        for scene in low_confidence_scenes[:5]:
            print(
                f"   Scene {scene['scene_id']}: "
                f"{scene.get('alignment_confidence', 0):.3f} - "
                f"{scene.get('location', 'unknown')}"
            )
        if len(low_confidence_scenes) > 5:
            print(f"   ... and {len(low_confidence_scenes) - 5} more")

    return metrics


def build_subtitle_chunks(
    subtitle_path: str,
    film_id: str,
    output_dir: str = "corpus",
    max_gap_sec: float = 6.0,
    max_chars: int = 1200,
) -> str:
    """Build subtitle chunk corpus for server semantic search.

    Generates the {film_id}_chunks.jsonl file that the server loads at startup.
    """
    print(f"\n[Subtitle Chunks] Parsing {subtitle_path}...")
    cues = parse_srt_file(subtitle_path)
    print(f"[Subtitle Chunks] Parsed {len(cues)} raw cues")

    chunks = chunk_cues(
        cues,
        max_gap_sec=max_gap_sec,
        max_chars=max_chars,
        remove_hoh=True,
        remove_speaker_label=False,
        allow_cross_type_merge=False,
        drop_metadata=True,
    )
    print(f"[Subtitle Chunks] Merged into {len(chunks)} chunks")

    out_path = os.path.join(output_dir, f"{film_id}_chunks.jsonl")
    write_jsonl(chunks, film_id, out_path)
    return out_path


async def process_movie(
    title: str,
    script_path: str,
    subtitle_path: str,
    year: Optional[int] = None,
    force_rebuild: bool = False,
    output_dir: str = "corpus",
    max_gap_sec: float = 6.0,
    max_chars: int = 1200,
) -> Optional[dict]:
    """Process a single movie through both pipelines.

    Pipeline 1 (Subtitle Chunks):
        Generates {film_id}_chunks.jsonl for server semantic search.

    Pipeline 2 (Enriched Corpus):
        Generates {movie_id}_enriched.jsonl, {movie_id}_metadata.json,
        and stores in ChromaDB vector store.

    Args:
        title: Movie title for TMDB lookup
        script_path: Path to screenplay .txt file
        subtitle_path: Path to .srt subtitle file
        year: Optional release year for TMDB disambiguation
        force_rebuild: Skip cache check and rebuild
        output_dir: Directory for output files
        max_gap_sec: Max gap (seconds) to merge consecutive subtitle cues
        max_chars: Max characters per merged subtitle chunk
    """
    print("=" * 70)
    print(f"PROCESSING: {title}")
    print("=" * 70)
    print()

    if not os.path.exists(script_path):
        print(f"Script file not found: {script_path}")
        return None

    if not os.path.exists(subtitle_path):
        print(f"Subtitle file not found: {subtitle_path}")
        return None

    print(f"Script: {script_path}")
    print(f"Subtitles: {subtitle_path}")
    if year:
        print(f"Year: {year}")
    print()

    script_hash = compute_file_hash(script_path)
    subtitle_hash = compute_file_hash(subtitle_path)

    title_slug = title.lower().replace(" ", "_").replace("'", "")
    year_str = str(year) if year else "unknown"
    movie_id = f"{title_slug}_{year_str}"
    film_id = title_slug

    if not force_rebuild and not check_incremental_update(
        title_slug, movie_id, script_hash, subtitle_hash, output_dir
    ):
        print("Corpus is up-to-date, skipping rebuild.")
        print("Use --force to rebuild anyway.")
        return "cached"

    pipeline_start = time.time()

    print("-" * 70)
    print("PIPELINE 1: Subtitle Chunks")
    print("-" * 70)
    chunks_path = build_subtitle_chunks(
        subtitle_path,
        film_id,
        output_dir=output_dir,
        max_gap_sec=max_gap_sec,
        max_chars=max_chars,
    )

    print()
    print("-" * 70)
    print("PIPELINE 2: Enriched Corpus")
    print("-" * 70)

    try:
        builder = MovieCorpusBuilder(use_improved_aligner=True)
        print("Corpus builder initialized")
        print()
    except ValueError as e:
        print(f"Failed to initialize corpus builder: {e}")
        print()
        print("Make sure your .env file has:")
        print("  - TMDB_API_KEY")
        print("  - AZURE_OPENAI_API_KEY")
        print("  - AZURE_OPENAI_ENDPOINT")
        return None

    try:
        print("Starting enrichment pipeline...")
        print()

        corpus = await builder.build_corpus(
            movie_title=title,
            script_path=script_path,
            subtitle_path=subtitle_path,
            release_year=year,
            output_dir=output_dir,
        )

        print()
        print("Enriched corpus building complete!")
        print()

        metrics = validate_corpus_quality(corpus)

        save_cache(corpus["movie_id"], script_hash, subtitle_hash, output_dir)

        print("\nStoring in vector database...")
        vector_store = MovieVectorStore(persist_directory="./chroma_db")
        vector_store.store_movie_corpus(corpus)
        print("Stored in ChromaDB")

        total_time = time.time() - pipeline_start

        print()
        print("=" * 70)
        print("SUCCESS")
        print("=" * 70)
        print()
        print(f"Movie ID: {corpus['movie_id']}")
        print(f"Film ID (server): {film_id}")
        print(f"Scenes: {len(corpus['scenes'])}")
        print(f"Characters: {len(corpus['characters'])}")
        print(f"Total processing time: {total_time:.1f}s")
        print()
        print("Files created:")
        print(f"  {chunks_path}")
        print(f"  {output_dir}/{corpus['movie_id']}_enriched.jsonl")
        print(f"  {output_dir}/{corpus['movie_id']}_metadata.json")
        print()
        print("Next steps:")
        print("  1. Restart the server to load the new corpus:")
        print("     uvicorn server.main:app --reload")
        print(f"  2. The film will be available as film_id='{film_id}'")
        print()

        return corpus

    except Exception as e:
        print()
        print(f"Error during enriched corpus processing: {e}")
        import traceback

        traceback.print_exc()
        return None


async def batch_process(
    movies_file: str,
    force_rebuild: bool = False,
    output_dir: str = "corpus",
    max_gap_sec: float = 6.0,
    max_chars: int = 1200,
) -> None:
    """Process multiple movies from a JSON config file.

    Config format:
    [
        {
            "title": "Forrest Gump",
            "script": "scripts/forrestgump_script.txt",
            "subtitles": "data/forrestgump.srt",
            "year": 1994
        },
        ...
    ]
    """
    with open(movies_file, "r") as f:
        movies = json.load(f)

    print(f"Processing {len(movies)} movies in batch mode...")
    print()

    results: list[dict[str, object]] = []
    for movie in movies:
        result = await process_movie(
            title=movie["title"],
            script_path=movie["script"],
            subtitle_path=movie["subtitles"],
            year=movie.get("year"),
            force_rebuild=force_rebuild,
            output_dir=output_dir,
            max_gap_sec=max_gap_sec,
            max_chars=max_chars,
        )
        if result == "cached":
            status = "cached"
        elif result is not None:
            status = "ok"
        else:
            status = "failed"
        results.append({"title": movie["title"], "status": status})
        print()

    ok_count = sum(1 for r in results if r["status"] == "ok")
    cached_count = sum(1 for r in results if r["status"] == "cached")
    failed_count = sum(1 for r in results if r["status"] == "failed")
    print(
        f"Batch complete: {ok_count} built, "
        f"{cached_count} cached, "
        f"{failed_count} failed "
        f"(out of {len(movies)})"
    )
    for r in results:
        label = {"ok": "OK", "cached": "CACHED", "failed": "FAILED"}[r["status"]]
        print(f"  [{label}] {r['title']}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build subtitle chunks and enriched corpus for a movie.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single movie
  python -m preprocessing.process_movie \\
      --title "Forrest Gump" \\
      --script scripts/forrestgump_script.txt \\
      --subtitles data/forrestgump.srt \\
      --year 1994

  # Batch processing
  python -m preprocessing.process_movie --batch movies.json

  # Force rebuild (ignore cache)
  python -m preprocessing.process_movie \\
      --title "Forrest Gump" \\
      --script scripts/forrestgump_script.txt \\
      --subtitles data/forrestgump.srt \\
      --year 1994 --force
        """,
    )

    parser.add_argument("--title", help="Movie title (for TMDB lookup)")
    parser.add_argument("--script", help="Path to screenplay .txt file")
    parser.add_argument("--subtitles", help="Path to subtitle .srt file")
    parser.add_argument("--year", type=int, help="Release year (optional, for TMDB disambiguation)")
    parser.add_argument(
        "--force", action="store_true", help="Force rebuild even if cached"
    )
    parser.add_argument(
        "--batch", help="Process multiple movies from a JSON config file"
    )
    parser.add_argument(
        "--output-dir",
        default="corpus",
        help="Output directory for corpus files (default: corpus)",
    )
    parser.add_argument(
        "--max-gap",
        type=float,
        default=6.0,
        help="Max gap in seconds to merge consecutive subtitle cues (default: 6.0)",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=1200,
        help="Max characters per merged subtitle chunk (default: 1200)",
    )

    args = parser.parse_args()

    if args.batch:
        asyncio.run(
            batch_process(
                args.batch,
                force_rebuild=args.force,
                output_dir=args.output_dir,
                max_gap_sec=args.max_gap,
                max_chars=args.max_chars,
            )
        )
    elif args.title and args.script and args.subtitles:
        asyncio.run(
            process_movie(
                title=args.title,
                script_path=args.script,
                subtitle_path=args.subtitles,
                year=args.year,
                force_rebuild=args.force,
                output_dir=args.output_dir,
                max_gap_sec=args.max_gap,
                max_chars=args.max_chars,
            )
        )
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
