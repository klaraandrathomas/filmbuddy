"""
Movie Corpus Builder (Orchestrator)

Orchestrates the full preprocessing pipeline:
1. Fetch TMDB metadata (cast, runtime)
2. Parse script into structured scenes
3. Extract character metadata via LLM
4. Merge TMDB and script character data
5. Align scenes to subtitle timestamps
6. Generate scene summaries
7. Build enriched chunks
8. Save to JSONL format

Produces scene-aware corpus with character details for each timestamp.
"""

import os
import json
import asyncio
import time
from pathlib import Path
from typing import Optional
from rapidfuzz import fuzz

from preprocessing.tmdb_client import TMDBClient
from preprocessing.script_parser import ScriptParser
from preprocessing.character_extractor import CharacterExtractor
from preprocessing.timestamp_aligner import TimestampAligner
from preprocessing.improved_aligner import ImprovedTimestampAligner


class MovieCorpusBuilder:
    """Orchestrates the full corpus building pipeline."""
    
    def __init__(self, use_improved_aligner: bool = True):
        """
        Initialize all preprocessing components.
        
        Args:
            use_improved_aligner: If True, use ImprovedTimestampAligner (recommended).
                                 If False, use legacy TimestampAligner.
        """
        self.tmdb = TMDBClient()
        self.parser = ScriptParser()
        self.extractor = CharacterExtractor()
        
        # Choose aligner
        if use_improved_aligner:
            self.aligner = ImprovedTimestampAligner(
                anchor_threshold=0.85,
                fuzzy_threshold=0.75,
                min_phrase_words=4
            )
            self.aligner_name = "ImprovedTimestampAligner"
        else:
            self.aligner = TimestampAligner()
            self.aligner_name = "TimestampAligner (legacy)"
        
        print(f"[CorpusBuilder] Using {self.aligner_name}")
    
    async def build_corpus(
        self,
        movie_title: str,
        script_path: str,
        subtitle_path: str,
        release_year: int = None,
        output_dir: str = "corpus"
    ) -> dict:
        """
        Build complete enriched corpus for a movie.
        
        Args:
            movie_title: Movie title for TMDB lookup
            script_path: Path to screenplay .txt file
            subtitle_path: Path to .srt file
            release_year: Optional year for TMDB disambiguation
            output_dir: Where to save output files
        
        Returns:
            dict with keys:
                - movie_id: str (e.g., "la_la_land_2016")
                - metadata: dict (from TMDB)
                - characters: dict (merged TMDB + LLM extraction)
                - scenes: list[dict] (fully enriched scenes)
                - stats: dict (processing statistics)
        
        Pipeline:
            1. Fetch TMDB metadata (cast, runtime)
            2. Parse script into scenes
            3. Extract character metadata via LLM (using Azure OpenAI)
            4. Merge TMDB cast with script characters
            5. Load and parse subtitles
            6. Align scenes to timestamps
            7. Generate scene summaries (LLM, batched for efficiency)
            8. Build final enriched chunks
            9. Save to JSONL and return
        """
        start_time = time.time()
        stats = {
            'total_time': 0,
            'tmdb_time': 0,
            'parse_time': 0,
            'character_extraction_time': 0,
            'alignment_time': 0,
            'summary_time': 0,
            'total_scenes': 0,
            'aligned_scenes': 0,
            'interpolated_scenes': 0,
            'total_characters': 0,
        }
        
        print(f"\n{'='*60}")
        print(f"Building Enriched Corpus for: {movie_title}")
        print(f"{'='*60}\n")
        
        # Step 1: Fetch TMDB metadata
        print("[1/8] Fetching TMDB metadata...")
        step_start = time.time()
        try:
            tmdb_metadata = await self.tmdb.get_movie_metadata(movie_title, release_year)
            stats['tmdb_time'] = time.time() - step_start
            print(f"  ✓ Found: {tmdb_metadata['title']} ({tmdb_metadata['release_year']})")
            print(f"  ✓ Runtime: {tmdb_metadata['runtime_seconds'] / 60:.0f} minutes")
            print(f"  ✓ Cast: {len(tmdb_metadata['characters'])} members")
        except Exception as e:
            print(f"  ✗ TMDB lookup failed: {e}")
            print(f"  ⚠ Continuing without TMDB data...")
            tmdb_metadata = {
                'movie_id': None,
                'title': movie_title,
                'runtime_seconds': 0,
                'release_year': release_year,
                'characters': [],
            }
            stats['tmdb_time'] = time.time() - step_start
        
        # Generate movie_id
        title_slug = movie_title.lower().replace(' ', '_').replace("'", '')
        year_str = str(tmdb_metadata.get('release_year') or release_year or 'unknown')
        movie_id = f"{title_slug}_{year_str}"
        
        # Step 2: Parse script into scenes
        print(f"\n[2/8] Parsing screenplay...")
        step_start = time.time()
        with open(script_path, 'r', encoding='utf-8') as f:
            script_text = f.read()
        
        scenes = self.parser.parse_script(script_text)
        stats['parse_time'] = time.time() - step_start
        stats['total_scenes'] = len(scenes)
        print(f"  ✓ Parsed {len(scenes)} scenes")
        
        # Extract all unique character names from scenes
        all_characters = set()
        for scene in scenes:
            all_characters.update(scene.get('characters', []))
        all_characters = sorted(list(all_characters))
        stats['total_characters'] = len(all_characters)
        print(f"  ✓ Found {len(all_characters)} characters: {', '.join(all_characters[:5])}{'...' if len(all_characters) > 5 else ''}")
        
        # Step 3: Extract character metadata via LLM
        print(f"\n[3/8] Extracting character metadata via LLM...")
        step_start = time.time()
        script_character_metadata = await self.extractor.extract_character_metadata(
            script_text,
            all_characters
        )
        stats['character_extraction_time'] = time.time() - step_start
        print(f"  ✓ Extracted metadata for {len(script_character_metadata)} characters")
        
        # Step 4: Merge TMDB cast with script characters
        print(f"\n[4/8] Merging TMDB and script character data...")
        merged_characters = self._merge_character_data(
            script_character_metadata,
            tmdb_metadata['characters']
        )
        print(f"  ✓ Merged data for {len(merged_characters)} characters")
        
        # Display sample character
        if merged_characters:
            sample_char_name = list(merged_characters.keys())[0]
            sample_char = merged_characters[sample_char_name]
            if sample_char.get('actor'):
                print(f"  ✓ Example: {sample_char['full_name']} played by {sample_char['actor']}")
        
        # Step 5: Load and parse subtitles
        print(f"\n[5/8] Parsing subtitles...")
        subtitles = self.aligner.parse_srt(subtitle_path)
        print(f"  ✓ Parsed {len(subtitles)} subtitle cues")
        print(f"  ✓ Duration: {subtitles[-1]['t_end'] / 60:.1f} minutes")
        
        # Step 6: Align scenes to timestamps
        print(f"\n[6/8] Aligning scenes to timestamps...")
        step_start = time.time()
        aligned_scenes = self.aligner.align_scenes_to_subtitles(scenes, subtitles)
        stats['alignment_time'] = time.time() - step_start
        
        # Count alignment methods
        dialogue_matches = sum(1 for s in aligned_scenes if s.get('alignment_method') == 'dialogue_match')
        interpolated = sum(1 for s in aligned_scenes if s.get('alignment_method') == 'interpolated')
        stats['aligned_scenes'] = dialogue_matches
        stats['interpolated_scenes'] = interpolated
        
        print(f"  ✓ Aligned {len(aligned_scenes)} scenes")
        print(f"    - Dialogue matched: {dialogue_matches} ({dialogue_matches/len(aligned_scenes)*100:.1f}%)")
        print(f"    - Interpolated: {interpolated} ({interpolated/len(aligned_scenes)*100:.1f}%)")
        
        # Step 7: Generate scene summaries
        print(f"\n[7/8] Generating scene summaries via LLM...")
        step_start = time.time()
        summaries = await self.extractor.batch_generate_summaries(
            aligned_scenes,
            merged_characters,
            batch_size=5
        )
        stats['summary_time'] = time.time() - step_start
        print(f"  ✓ Generated {len(summaries)} summaries")
        
        # Step 8: Build final enriched chunks
        print(f"\n[8/8] Building enriched chunks...")
        enriched_scenes = []
        for i, (scene, summary) in enumerate(zip(aligned_scenes, summaries)):
            chunk = self._build_enriched_chunk(
                scene,
                merged_characters,
                summary,
                movie_id
            )
            enriched_scenes.append(chunk)
        
        print(f"  ✓ Built {len(enriched_scenes)} enriched chunks")
        
        # Calculate total time
        stats['total_time'] = time.time() - start_time
        
        # Assemble corpus
        corpus = {
            'movie_id': movie_id,
            'metadata': {
                'title': tmdb_metadata['title'],
                'release_year': tmdb_metadata.get('release_year'),
                'runtime_seconds': tmdb_metadata.get('runtime_seconds'),
                'genres': tmdb_metadata.get('genres', []),
                'overview': tmdb_metadata.get('overview'),
            },
            'characters': merged_characters,
            'scenes': enriched_scenes,
            'stats': stats,
        }
        
        # Save to JSONL
        output_path = self.save_corpus(corpus, output_dir)
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"✅ Corpus Build Complete!")
        print(f"{'='*60}")
        print(f"Movie ID: {movie_id}")
        print(f"Total Scenes: {stats['total_scenes']}")
        print(f"Total Characters: {stats['total_characters']}")
        print(f"Alignment Rate: {dialogue_matches}/{len(aligned_scenes)} ({dialogue_matches/len(aligned_scenes)*100:.1f}%)")
        print(f"Processing Time: {stats['total_time']:.1f}s")
        print(f"Output: {output_path}")
        print(f"{'='*60}\n")
        
        return corpus
    
    def _merge_character_data(
        self, 
        script_characters: dict,  # From LLM extraction
        tmdb_cast: list[dict]     # From TMDB
    ) -> dict:
        """
        Merge character info from both sources.
        
        Challenges:
            - Script may use nickname (MIA), TMDB has full name (Mia Dolan)
            - Script may have minor characters not in TMDB top 20
            - Need fuzzy matching for character names
        
        Strategy:
            1. For each TMDB character, fuzzy match to script characters
            2. Merge fields: script gets priority for description/role
            3. TMDB adds: actor_name, profile_image, billing_order
            4. Script-only characters: keep with "unknown" actor
        
        Returns:
            dict[str, MergedCharacter]
        """
        merged = {}
        
        # Start with script characters (has all characters from script)
        for script_name, script_data in script_characters.items():
            merged[script_name] = {
                'character_name': script_name,
                'full_name': script_data.get('full_name', script_name),
                'gender': script_data.get('gender', 'unknown'),
                'role': script_data.get('role', 'minor'),
                'description': script_data.get('description', ''),
                'occupation': script_data.get('occupation', 'Unknown'),
                'relationships': script_data.get('relationships', {}),
                'actor': None,  # Will be filled from TMDB if available
                'profile_image': None,
                'billing_order': 999,
            }
        
        # Match TMDB cast to script characters using fuzzy matching
        for tmdb_char in tmdb_cast:
            tmdb_char_name = tmdb_char['character_name']
            tmdb_actor = tmdb_char['actor_name']
            
            # Try to find best match in script characters
            best_match = None
            best_score = 0
            
            for script_name in script_characters.keys():
                # Compare character names using fuzzy matching
                score = fuzz.ratio(
                    tmdb_char_name.lower(),
                    script_name.lower()
                ) / 100.0
                
                # Also try comparing with full_name from script
                full_name = script_characters[script_name].get('full_name', script_name)
                score_full = fuzz.ratio(
                    tmdb_char_name.lower(),
                    full_name.lower()
                ) / 100.0
                
                # Use better score
                score = max(score, score_full)
                
                if score > best_score:
                    best_score = score
                    best_match = script_name
            
            # If we found a good match (>= 60% similarity), merge the data
            if best_match and best_score >= 0.6:
                merged[best_match]['actor'] = tmdb_actor
                merged[best_match]['profile_image'] = tmdb_char.get('profile_path')
                merged[best_match]['billing_order'] = tmdb_char.get('order', 999)
                
                # Update gender if TMDB has it and script doesn't
                if tmdb_char.get('gender') != 'unknown' and merged[best_match]['gender'] == 'unknown':
                    merged[best_match]['gender'] = tmdb_char['gender']
            else:
                # No match found in script - add as new character
                # (This handles case where TMDB has characters not in script scenes)
                char_key = tmdb_char_name.upper().replace(' ', '_')
                if char_key not in merged:
                    merged[char_key] = {
                        'character_name': char_key,
                        'full_name': tmdb_char_name,
                        'gender': tmdb_char.get('gender', 'unknown'),
                        'role': 'minor',  # Assume minor if not in script
                        'description': '',
                        'occupation': 'Unknown',
                        'relationships': {},
                        'actor': tmdb_actor,
                        'profile_image': tmdb_char.get('profile_path'),
                        'billing_order': tmdb_char.get('order', 999),
                    }
        
        return merged
    
    def _build_enriched_chunk(
        self, 
        scene: dict, 
        characters: dict,
        summary: str,
        movie_id: str
    ) -> dict:
        """
        Build final chunk format for vector storage.
        
        Returns:
            {
                "chunk_id": "la_la_land_2016_scene_001",
                "movie_id": "la_la_land_2016",
                "source_type": "script",
                "t_start": 204.5,
                "t_end": 287.3,
                
                # Scene info
                "scene_id": 1,
                "scene_header": "INT. COFFEE SHOP - DAY",
                "location": "COFFEE SHOP",
                "time_of_day": "DAY",
                "int_ext": "INT",
                
                # Content
                "summary": "Mia arrives late to her barista job...",
                "dialogue_text": "MIA: Sorry I'm late...",
                "action_text": "Mia enters looking harried...",
                
                # Characters (key for deictic questions!)
                "characters_present": ["MIA", "MANAGER"],
                "character_details": {
                    "MIA": {
                        "full_name": "Mia Dolan",
                        "actor": "Emma Stone",
                        "gender": "female",
                        "role": "protagonist"
                    },
                    ...
                },
                
                # Alignment metadata
                "alignment_confidence": 0.92,
                "alignment_method": "dialogue_match"
            }
        """
        # Format dialogue text
        dialogue_lines = []
        for d in scene.get('dialogue', []):
            char = d.get('character', 'UNKNOWN')
            text = d.get('text', '')
            dialogue_lines.append(f"{char}: {text}")
        dialogue_text = '\n'.join(dialogue_lines)
        
        # Format action text
        action_text = '\n'.join(scene.get('action_lines', []))
        
        # Build character details for characters present in this scene
        characters_present = scene.get('characters', [])
        character_details = {}
        
        for char_name in characters_present:
            if char_name in characters:
                char_data = characters[char_name]
                character_details[char_name] = {
                    'full_name': char_data.get('full_name', char_name),
                    'actor': char_data.get('actor'),
                    'gender': char_data.get('gender', 'unknown'),
                    'role': char_data.get('role', 'minor'),
                    'description': char_data.get('description', ''),
                    'occupation': char_data.get('occupation', 'Unknown'),
                }
        
        # Build chunk
        chunk_id = f"{movie_id}_scene_{scene['scene_id']:03d}"
        
        chunk = {
            # IDs
            'chunk_id': chunk_id,
            'movie_id': movie_id,
            'source_type': 'script',
            
            # Timestamps
            't_start': scene.get('t_start', 0),
            't_end': scene.get('t_end', 0),
            
            # Scene info
            'scene_id': scene.get('scene_id'),
            'scene_header': scene.get('scene_header', ''),
            'location': scene.get('location', ''),
            'time_of_day': scene.get('time_of_day'),
            'int_ext': scene.get('int_ext'),
            
            # Content
            'summary': summary,
            'dialogue_text': dialogue_text,
            'action_text': action_text,
            'raw_text': scene.get('raw_text', ''),
            
            # Characters
            'characters_present': characters_present,
            'character_details': character_details,
            
            # Alignment metadata
            'alignment_confidence': scene.get('alignment_confidence', 0.0),
            'alignment_method': scene.get('alignment_method', 'unknown'),
        }
        
        return chunk
    
    def save_corpus(self, corpus: dict, output_dir: str) -> str:
        """
        Save corpus to JSONL file.
        
        File naming: {movie_id}_enriched.jsonl
        
        Returns:
            Path to saved file
        """
        # Create output directory if it doesn't exist
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        movie_id = corpus['movie_id']
        filename = f"{movie_id}_enriched.jsonl"
        filepath = output_path / filename
        
        # Write scenes as JSONL (one scene per line)
        with open(filepath, 'w', encoding='utf-8') as f:
            for scene in corpus['scenes']:
                json_line = json.dumps(scene, ensure_ascii=False)
                f.write(json_line + '\n')
        
        # Also save metadata and characters to a separate JSON file for reference
        metadata_file = output_path / f"{movie_id}_metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            metadata = {
                'movie_id': corpus['movie_id'],
                'metadata': corpus['metadata'],
                'characters': corpus['characters'],
                'stats': corpus['stats'],
            }
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        return str(filepath)

