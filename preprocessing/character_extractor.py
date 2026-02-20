"""
Character Extractor (LLM-Powered)

Uses LLM (via Azure OpenAI) to extract rich character metadata including:
- Full names and gender
- Role classification (protagonist, antagonist, supporting, minor)
- Character descriptions and occupations
- Relationships between characters
- Scene summaries

Optimized for cost-efficiency through batching and selective extraction.
"""

import os
import json
import asyncio
from typing import Optional
from openai import AzureOpenAI, OpenAI


class CharacterExtractor:
    """LLM-powered character metadata extraction.

    Supports both Azure OpenAI and regular OpenAI.  When Azure credentials
    (AZURE_OPENAI_API_KEY + AZURE_OPENAI_ENDPOINT) are present the Azure
    client is used; otherwise it falls back to the standard OpenAI client
    with OPENAI_API_KEY.
    """

    def __init__(
        self,
        api_key: str = None,
        endpoint: str = None,
        api_version: str = None,
        deployment_name: str = None,
    ):
        """Initialise with Azure OpenAI or standard OpenAI credentials.

        Args:
            api_key: Azure OpenAI API key (defaults to AZURE_OPENAI_API_KEY env
                var).  For standard OpenAI, set the OPENAI_API_KEY env var
                instead.
            endpoint: Azure OpenAI endpoint (defaults to AZURE_OPENAI_ENDPOINT
                env var).  Must be provided together with *api_key* to select
                the Azure path.
            api_version: Azure API version (defaults to AZURE_OPENAI_API_VERSION
                env var or "2024-10-21").
            deployment_name: Model / deployment name.  Defaults to
                AZURE_OPENAI_DEPLOYMENT_NAME (Azure) or FILMBUDDY_LLM_MODEL /
                "gpt-4o" (OpenAI).
        """
        azure_key = api_key or os.environ.get("AZURE_OPENAI_API_KEY")
        azure_endpoint = endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT")
        openai_key = os.environ.get("OPENAI_API_KEY")

        if azure_key and azure_endpoint:
            self.api_version = api_version or os.environ.get(
                "AZURE_OPENAI_API_VERSION", "2024-10-21"
            )
            self.deployment_name = deployment_name or os.environ.get(
                "AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4.1"
            )
            self.client = AzureOpenAI(
                api_key=azure_key,
                api_version=self.api_version,
                azure_endpoint=azure_endpoint,
            )
            print(f"[CharacterExtractor] Using Azure OpenAI deployment: {self.deployment_name}")
            print(f"[CharacterExtractor] Azure endpoint: {azure_endpoint}")
        elif openai_key or api_key:
            self.deployment_name = deployment_name or os.environ.get(
                "FILMBUDDY_LLM_MODEL", "gpt-4o"
            )
            self.client = OpenAI(api_key=api_key or openai_key)
            print(f"[CharacterExtractor] Using OpenAI model: {self.deployment_name}")
        else:
            raise ValueError(
                "No LLM API key found. Set OPENAI_API_KEY or both "
                "AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT."
            )
    
    async def extract_character_metadata(
        self, 
        script_text: str, 
        character_names: list[str]
    ) -> dict[str, dict]:
        """
        Extract character metadata from script using LLM.
        
        Args:
            script_text: Full script or first N pages
            character_names: List of character names found by parser
        
        Returns:
            dict mapping character names to metadata:
            {
                "MIA": {
                    "full_name": "Mia Dolan",
                    "gender": "female",
                    "role": "protagonist",  # protagonist | antagonist | supporting | minor
                    "description": "Aspiring actress working as a barista...",
                    "occupation": "Barista / Actress",
                    "relationships": {
                        "SEBASTIAN": "love interest, later boyfriend"
                    },
                    "first_appearance_scene": 1
                },
                ...
            }
        
        Implementation Notes:
            - Use first 15-20 pages of script for context (characters are usually introduced early)
            - Send single prompt with all characters to avoid multiple API calls
            - Use JSON mode for reliable parsing
        """
        # Limit to first ~20 pages (approximately 15000 characters)
        script_excerpt = script_text[:15000]
        
        # Build prompt
        prompt = self._build_character_extraction_prompt(script_excerpt, character_names)
        
        # Call LLM with JSON mode
        try:
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            
            # Parse JSON response
            result = json.loads(response.choices[0].message.content)
            
            # Validate and clean up the result
            return self._validate_character_metadata(result, character_names)
        
        except Exception as e:
            print(f"[CharacterExtractor] Error extracting character metadata: {e}")
            # Return empty metadata for all characters
            return {name: self._default_character_metadata(name) for name in character_names}
    
    async def generate_scene_summary(
        self, 
        scene: dict, 
        character_metadata: dict = None
    ) -> str:
        """
        Generate 1-2 sentence summary of a scene.
        
        Args:
            scene: Parsed scene dict from ScriptParser
            character_metadata: Optional character info for context
        
        Returns:
            str: Concise summary, e.g., 
            "Mia and Sebastian argue about their relationship at the Griffith Observatory, 
             leading to their decision to pursue their individual dreams."
        
        Implementation Notes:
            - Keep summaries factual and concise
            - Mention key characters and main action
            - Avoid spoilers if possible (just describe what happens, not why it matters)
        """
        # Build prompt
        prompt = self._build_scene_summary_prompt(scene, character_metadata)
        
        try:
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=150
            )
            
            summary = response.choices[0].message.content.strip()
            
            # Remove quotes if LLM added them
            if summary.startswith('"') and summary.endswith('"'):
                summary = summary[1:-1]
            
            return summary
        
        except Exception as e:
            print(f"[CharacterExtractor] Error generating scene summary: {e}")
            # Return fallback summary
            return self._fallback_scene_summary(scene)
    
    async def batch_generate_summaries(
        self, 
        scenes: list[dict], 
        character_metadata: dict = None,
        batch_size: int = 5
    ) -> list[str]:
        """
        Generate summaries for multiple scenes efficiently.
        
        Args:
            scenes: List of parsed scenes
            character_metadata: Character info dict
            batch_size: Number of scenes per API call
        
        Returns:
            list[str]: Summaries in same order as input scenes
        
        Implementation Notes:
            - Batch 5 scenes per API call to reduce costs
            - Use asyncio.gather for parallel batches
            - Total API calls = ceil(num_scenes / batch_size)
        """
        summaries = []
        
        # Process scenes in batches
        for i in range(0, len(scenes), batch_size):
            batch = scenes[i:i + batch_size]
            
            # Build batch prompt
            prompt = self._build_batch_summary_prompt(batch, character_metadata)
            
            try:
                response = self.client.chat.completions.create(
                    model=self.deployment_name,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    temperature=0.5,
                    max_tokens=500
                )
                
                # Parse JSON response
                result = json.loads(response.choices[0].message.content)
                
                # Extract summaries in order
                for scene in batch:
                    scene_key = f"scene_{scene['scene_id']}"
                    summary = result.get(scene_key, self._fallback_scene_summary(scene))
                    summaries.append(summary)
            
            except Exception as e:
                print(f"[CharacterExtractor] Error in batch {i//batch_size + 1}: {e}")
                # Add fallback summaries for this batch
                for scene in batch:
                    summaries.append(self._fallback_scene_summary(scene))
        
        return summaries
    
    def _build_character_extraction_prompt(
        self, 
        script_excerpt: str, 
        character_names: list[str]
    ) -> str:
        """Build prompt for character metadata extraction."""
        return f"""You are analyzing a movie script to extract character information.

SCRIPT EXCERPT (first 20 pages):
{script_excerpt}

CHARACTERS TO ANALYZE:
{', '.join(character_names)}

For each character, provide:
1. full_name - Their complete name if mentioned (or the character name if full name not found)
2. gender - "male", "female", or "unknown"
3. role - "protagonist", "antagonist", "supporting", or "minor"
4. description - 1-2 sentence description of who they are
5. occupation - Their job or role in life (if known, otherwise "Unknown")
6. relationships - Key relationships to other characters in this list (as a dict)

Return ONLY valid JSON in this exact format:
{{
  "CHARACTER_NAME": {{
    "full_name": "...",
    "gender": "...",
    "role": "...",
    "description": "...",
    "occupation": "...",
    "relationships": {{"OTHER_CHAR": "relationship description"}}
  }}
}}

Include ALL characters from the list, even if minimal information is available."""
    
    def _build_scene_summary_prompt(
        self, 
        scene: dict, 
        character_metadata: dict = None
    ) -> str:
        """Build prompt for single scene summary."""
        # Format character info if available
        char_info = ""
        if character_metadata and scene.get('characters'):
            char_details = []
            for char in scene['characters']:
                if char in character_metadata:
                    meta = character_metadata[char]
                    char_details.append(f"{char} ({meta.get('role', 'character')})")
                else:
                    char_details.append(char)
            char_info = f"\nCharacters: {', '.join(char_details)}"
        
        # Truncate very long scenes
        raw_text = scene.get('raw_text', '')[:1000]
        
        return f"""Summarize this movie scene in 1-2 sentences. Focus on what happens, who's involved, 
and any key emotional beats. Be concise and factual.

LOCATION: {scene.get('location', 'Unknown')}{char_info}

SCENE:
{raw_text}

Summary:"""
    
    def _build_batch_summary_prompt(
        self, 
        scenes: list[dict], 
        character_metadata: dict = None
    ) -> str:
        """Build prompt for batch scene summaries."""
        scenes_text = []
        
        for scene in scenes:
            # Format character info
            char_info = ""
            if character_metadata and scene.get('characters'):
                char_details = []
                for char in scene['characters']:
                    if char in character_metadata:
                        meta = character_metadata[char]
                        char_details.append(f"{char} ({meta.get('role', 'character')})")
                    else:
                        char_details.append(char)
                char_info = f"\nCharacters: {', '.join(char_details)}"
            
            # Truncate scene text
            raw_text = scene.get('raw_text', '')[:800]
            
            scene_text = f"""Scene {scene['scene_id']}: {scene.get('scene_header', 'Unknown')}
Location: {scene.get('location', 'Unknown')}{char_info}
{raw_text}
---"""
            scenes_text.append(scene_text)
        
        return f"""Summarize each of these movie scenes in 1-2 sentences. Focus on what happens, 
who's involved, and key emotional beats. Be concise and factual.

{chr(10).join(scenes_text)}

Return ONLY valid JSON in this format:
{{
  "scene_1": "summary of scene 1...",
  "scene_2": "summary of scene 2...",
  ...
}}"""
    
    def _validate_character_metadata(
        self, 
        result: dict, 
        character_names: list[str]
    ) -> dict:
        """Validate and clean up character metadata from LLM."""
        validated = {}
        
        for name in character_names:
            if name in result:
                char_data = result[name]
                validated[name] = {
                    "full_name": char_data.get("full_name", name),
                    "gender": char_data.get("gender", "unknown").lower(),
                    "role": char_data.get("role", "minor").lower(),
                    "description": char_data.get("description", ""),
                    "occupation": char_data.get("occupation", "Unknown"),
                    "relationships": char_data.get("relationships", {}),
                }
            else:
                validated[name] = self._default_character_metadata(name)
        
        return validated
    
    def _default_character_metadata(self, name: str) -> dict:
        """Return default metadata when extraction fails."""
        return {
            "full_name": name,
            "gender": "unknown",
            "role": "minor",
            "description": "",
            "occupation": "Unknown",
            "relationships": {},
        }
    
    def _fallback_scene_summary(self, scene: dict) -> str:
        """Generate fallback summary when LLM fails."""
        location = scene.get('location', 'Unknown location')
        characters = scene.get('characters', [])
        
        if characters:
            char_str = ' and '.join(characters) if len(characters) <= 2 else f"{characters[0]} and others"
            return f"{char_str} at {location}."
        else:
            return f"Scene at {location}."
