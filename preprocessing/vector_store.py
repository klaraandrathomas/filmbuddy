"""
Movie Vector Store (ChromaDB)

Manages storage and retrieval of enriched movie corpora using ChromaDB:
- Stores scene chunks with embeddings
- Enables timestamp-based queries
- Supports semantic search with temporal constraints
- Provides character lookup by scene
- Handles spoiler filtering

Compatible with existing FilmBuddy server architecture.
"""

import json
from pathlib import Path
from typing import Optional
import chromadb
from chromadb.config import Settings


class MovieVectorStore:
    """ChromaDB-backed vector store for movie corpora."""
    
    def __init__(self, persist_directory: str = "./chroma_db"):
        """
        Initialize ChromaDB client with persistence.
        
        Args:
            persist_directory: Directory to persist ChromaDB data
        """
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB client with persistence
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory)
        )
        
        print(f"[MovieVectorStore] Initialized with persistence at: {self.persist_directory}")
    
    def store_movie_corpus(self, corpus: dict) -> None:
        """
        Store enriched corpus in vector database.
        
        Creates collection:
            {movie_id}_scenes - Scene chunks with embeddings
        
        Scene documents include:
            - Full text for embedding (summary + key dialogue)
            - Metadata for filtering (t_start, t_end, characters, location)
        
        Args:
            corpus: Dict with 'movie_id', 'scenes', 'characters', 'metadata'
        """
        movie_id = corpus['movie_id']
        scenes = corpus['scenes']
        
        print(f"\n[MovieVectorStore] Storing corpus for: {movie_id}")
        print(f"  Scenes to store: {len(scenes)}")
        
        # Create or get collection for scenes
        collection_name = f"{movie_id}_scenes"
        
        # Delete collection if it exists (for clean re-indexing)
        try:
            self.client.delete_collection(collection_name)
            print(f"  Deleted existing collection: {collection_name}")
        except Exception:
            pass
        
        # Create new collection
        collection = self.client.create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}  # Use cosine similarity
        )
        
        # Prepare documents, metadatas, and ids for batch insertion
        documents = []
        metadatas = []
        ids = []
        
        for scene in scenes:
            # Build searchable text from summary and dialogue
            summary = scene.get('summary', '')
            dialogue = scene.get('dialogue_text', '')
            location = scene.get('location', '')
            
            # Create rich document text for embedding
            doc_text = f"{summary}\n\n{dialogue[:500]}"  # Limit dialogue to 500 chars
            if location:
                doc_text = f"Location: {location}\n{doc_text}"
            
            documents.append(doc_text)
            
            # Store metadata (ChromaDB requires all values to be str, int, float, or bool)
            metadata = {
                'movie_id': str(scene.get('movie_id', movie_id)),
                'scene_id': int(scene.get('scene_id', 0)),
                'chunk_id': str(scene.get('chunk_id', '')),
                't_start': float(scene.get('t_start', 0)),
                't_end': float(scene.get('t_end', 0)),
                'location': str(scene.get('location', '')),
                'time_of_day': str(scene.get('time_of_day', '')),
                'int_ext': str(scene.get('int_ext', '')),
                'alignment_confidence': float(scene.get('alignment_confidence', 0)),
                'alignment_method': str(scene.get('alignment_method', '')),
                'synthetic': bool(scene.get('synthetic', False)),  # Mark synthetic scenes
                # Store characters as JSON string (ChromaDB doesn't support lists directly)
                'characters_present': json.dumps(scene.get('characters_present', [])),
                'character_details': json.dumps(scene.get('character_details', {})),
            }
            
            metadatas.append(metadata)
            ids.append(scene['chunk_id'])
        
        # Batch insert all documents
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        
        print(f"  ✓ Stored {len(documents)} scenes in collection: {collection_name}")
        
        # Store movie metadata and characters separately (as JSON file)
        metadata_path = self.persist_directory / f"{movie_id}_corpus_meta.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            meta_data = {
                'movie_id': corpus['movie_id'],
                'metadata': corpus.get('metadata', {}),
                'characters': corpus.get('characters', {}),
                'stats': corpus.get('stats', {}),
            }
            json.dump(meta_data, f, indent=2, ensure_ascii=False)
        
        print(f"  ✓ Stored metadata at: {metadata_path}")
    
    def query_scene_at_timestamp(
        self, 
        movie_id: str, 
        timestamp: float,
        buffer: float = 5.0
    ) -> Optional[dict]:
        """
        Retrieve the scene containing a specific timestamp.
        
        Args:
            movie_id: Movie identifier
            timestamp: Playback time in seconds
            buffer: Tolerance window in seconds (default: 5s)
        
        Returns:
            Scene dict or None if not found
        
        Implementation:
            Use metadata filtering: (t_start - buffer) <= timestamp <= (t_end + buffer)
        """
        collection_name = f"{movie_id}_scenes"
        
        try:
            collection = self.client.get_collection(collection_name)
        except Exception:
            print(f"[MovieVectorStore] Collection not found: {collection_name}")
            return None
        
        # Query with timestamp filter
        # ChromaDB doesn't support complex range queries directly, so we get all and filter
        results = collection.get(
            where={
                "$and": [
                    {"t_start": {"$lte": timestamp + buffer}},
                    {"t_end": {"$gte": timestamp - buffer}}
                ]
            },
            include=["metadatas", "documents"]
        )
        
        if not results['ids']:
            return None
        
        # Return the first match (should only be one)
        metadata = results['metadatas'][0]
        document = results['documents'][0]
        
        # Parse JSON fields back to Python objects
        scene = dict(metadata)
        scene['characters_present'] = json.loads(scene.get('characters_present', '[]'))
        scene['character_details'] = json.loads(scene.get('character_details', '{}'))
        scene['document_text'] = document
        
        return scene
    
    def query_characters_in_scene(
        self, 
        movie_id: str, 
        scene_id: int
    ) -> list[dict]:
        """
        Get character details for a specific scene.
        
        Args:
            movie_id: Movie identifier
            scene_id: Scene number
        
        Returns:
            list of character dicts with full metadata
        """
        collection_name = f"{movie_id}_scenes"
        
        try:
            collection = self.client.get_collection(collection_name)
        except Exception:
            return []
        
        # Query by scene_id
        results = collection.get(
            where={"scene_id": scene_id},
            include=["metadatas"]
        )
        
        if not results['ids']:
            return []
        
        metadata = results['metadatas'][0]
        character_details = json.loads(metadata.get('character_details', '{}'))
        
        # Convert to list format
        characters = []
        for char_name, details in character_details.items():
            char_dict = dict(details)
            char_dict['character_name'] = char_name
            characters.append(char_dict)
        
        return characters
    
    def semantic_search(
        self, 
        movie_id: str, 
        query: str,
        timestamp: Optional[float] = None,
        top_k: int = 5,
        spoiler_mode: str = "off"
    ) -> list[dict]:
        """
        Semantic search with optional temporal constraints.
        
        Args:
            movie_id: Movie identifier
            query: Search query
            timestamp: Current playback time (for spoiler filtering)
            top_k: Number of results
            spoiler_mode: "off" filters future content, "on" allows all
        
        Returns:
            list of scene dicts sorted by relevance
        """
        collection_name = f"{movie_id}_scenes"
        
        try:
            collection = self.client.get_collection(collection_name)
        except Exception:
            print(f"[MovieVectorStore] Collection not found: {collection_name}")
            return []
        
        # Build where filter for spoiler mode
        where_filter = None
        if spoiler_mode == "off" and timestamp is not None:
            # Only return scenes that start before or at current timestamp
            where_filter = {"t_start": {"$lte": timestamp}}
        
        # Perform semantic search
        results = collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where_filter,
            include=["metadatas", "documents", "distances"]
        )
        
        # Format results
        scenes = []
        if results['ids'] and results['ids'][0]:
            for i in range(len(results['ids'][0])):
                metadata = results['metadatas'][0][i]
                document = results['documents'][0][i]
                distance = results['distances'][0][i]
                
                # Parse JSON fields
                scene = dict(metadata)
                scene['characters_present'] = json.loads(scene.get('characters_present', '[]'))
                scene['character_details'] = json.loads(scene.get('character_details', '{}'))
                scene['document_text'] = document
                scene['relevance_score'] = 1 - distance  # Convert distance to similarity
                
                scenes.append(scene)
        
        return scenes
    
    def list_movies(self) -> list[str]:
        """
        List all movies in the store.
        
        Returns:
            list of movie_ids
        """
        collections = self.client.list_collections()
        
        # Extract movie_ids from collection names (format: {movie_id}_scenes)
        movie_ids = set()
        for collection in collections:
            name = collection.name
            if name.endswith('_scenes'):
                movie_id = name[:-7]  # Remove '_scenes' suffix
                movie_ids.add(movie_id)
        
        return sorted(list(movie_ids))
    
    def has_movie(self, movie_id: str) -> bool:
        """
        Check if a movie exists in the store.
        
        Args:
            movie_id: Movie identifier
        
        Returns:
            True if movie exists, False otherwise
        """
        collection_name = f"{movie_id}_scenes"
        try:
            self.client.get_collection(collection_name)
            return True
        except Exception:
            return False
    
    def delete_movie(self, movie_id: str) -> bool:
        """
        Remove a movie from the store.
        
        Args:
            movie_id: Movie identifier
        
        Returns:
            True if deleted, False if not found
        """
        collection_name = f"{movie_id}_scenes"
        
        try:
            self.client.delete_collection(collection_name)
            print(f"[MovieVectorStore] Deleted collection: {collection_name}")
            
            # Also delete metadata file
            metadata_path = self.persist_directory / f"{movie_id}_corpus_meta.json"
            if metadata_path.exists():
                metadata_path.unlink()
                print(f"[MovieVectorStore] Deleted metadata: {metadata_path}")
            
            return True
        except Exception as e:
            print(f"[MovieVectorStore] Failed to delete {movie_id}: {e}")
            return False
    
    def get_movie_metadata(self, movie_id: str) -> Optional[dict]:
        """
        Get movie metadata and character information.
        
        Args:
            movie_id: Movie identifier
        
        Returns:
            Dict with metadata, characters, and stats, or None if not found
        """
        metadata_path = self.persist_directory / f"{movie_id}_corpus_meta.json"
        
        if not metadata_path.exists():
            return None
        
        with open(metadata_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get_all_characters(self, movie_id: str) -> dict:
        """
        Get all character information for a movie.
        
        Args:
            movie_id: Movie identifier
        
        Returns:
            Dict of character_name -> character_details
        """
        metadata = self.get_movie_metadata(movie_id)
        if metadata:
            return metadata.get('characters', {})
        return {}

