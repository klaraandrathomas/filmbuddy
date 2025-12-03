"""
Timestamp Aligner

Aligns script scenes to subtitle timestamps using:
- Fuzzy dialogue matching (rapidfuzz)
- Intelligent interpolation for unmatched scenes
- Confidence scoring for alignment quality

Enables temporal queries by providing accurate start/end times for each scene.
"""

import re
import string
from typing import Optional
from rapidfuzz import fuzz


class TimestampAligner:
    """Align script scenes to subtitle timestamps."""
    
    def __init__(self, match_threshold: float = 0.75):
        """
        Args:
            match_threshold: Minimum similarity ratio for fuzzy match (0-1)
        """
        self.match_threshold = match_threshold
    
    def align_scenes_to_subtitles(
        self, 
        scenes: list[dict], 
        subtitles: list[dict]
    ) -> list[dict]:
        """
        Add timestamp fields to each scene.
        
        Args:
            scenes: Parsed scenes from ScriptParser
            subtitles: Parsed subtitle cues (from parse_srt or existing parser)
        
        Returns:
            list of scenes with added fields:
                - t_start: float (seconds)
                - t_end: float (seconds)
                - alignment_confidence: float (0-1)
                - alignment_method: str ("dialogue_match" | "interpolated")
        
        Implementation:
            1. Build search index from subtitle text
            2. For each scene, extract key dialogue lines
            3. Search subtitles for matching dialogue
            4. If match found, use subtitle timestamp ± buffer
            5. If no match, interpolate from neighbors or use proportional estimate
        """
        if not subtitles:
            raise ValueError("No subtitles provided for alignment")
        
        total_duration = subtitles[-1]['t_end'] if subtitles else 0
        aligned_scenes = []
        
        for i, scene in enumerate(scenes):
            # Try to find dialogue match
            key_phrases = self._extract_key_dialogue(scene)
            
            best_match = None
            best_confidence = 0.0
            
            for phrase in key_phrases:
                match = self._fuzzy_match_in_subtitles(phrase, subtitles)
                if match:
                    t_start, t_end, confidence = match
                    if confidence > best_confidence:
                        best_match = (t_start, t_end)
                        best_confidence = confidence
            
            # Create aligned scene
            aligned_scene = scene.copy()
            
            if best_match and best_confidence >= self.match_threshold:
                # Use matched timestamp with buffer
                t_start, t_end = best_match
                
                # Add buffer before and after (scenes are typically longer than single subtitle)
                scene_buffer_before = 5.0  # seconds
                scene_buffer_after = 15.0   # seconds
                
                aligned_scene['t_start'] = max(0, t_start - scene_buffer_before)
                aligned_scene['t_end'] = min(total_duration, t_end + scene_buffer_after)
                aligned_scene['alignment_confidence'] = best_confidence
                aligned_scene['alignment_method'] = 'dialogue_match'
            else:
                # Interpolate timestamp
                t_start, t_end = self._interpolate_timestamp(i, scenes, aligned_scenes, total_duration)
                aligned_scene['t_start'] = t_start
                aligned_scene['t_end'] = t_end
                aligned_scene['alignment_confidence'] = 0.3  # Low confidence for interpolated
                aligned_scene['alignment_method'] = 'interpolated'
            
            aligned_scenes.append(aligned_scene)
        
        return aligned_scenes
    
    def _extract_key_dialogue(self, scene: dict) -> list[str]:
        """
        Extract searchable dialogue phrases from scene.
        
        - Prefer first and last dialogue lines (more distinctive)
        - Clean punctuation and normalize whitespace
        - Skip very short lines (< 4 words)
        
        Returns:
            list of 3-5 key phrases to search for
        """
        dialogue = scene.get('dialogue', [])
        if not dialogue:
            return []
        
        key_phrases = []
        
        # Get first dialogue line
        if len(dialogue) > 0:
            first_text = dialogue[0].get('text', '')
            if self._is_substantial_phrase(first_text):
                key_phrases.append(self._normalize_text(first_text))
        
        # Get last dialogue line (if different from first)
        if len(dialogue) > 1:
            last_text = dialogue[-1].get('text', '')
            if self._is_substantial_phrase(last_text):
                key_phrases.append(self._normalize_text(last_text))
        
        # Get middle dialogue lines (up to 3 more)
        if len(dialogue) > 2:
            middle_indices = [len(dialogue) // 2]
            if len(dialogue) > 4:
                middle_indices.append(len(dialogue) // 3)
            if len(dialogue) > 6:
                middle_indices.append(2 * len(dialogue) // 3)
            
            for idx in middle_indices[:3]:
                if idx < len(dialogue):
                    text = dialogue[idx].get('text', '')
                    if self._is_substantial_phrase(text):
                        key_phrases.append(self._normalize_text(text))
        
        # Remove duplicates while preserving order
        seen = set()
        unique_phrases = []
        for phrase in key_phrases:
            if phrase not in seen and phrase:
                seen.add(phrase)
                unique_phrases.append(phrase)
        
        return unique_phrases[:5]  # Max 5 phrases
    
    def _fuzzy_match_in_subtitles(
        self, 
        phrase: str, 
        subtitles: list[dict],
        time_window: Optional[tuple[float, float]] = None
    ) -> Optional[tuple[float, float, float]]:
        """
        Find phrase in subtitles using fuzzy matching.
        
        Args:
            phrase: Dialogue to search for
            subtitles: Subtitle list
            time_window: Optional (start, end) to narrow search
        
        Returns:
            (t_start, t_end, confidence) if found, else None
        
        Implementation:
            - Use rapidfuzz.fuzz.partial_ratio for similarity
            - Normalize both strings (lowercase, remove punctuation)
            - Return subtitle cue with highest match above threshold
        """
        if not phrase or not subtitles:
            return None
        
        best_match = None
        best_score = 0
        
        for subtitle in subtitles:
            # Check time window if provided
            if time_window:
                start, end = time_window
                if subtitle['t_start'] < start or subtitle['t_start'] > end:
                    continue
            
            # Normalize subtitle text
            sub_text = self._normalize_text(subtitle.get('text', ''))
            
            # Skip empty subtitles
            if not sub_text:
                continue
            
            # Calculate similarity using partial ratio (best for substring matching)
            score = fuzz.partial_ratio(phrase, sub_text) / 100.0
            
            if score > best_score:
                best_score = score
                best_match = (subtitle['t_start'], subtitle['t_end'], score)
        
        # Only return if above threshold
        if best_match and best_score >= self.match_threshold:
            return best_match
        
        return None
    
    def _interpolate_timestamp(
        self, 
        scene_idx: int, 
        scenes: list[dict],
        aligned_scenes: list[dict],
        total_duration: float
    ) -> tuple[float, float]:
        """
        Estimate timestamp when no dialogue match found.
        
        Strategy:
            1. If neighbors have timestamps, interpolate between them
            2. Otherwise, use proportional estimate:
               t_start = (scene_idx / total_scenes) * total_duration
        """
        num_scenes = len(scenes)
        
        # Try to find previous aligned scene
        prev_timestamp = None
        if scene_idx > 0 and aligned_scenes:
            prev_scene = aligned_scenes[-1]
            if 't_end' in prev_scene:
                prev_timestamp = prev_scene['t_end']
        
        # Try to find next aligned scene (look ahead in scenes)
        next_timestamp = None
        for future_idx in range(scene_idx + 1, min(scene_idx + 5, num_scenes)):
            future_scene = scenes[future_idx]
            # Check if this future scene might have a match
            key_phrases = self._extract_key_dialogue(future_scene)
            if key_phrases:
                # We can't know for sure yet, so just use proportional
                break
        
        # Estimate based on position
        if prev_timestamp is not None:
            # Start after previous scene
            t_start = prev_timestamp + 1.0  # 1 second buffer
        else:
            # Proportional estimate
            proportion = scene_idx / max(num_scenes, 1)
            t_start = proportion * total_duration
        
        # Estimate scene duration (average 2-3 minutes per scene)
        avg_scene_duration = total_duration / max(num_scenes, 1)
        estimated_duration = max(60, min(avg_scene_duration, 180))  # Between 60-180 seconds
        
        t_end = t_start + estimated_duration
        t_end = min(t_end, total_duration)
        
        return (t_start, t_end)
    
    def _is_substantial_phrase(self, text: str) -> bool:
        """Check if phrase is substantial enough for matching."""
        words = text.split()
        return len(words) >= 4  # At least 4 words
    
    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for fuzzy matching.
        
        - Lowercase
        - Remove punctuation
        - Normalize whitespace
        """
        # Lowercase
        text = text.lower()
        
        # Remove punctuation
        text = text.translate(str.maketrans('', '', string.punctuation))
        
        # Normalize whitespace
        text = ' '.join(text.split())
        
        return text
    
    @staticmethod
    def parse_srt(srt_path: str) -> list[dict]:
        """
        Parse SRT file into list of subtitle cues.
        
        Returns:
            list of dicts with keys: t_start, t_end, text
        
        Note: Can reuse logic from build_time_aware_corpus.py
        """
        import srt
        
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse using srt library
        subtitle_generator = srt.parse(content)
        
        subtitles = []
        for sub in subtitle_generator:
            subtitles.append({
                't_start': sub.start.total_seconds(),
                't_end': sub.end.total_seconds(),
                'text': sub.content
            })
        
        return subtitles
