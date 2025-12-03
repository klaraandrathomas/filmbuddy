"""
TMDB API Client

Fetches movie metadata from The Movie Database (TMDB) including:
- Movie search and details
- Cast information
- Character-to-actor mapping
- Runtime and release information
"""

import os
from dataclasses import dataclass
from typing import Optional
import aiohttp
import asyncio


@dataclass
class TMDBCharacter:
    """Character information from TMDB cast data."""
    character_name: str      # e.g., "Mia Dolan"
    actor_name: str          # e.g., "Emma Stone"
    gender: str              # "female" | "male" | "unknown"
    billing_order: int       # 0 = lead, higher = smaller role
    profile_image_url: Optional[str] = None   # Optional headshot URL


class TMDBClient:
    """Client for The Movie Database (TMDB) API."""
    
    BASE_URL = "https://api.themoviedb.org/3"
    IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"
    
    def __init__(self, api_key: str = None):
        """
        Initialize with API key from env or parameter.
        
        Args:
            api_key: TMDB API key (defaults to TMDB_API_KEY env var)
        """
        self.api_key = api_key or os.environ.get("TMDB_API_KEY")
        if not self.api_key:
            raise ValueError(
                "TMDB API key not found. Set TMDB_API_KEY environment variable "
                "or pass api_key parameter."
            )
    
    async def search_movie(self, title: str, year: int = None) -> dict:
        """
        Search for a movie by title and optional year.
        
        Args:
            title: Movie title (e.g., "La La Land")
            year: Release year for disambiguation (e.g., 2016)
        
        Returns:
            dict with keys: id, title, release_date, overview, poster_path
            Returns None if movie not found
        """
        params = {
            "api_key": self.api_key,
            "query": title,
        }
        
        if year:
            params["year"] = year
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.BASE_URL}/search/movie",
                params=params
            ) as response:
                if response.status != 200:
                    raise Exception(f"TMDB API error: {response.status}")
                
                data = await response.json()
                results = data.get("results", [])
                
                if not results:
                    return None
                
                # Return first result (most relevant)
                movie = results[0]
                return {
                    "id": movie["id"],
                    "title": movie["title"],
                    "release_date": movie.get("release_date"),
                    "overview": movie.get("overview"),
                    "poster_path": movie.get("poster_path"),
                }
    
    async def get_movie_details(self, movie_id: int) -> dict:
        """
        Get full movie details including runtime.
        
        Args:
            movie_id: TMDB movie ID
        
        Returns:
            dict with keys: id, title, runtime, release_date, genres, overview
        """
        params = {"api_key": self.api_key}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.BASE_URL}/movie/{movie_id}",
                params=params
            ) as response:
                if response.status != 200:
                    raise Exception(f"TMDB API error: {response.status}")
                
                movie = await response.json()
                
                return {
                    "id": movie["id"],
                    "title": movie["title"],
                    "runtime": movie.get("runtime"),  # in minutes
                    "release_date": movie.get("release_date"),
                    "genres": [g["name"] for g in movie.get("genres", [])],
                    "overview": movie.get("overview"),
                }
    
    async def get_cast(self, movie_id: int, limit: int = 20) -> list[dict]:
        """
        Get top billed cast members.
        
        Args:
            movie_id: TMDB movie ID
            limit: Max number of cast members to return
        
        Returns:
            list of dicts with keys: actor_name, character_name, order, gender, profile_path
        """
        params = {"api_key": self.api_key}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.BASE_URL}/movie/{movie_id}/credits",
                params=params
            ) as response:
                if response.status != 200:
                    raise Exception(f"TMDB API error: {response.status}")
                
                data = await response.json()
                cast = data.get("cast", [])
                
                # Convert TMDB gender codes to readable strings
                def gender_code_to_string(code: int) -> str:
                    if code == 1:
                        return "female"
                    elif code == 2:
                        return "male"
                    else:
                        return "unknown"
                
                # Extract and format cast data
                result = []
                for person in cast[:limit]:
                    profile_path = person.get("profile_path")
                    result.append({
                        "actor_name": person.get("name"),
                        "character_name": person.get("character"),
                        "order": person.get("order", 999),
                        "gender": gender_code_to_string(person.get("gender", 0)),
                        "profile_path": f"{self.IMAGE_BASE_URL}{profile_path}" if profile_path else None,
                    })
                
                return result
    
    async def get_movie_metadata(self, title: str, year: int = None) -> dict:
        """
        Convenience method to get all movie data in one call.
        
        Args:
            title: Movie title
            year: Optional release year for disambiguation
        
        Returns:
            dict with keys:
                - movie_id: int
                - title: str
                - runtime_seconds: int
                - release_year: int
                - characters: list[dict] with actor_name, character_name, gender
        
        Raises:
            ValueError: If movie not found
        """
        # Search for movie
        search_result = await self.search_movie(title, year)
        if not search_result:
            raise ValueError(f"Movie not found: {title}" + (f" ({year})" if year else ""))
        
        movie_id = search_result["id"]
        
        # Get details and cast in parallel
        details_task = self.get_movie_details(movie_id)
        cast_task = self.get_cast(movie_id)
        
        details, cast = await asyncio.gather(details_task, cast_task)
        
        # Extract release year
        release_year = None
        if details.get("release_date"):
            release_year = int(details["release_date"].split("-")[0])
        
        # Convert runtime to seconds
        runtime_minutes = details.get("runtime", 0)
        runtime_seconds = runtime_minutes * 60 if runtime_minutes else 0
        
        return {
            "movie_id": movie_id,
            "title": details["title"],
            "runtime_seconds": runtime_seconds,
            "release_year": release_year,
            "genres": details.get("genres", []),
            "overview": details.get("overview"),
            "characters": cast,
        }
