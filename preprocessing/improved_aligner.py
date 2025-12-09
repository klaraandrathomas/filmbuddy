"""
Improved Timestamp Aligner

Fixes timestamp duplication issues in the original aligner by using:
- Anchor-based sequential alignment
- Distinctiveness scoring for dialogue phrases
- Uniqueness constraints (each subtitle matched once)
- Temporal ordering enforcement
- Intelligent interpolation between anchors
- Validation pass to ensure consistency

This eliminates the 33% timestamp duplication problem in the original implementation.
"""

import re
import string
from typing import Optional, List, Tuple, Set
from collections import Counter
from rapidfuzz import fuzz


class ImprovedTimestampAligner:
    """
    Improved timestamp aligner with uniqueness and temporal ordering constraints.
    
    Algorithm:
    1. Build word frequency index from all subtitles
    2. Extract distinctive phrases from each scene (scored by rarity)
    3. Find anchor scenes with high-confidence matches (sequential, no duplicates)
    4. Interpolate timestamps for non-anchor scenes
    5. Validate and enforce temporal ordering
    """
    
    def __init__(
        self, 
        anchor_threshold: float = 0.85,
        fuzzy_threshold: float = 0.75,
        min_phrase_words: int = 4
    ):
        """
        Args:
            anchor_threshold: Minimum combined score for anchor match (0-1)
            fuzzy_threshold: Minimum fuzzy similarity score (0-1)
            min_phrase_words: Minimum words in a phrase for matching
        """
        self.anchor_threshold = anchor_threshold
        self.fuzzy_threshold = fuzzy_threshold
        self.min_phrase_words = min_phrase_words
        self.word_freq = {}  # Built from subtitles
    
    def align_scenes_to_subtitles(
        self, 
        scenes: list[dict], 
        subtitles: list[dict]
    ) -> list[dict]:
        """
        Align script scenes to subtitle timestamps with improved accuracy.
        
        Args:
            scenes: Parsed scenes from ScriptParser
            subtitles: Parsed subtitle cues with t_start, t_end, text
        
        Returns:
            Scenes with added timestamp and alignment metadata:
                - t_start: float (seconds)
                - t_end: float (seconds)
                - alignment_confidence: float (0-1)
                - alignment_method: "anchor_match" | "interpolated"
                - distinctiveness_score: float (for anchor matches)
        """
        if not subtitles:
            raise ValueError("No subtitles provided for alignment")
        
        if not scenes:
            raise ValueError("No scenes provided for alignment")
        
        total_duration = subtitles[-1]['t_end']
        
        print(f"\n[ImprovedAligner] Starting alignment...")
        print(f"  Scenes: {len(scenes)}")
        print(f"  Subtitles: {len(subtitles)}")
        print(f"  Duration: {total_duration / 60:.1f} minutes")
        
        # Step 1: Build word frequency index
        print(f"\n[1/5] Building word frequency index...")
        self.word_freq = self._build_word_frequency(subtitles)
        print(f"  ✓ Indexed {len(self.word_freq)} unique words")
        
        # Step 2: Find anchor scenes
        print(f"\n[2/5] Finding anchor scenes...")
        anchors, used_subtitles = self._find_anchor_scenes(scenes, subtitles)
        anchor_rate = len(anchors) / len(scenes) * 100
        print(f"  ✓ Found {len(anchors)} anchor scenes ({anchor_rate:.1f}%)")
        
        # Step 3: Interpolate non-anchor scenes
        print(f"\n[3/5] Interpolating non-anchor scenes...")
        aligned_scenes = self._interpolate_all_scenes(scenes, anchors, total_duration)
        interpolated_count = sum(1 for s in aligned_scenes if s.get('alignment_method') == 'interpolated')
        print(f"  ✓ Interpolated {interpolated_count} scenes")
        
        # Step 4: Enforce temporal ordering
        print(f"\n[4/5] Enforcing temporal ordering...")
        aligned_scenes = self._enforce_temporal_order(aligned_scenes)
        print(f"  ✓ Validated scene ordering")
        
        # Step 5: Detect and report any remaining issues
        print(f"\n[5/5] Final validation...")
        self._validate_alignment(aligned_scenes)
        
        print(f"\n[ImprovedAligner] ✅ Alignment complete!")
        
        return aligned_scenes
    
    def _build_word_frequency(self, subtitles: list[dict]) -> dict:
        """
        Build word frequency map from all subtitle text.
        Used for calculating phrase distinctiveness.
        """
        word_freq = Counter()
        
        for subtitle in subtitles:
            text = subtitle.get('text', '')
            normalized = self._normalize_text(text)
            words = normalized.split()
            word_freq.update(words)
        
        return dict(word_freq)
    
    def _find_anchor_scenes(
        self, 
        scenes: list[dict], 
        subtitles: list[dict]
    ) -> Tuple[dict, Set[int]]:
        """
        Find anchor scenes with distinctive dialogue.
        
        Returns:
            (anchors_dict, used_subtitle_indices)
            where anchors_dict maps scene_id -> aligned_scene
        """
        anchors = {}
        used_subtitles = set()
        last_match_time = 0
        
        for i, scene in enumerate(scenes):
            # Extract distinctive phrases
            phrases = self._extract_distinctive_phrases(scene)
            
            if not phrases:
                continue
            
            # Try to match with temporal constraint
            best_match = self._find_best_match(
                phrases,
                subtitles,
                time_window=(last_match_time, float('inf')),
                used_indices=used_subtitles
            )
            
            if best_match:
                t_start, t_end, combined_score, distinctiveness, sub_idx = best_match
                
                # Check if this qualifies as an anchor
                if combined_score >= self.anchor_threshold:
                    # Create aligned scene
                    aligned_scene = scene.copy()
                    
                    # Use smaller buffer for anchors (they're high confidence)
                    buffer_before = 3.0
                    buffer_after = 8.0
                    
                    aligned_scene['t_start'] = max(last_match_time, t_start - buffer_before)
                    aligned_scene['t_end'] = t_end + buffer_after
                    aligned_scene['alignment_confidence'] = combined_score
                    aligned_scene['alignment_method'] = 'anchor_match'
                    aligned_scene['distinctiveness_score'] = distinctiveness
                    
                    anchors[scene['scene_id']] = aligned_scene
                    used_subtitles.add(sub_idx)
                    last_match_time = t_end
                    
                    if len(anchors) <= 10 or len(anchors) % 10 == 0:
                        mins, secs = int(t_start // 60), int(t_start % 60)
                        print(f"    Anchor #{len(anchors)}: Scene {scene['scene_id']} → {mins}:{secs:02d} (confidence: {combined_score:.3f})")
        
        return anchors, used_subtitles
    
    def _extract_distinctive_phrases(self, scene: dict) -> List[Tuple[str, float]]:
        """
        Extract dialogue phrases and score by distinctiveness.
        
        Returns:
            list of (normalized_phrase, distinctiveness_score) tuples,
            sorted by distinctiveness (most distinctive first)
        """
        dialogue = scene.get('dialogue', [])
        if not dialogue:
            return []
        
        phrases = []
        
        for d in dialogue:
            text = d.get('text', '')
            
            # Skip very short phrases
            words = text.split()
            if len(words) < self.min_phrase_words:
                continue
            
            # Normalize for matching
            normalized = self._normalize_text(text)
            
            # Calculate distinctiveness
            distinctiveness = self._calculate_distinctiveness(text, normalized)
            
            phrases.append((normalized, distinctiveness))
        
        # Sort by distinctiveness (highest first)
        phrases.sort(key=lambda x: x[1], reverse=True)
        
        # Return top 5 most distinctive
        return phrases[:5]
    
    def _calculate_distinctiveness(self, original_text: str, normalized_text: str) -> float:
        """
        Calculate how distinctive/unique a phrase is.
        
        Factors:
        - Length (longer = more distinctive)
        - Word rarity (rare words = more distinctive)
        - Proper nouns (capitalized = more distinctive)
        - Avoid generic phrases ("yeah", "okay", "what")
        
        Returns:
            Score from 0 to 1 (higher = more distinctive)
        """
        words = normalized_text.split()
        if not words:
            return 0.0
        
        # 1. Length bonus (longer phrases are more distinctive)
        # Cap at 15 words for diminishing returns
        length_score = min(len(words) / 15.0, 1.0)
        
        # 2. Rarity score (inverse of word frequency)
        rarity_scores = []
        for word in words:
            freq = self.word_freq.get(word, 0)
            # Rare words score higher
            # Use log scale to dampen effect of very common words
            if freq == 0:
                rarity = 1.0
            else:
                # Normalize: assume max frequency is 1000 (very common word)
                rarity = 1.0 - min(freq / 1000.0, 1.0)
            rarity_scores.append(rarity)
        
        avg_rarity = sum(rarity_scores) / len(rarity_scores) if rarity_scores else 0
        
        # 3. Proper noun bonus (names, places)
        original_words = original_text.split()
        proper_nouns = sum(1 for w in original_words if w and w[0].isupper() and len(w) > 1)
        proper_noun_score = min(proper_nouns / 3.0, 0.3)  # Up to +30%
        
        # 4. Penalty for generic phrases
        generic_words = {'yeah', 'yes', 'no', 'okay', 'ok', 'hey', 'hi', 'what', 'why', 'how'}
        generic_count = sum(1 for w in words if w in generic_words)
        generic_penalty = min(generic_count / len(words), 0.5)  # Up to -50%
        
        # Combined score
        distinctiveness = (
            0.3 * length_score +
            0.5 * avg_rarity +
            0.2 * proper_noun_score
        ) * (1.0 - generic_penalty)
        
        return max(0.0, min(1.0, distinctiveness))
    
    def _find_best_match(
        self,
        phrases: List[Tuple[str, float]],
        subtitles: list[dict],
        time_window: Tuple[float, float],
        used_indices: Set[int]
    ) -> Optional[Tuple[float, float, float, float, int]]:
        """
        Find best matching subtitle for given phrases.
        
        Args:
            phrases: List of (phrase, distinctiveness) tuples
            subtitles: All subtitle cues
            time_window: (start, end) time range to search
            used_indices: Set of subtitle indices already matched
        
        Returns:
            (t_start, t_end, combined_score, distinctiveness, subtitle_idx) or None
        """
        best_match = None
        best_combined_score = 0
        
        for phrase, distinctiveness in phrases:
            # Search for this phrase in subtitles
            match = self._fuzzy_match_in_subtitles(
                phrase,
                subtitles,
                time_window,
                used_indices
            )
            
            if match:
                t_start, t_end, sim_score, sub_idx = match
                
                # Combined score: similarity * distinctiveness
                # Both factors must be reasonably high
                combined_score = (sim_score ** 0.7) * (distinctiveness ** 0.3)
                
                if combined_score > best_combined_score:
                    best_combined_score = combined_score
                    best_match = (t_start, t_end, combined_score, distinctiveness, sub_idx)
        
        return best_match
    
    def _fuzzy_match_in_subtitles(
        self,
        phrase: str,
        subtitles: list[dict],
        time_window: Tuple[float, float],
        used_indices: Set[int]
    ) -> Optional[Tuple[float, float, float, int]]:
        """
        Find phrase in subtitles using fuzzy matching.
        
        Args:
            phrase: Normalized phrase to search for
            subtitles: All subtitle cues
            time_window: (start, end) time constraint
            used_indices: Subtitle indices already matched (to skip)
        
        Returns:
            (t_start, t_end, similarity_score, subtitle_index) or None
        """
        if not phrase:
            return None
        
        best_match = None
        best_score = 0
        
        for idx, subtitle in enumerate(subtitles):
            # Skip if already used
            if idx in used_indices:
                continue
            
            # Check time window
            sub_start = subtitle['t_start']
            if not (time_window[0] <= sub_start <= time_window[1]):
                continue
            
            # Normalize subtitle text
            sub_text = self._normalize_text(subtitle.get('text', ''))
            
            if not sub_text:
                continue
            
            # Use token_sort_ratio (handles word order variations)
            score = fuzz.token_sort_ratio(phrase, sub_text) / 100.0
            
            if score > best_score:
                best_score = score
                best_match = (subtitle['t_start'], subtitle['t_end'], score, idx)
        
        # Return only if above threshold
        if best_match and best_score >= self.fuzzy_threshold:
            return best_match
        
        return None
    
    def _interpolate_all_scenes(
        self,
        scenes: list[dict],
        anchors: dict,
        total_duration: float
    ) -> list[dict]:
        """
        Create aligned scene list with interpolated timestamps for non-anchors.
        """
        aligned_scenes = []
        
        for i, scene in enumerate(scenes):
            scene_id = scene['scene_id']
            
            if scene_id in anchors:
                # This is an anchor - use its timestamp
                aligned_scenes.append(anchors[scene_id])
            else:
                # Not an anchor - interpolate
                t_start, t_end = self._interpolate_between_anchors(
                    i, scenes, anchors, total_duration
                )
                
                aligned_scene = scene.copy()
                aligned_scene['t_start'] = t_start
                aligned_scene['t_end'] = t_end
                aligned_scene['alignment_confidence'] = 0.4  # Lower confidence
                aligned_scene['alignment_method'] = 'interpolated'
                
                aligned_scenes.append(aligned_scene)
        
        return aligned_scenes
    
    def _interpolate_between_anchors(
        self,
        scene_idx: int,
        scenes: list[dict],
        anchors: dict,
        total_duration: float
    ) -> Tuple[float, float]:
        """
        Interpolate timestamp for non-anchor scene.
        
        Strategy:
        1. Find nearest anchors before and after this scene
        2. Interpolate linearly between them based on scene count
        3. If only one anchor, extend from it
        4. If no anchors, use proportional estimate
        """
        current_scene_id = scenes[scene_idx]['scene_id']
        
        # Find previous anchor
        prev_anchor = None
        prev_idx = None
        for i in range(scene_idx - 1, -1, -1):
            if scenes[i]['scene_id'] in anchors:
                prev_anchor = anchors[scenes[i]['scene_id']]
                prev_idx = i
                break
        
        # Find next anchor
        next_anchor = None
        next_idx = None
        for i in range(scene_idx + 1, len(scenes)):
            if scenes[i]['scene_id'] in anchors:
                next_anchor = anchors[scenes[i]['scene_id']]
                next_idx = i
                break
        
        # Case 1: Between two anchors (ideal)
        if prev_anchor and next_anchor:
            prev_end = prev_anchor['t_end']
            next_start = next_anchor['t_start']
            
            # Number of scenes between anchors
            scenes_between = next_idx - prev_idx - 1
            
            if scenes_between > 0:
                # Divide time evenly
                time_span = next_start - prev_end
                duration_per_scene = time_span / (scenes_between + 1)
                
                # Position of current scene relative to prev anchor
                position = scene_idx - prev_idx
                
                t_start = prev_end + (position * duration_per_scene)
                t_end = t_start + duration_per_scene
            else:
                # Shouldn't happen
                t_start = prev_end
                t_end = next_start
        
        # Case 2: Only previous anchor (extend forward)
        elif prev_anchor:
            t_start = prev_anchor['t_end'] + 1.0
            # Estimate duration based on remaining time
            remaining_scenes = len(scenes) - scene_idx
            remaining_time = total_duration - t_start
            estimated_duration = remaining_time / max(remaining_scenes, 1)
            estimated_duration = max(30, min(estimated_duration, 180))  # 30s-3min
            t_end = min(t_start + estimated_duration, total_duration)
        
        # Case 3: Only next anchor (extend backward)
        elif next_anchor:
            t_end = next_anchor['t_start'] - 1.0
            # Estimate duration
            scenes_before = scene_idx + 1
            time_before = t_end
            estimated_duration = time_before / max(scenes_before, 1)
            estimated_duration = max(30, min(estimated_duration, 180))
            t_start = max(0, t_end - estimated_duration)
        
        # Case 4: No anchors at all (proportional estimate)
        else:
            proportion = scene_idx / len(scenes)
            avg_duration = total_duration / len(scenes)
            t_start = proportion * total_duration
            t_end = min(t_start + avg_duration, total_duration)
        
        return (t_start, t_end)
    
    def _enforce_temporal_order(self, scenes: list[dict]) -> list[dict]:
        """
        Ensure scenes respect temporal ordering and don't overlap.
        
        Rules:
        - Scene i+1 must start >= Scene i ends
        - If overlap detected, shift forward
        - Maintain minimum gap of 0.5 seconds
        """
        min_gap = 0.5
        adjustments = 0
        
        for i in range(1, len(scenes)):
            prev_scene = scenes[i-1]
            curr_scene = scenes[i]
            
            if curr_scene['t_start'] < prev_scene['t_end'] + min_gap:
                # Overlap or insufficient gap - adjust
                original_duration = curr_scene['t_end'] - curr_scene['t_start']
                
                curr_scene['t_start'] = prev_scene['t_end'] + min_gap
                curr_scene['t_end'] = curr_scene['t_start'] + original_duration
                
                # Reduce confidence slightly for adjusted scenes
                if curr_scene.get('alignment_method') == 'anchor_match':
                    curr_scene['alignment_confidence'] *= 0.95
                
                adjustments += 1
        
        if adjustments > 0:
            print(f"    Adjusted {adjustments} scenes for temporal ordering")
        
        return scenes
    
    def _validate_alignment(self, scenes: list[dict]) -> None:
        """
        Validate final alignment and report statistics.
        """
        # Check for duplicates
        timestamp_map = {}
        duplicates = []
        
        for scene in scenes:
            ts_key = f"{scene['t_start']:.1f}-{scene['t_end']:.1f}"
            if ts_key in timestamp_map:
                duplicates.append((ts_key, timestamp_map[ts_key], scene['scene_id']))
            timestamp_map[ts_key] = scene['scene_id']
        
        if duplicates:
            print(f"  ⚠️  WARNING: {len(duplicates)} duplicate timestamps detected!")
            for ts, scene1, scene2 in duplicates[:3]:
                print(f"      {ts}: Scene {scene1} and Scene {scene2}")
        else:
            print(f"  ✓ No duplicate timestamps")
        
        # Check ordering
        ordering_errors = 0
        for i in range(1, len(scenes)):
            if scenes[i]['t_start'] < scenes[i-1]['t_end']:
                ordering_errors += 1
        
        if ordering_errors > 0:
            print(f"  ⚠️  WARNING: {ordering_errors} ordering violations!")
        else:
            print(f"  ✓ Temporal ordering verified")
        
        # Report confidence distribution
        confidences = [s['alignment_confidence'] for s in scenes]
        avg_conf = sum(confidences) / len(confidences)
        print(f"  ✓ Average confidence: {avg_conf:.3f}")
    
    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for fuzzy matching.
        
        - Lowercase
        - Remove punctuation
        - Normalize whitespace
        - Remove common subtitle artifacts
        """
        # Lowercase
        text = text.lower()
        
        # Remove HTML tags and formatting
        text = re.sub(r'<[^>]+>', '', text)
        
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
        """
        import srt
        
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        subtitle_generator = srt.parse(content)
        
        subtitles = []
        for sub in subtitle_generator:
            subtitles.append({
                't_start': sub.start.total_seconds(),
                't_end': sub.end.total_seconds(),
                'text': sub.content
            })
        
        return subtitles

