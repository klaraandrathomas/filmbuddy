"""
Script Parser

Parses movie screenplay files into structured scenes with:
- Scene headers (INT./EXT., location, time of day)
- Characters present in each scene
- Dialogue lines with speaker attribution
- Action/description lines
- Parenthetical directions
"""

import re
from typing import Optional


class ScriptParser:
    """Parser for standard screenplay format."""
    
    # Scene header patterns
    SCENE_HEADER_PATTERNS = [
        r'^(INT\.?/EXT\.?|EXT\.?/INT\.?|INT\.?|EXT\.?|I/E\.?)\s+',
        r'^(INTERIOR|EXTERIOR|INT|EXT)\s+',
    ]
    
    # Time of day keywords
    TIME_OF_DAY_KEYWORDS = [
        'DAY', 'NIGHT', 'DAWN', 'DUSK', 'MORNING', 'AFTERNOON', 
        'EVENING', 'SUNSET', 'SUNRISE', 'CONTINUOUS', 'LATER',
        'SAME', 'MOMENTS LATER', 'SAME TIME'
    ]
    
    def parse_script(self, script_text: str) -> list[dict]:
        """
        Parse screenplay text into structured scenes.
        
        Args:
            script_text: Full screenplay as string
        
        Returns:
            list of scene dicts with keys:
                - scene_id: int (1-indexed)
                - scene_header: str (e.g., "INT. COFFEE SHOP - DAY")
                - location: str (e.g., "COFFEE SHOP")
                - time_of_day: str (e.g., "DAY", "NIGHT", "CONTINUOUS")
                - int_ext: str ("INT" | "EXT" | "INT/EXT")
                - characters: list[str] (e.g., ["MIA", "MANAGER"])
                - dialogue: list[dict] with character, text, parenthetical
                - action_lines: list[str]
                - raw_text: str (original scene text)
        """
        lines = script_text.split('\n')
        scenes = []
        current_scene = None
        current_character = None
        current_dialogue = None
        scene_start_line = 0
        
        for i, line in enumerate(lines):
            # Check if this is a scene header
            if self._is_scene_header(line):
                # Save previous scene if exists
                if current_scene:
                    current_scene['raw_text'] = '\n'.join(
                        lines[scene_start_line:i]
                    ).strip()
                    scenes.append(current_scene)
                
                # Start new scene
                scene_start_line = i
                current_scene = {
                    'scene_id': len(scenes) + 1,
                    'scene_header': line.strip(),
                    'location': self._extract_location(line),
                    'time_of_day': self._extract_time_of_day(line),
                    'int_ext': self._extract_int_ext(line),
                    'characters': [],
                    'dialogue': [],
                    'action_lines': [],
                    'raw_text': ''
                }
                current_character = None
                current_dialogue = None
                continue
            
            # Skip if no scene started yet (script may have title page)
            if not current_scene:
                continue
            
            # Skip empty lines
            if not line.strip():
                current_character = None
                current_dialogue = None
                continue
            
            # Check if this is a character name
            if self._is_character_name(line):
                current_character = self._clean_character_name(line)
                if current_character not in current_scene['characters']:
                    current_scene['characters'].append(current_character)
                current_dialogue = {
                    'character': current_character,
                    'text': '',
                    'parenthetical': None
                }
                continue
            
            # Check if this is a parenthetical
            if self._is_parenthetical(line) and current_character:
                if current_dialogue:
                    current_dialogue['parenthetical'] = line.strip()
                continue
            
            # Check if this is dialogue (follows a character name)
            if current_character and current_dialogue is not None:
                # It's dialogue
                dialogue_text = line.strip()
                if dialogue_text:
                    if current_dialogue['text']:
                        current_dialogue['text'] += ' ' + dialogue_text
                    else:
                        current_dialogue['text'] = dialogue_text
                    
                    # If this is the first text after character, add dialogue entry
                    if not any(d.get('character') == current_character and 
                              d.get('text') == current_dialogue['text'] 
                              for d in current_scene['dialogue']):
                        current_scene['dialogue'].append(current_dialogue.copy())
                continue
            
            # Otherwise, it's an action line
            if self._is_action_line(line):
                action_text = line.strip()
                if action_text:
                    current_scene['action_lines'].append(action_text)
                current_character = None
                current_dialogue = None
        
        # Don't forget the last scene
        if current_scene:
            current_scene['raw_text'] = '\n'.join(
                lines[scene_start_line:]
            ).strip()
            scenes.append(current_scene)
        
        return scenes
    
    def _is_scene_header(self, line: str) -> bool:
        """
        Detect if line is a scene header.
        
        Scene headers typically start with:
        - INT. / EXT. / INT./EXT.
        - I/E. (shorthand)
        
        Examples:
        - "INT. COFFEE SHOP - DAY"
        - "EXT. BEACH - SUNSET"
        - "INT./EXT. CAR - MOVING - NIGHT"
        """
        line_upper = line.strip().upper()
        
        # Must be somewhat short (scene headers are typically < 100 chars)
        if len(line_upper) > 150:
            return False
        
        # Check against patterns
        for pattern in self.SCENE_HEADER_PATTERNS:
            if re.match(pattern, line_upper, re.IGNORECASE):
                return True
        
        return False
    
    def _extract_location(self, header: str) -> str:
        """
        Extract location from scene header.
        
        "INT. COFFEE SHOP - DAY" → "COFFEE SHOP"
        "EXT. LOS ANGELES SKYLINE - NIGHT" → "LOS ANGELES SKYLINE"
        """
        header = header.strip()
        
        # Remove INT./EXT. prefix
        for pattern in self.SCENE_HEADER_PATTERNS:
            header = re.sub(pattern, '', header, flags=re.IGNORECASE)
        
        # Split by dash to separate location from time
        parts = header.split('-')
        if parts:
            location = parts[0].strip()
            return location
        
        return header.strip()
    
    def _extract_time_of_day(self, header: str) -> Optional[str]:
        """
        Extract time of day from scene header.
        
        Returns: "DAY", "NIGHT", "DUSK", "DAWN", "CONTINUOUS", "LATER", "SAME", or None
        """
        header_upper = header.upper()
        
        # Check for each time keyword
        for time_keyword in self.TIME_OF_DAY_KEYWORDS:
            if time_keyword in header_upper:
                return time_keyword
        
        return None
    
    def _extract_int_ext(self, header: str) -> str:
        """
        Extract INT/EXT designation from header.
        
        Returns: "INT", "EXT", or "INT/EXT"
        """
        header_upper = header.strip().upper()
        
        if header_upper.startswith('INT./EXT') or header_upper.startswith('INT/EXT'):
            return "INT/EXT"
        elif header_upper.startswith('EXT./INT') or header_upper.startswith('EXT/INT'):
            return "INT/EXT"
        elif header_upper.startswith('I/E'):
            return "INT/EXT"
        elif header_upper.startswith('INT'):
            return "INT"
        elif header_upper.startswith('EXT'):
            return "EXT"
        
        return "INT"  # Default
    
    def _is_character_name(self, line: str) -> bool:
        """
        Detect if line is a character name (dialogue cue).
        
        Character names can be:
        - ALL CAPS or mostly caps
        - Centered (10+ spaces) OR left-aligned (different script formats)
        - May have extensions: (V.O.), (O.S.), (CONT'D)
        
        Examples:
        - "          MIA" (centered format)
        - "BIANCA" (left-aligned format)
        - "          SEBASTIAN (V.O.)"
        - "PATRICK (CONT'D)"
        """
        stripped = line.strip()
        
        # Check if line is centered (traditional format)
        is_centered = line.startswith(' ' * 10)
        
        # Check if line is left-aligned but still looks like a character name
        # (short, all caps, no scene header indicators)
        is_left_aligned_char = (
            not line.startswith(' ') and  # No leading space
            len(stripped) > 0 and
            len(stripped) < 40 and  # Character names are short
            not any(word in stripped.upper() for word in ['INT.', 'EXT.', 'I/E', 'FADE', 'CUT TO', 'DISSOLVE'])
        )
        
        # Must be one of the two formats
        if not (is_centered or is_left_aligned_char):
            return False
        
        # Must not be empty
        if not stripped:
            return False
        
        # Remove common extensions
        cleaned = re.sub(r'\s*\(.*?\)\s*', '', stripped)
        
        # Must be all uppercase letters (and spaces, for multi-word names)
        if not cleaned.replace(' ', '').replace('.', '').replace("'", '').isalpha():
            return False
        
        # Must be ALL CAPS
        if cleaned != cleaned.upper():
            return False
        
        # Character names are typically short (< 30 chars without extensions)
        if len(cleaned) > 30:
            return False
        
        # Must not look like a scene header
        if self._is_scene_header(line):
            return False
        
        return True
    
    def _clean_character_name(self, line: str) -> str:
        """
        Clean character name by removing extensions.
        
        "MIA (V.O.)" → "MIA"
        "SEBASTIAN (CONT'D)" → "SEBASTIAN"
        """
        stripped = line.strip()
        
        # Remove extensions: (V.O.), (O.S.), (CONT'D), etc.
        cleaned = re.sub(r'\s*\(.*?\)\s*', '', stripped)
        
        return cleaned.strip()
    
    def _is_parenthetical(self, line: str) -> bool:
        """
        Detect parenthetical direction.
        
        Parentheticals are in parentheses and describe how to deliver:
        - "(softly)"
        - "(to Sebastian)"
        - "(laughing)"
        """
        stripped = line.strip()
        return stripped.startswith('(') and stripped.endswith(')')
    
    def _is_action_line(self, line: str) -> bool:
        """
        Detect action/description lines.
        
        Action lines:
        - Left-aligned or slightly indented (not as much as dialogue)
        - Not all caps (unless shouting)
        - Describe what we SEE
        """
        # Has some text
        if not line.strip():
            return False
        
        # Not heavily indented (character names and dialogue are indented more)
        if line.startswith(' ' * 10):
            return False
        
        # Not a scene header
        if self._is_scene_header(line):
            return False
        
        # Not a parenthetical
        if self._is_parenthetical(line):
            return False
        
        return True
