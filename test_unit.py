#!/usr/bin/env python3
"""
Unit Tests for FilmBuddy Components (Step 9)

Tests individual components in isolation.
"""

from preprocessing.script_parser import ScriptParser
from preprocessing.timestamp_aligner import TimestampAligner


class TestScriptParser:
    """Test script parsing functionality."""
    
    def setup_method(self):
        self.parser = ScriptParser()
    
    def test_scene_header_detection(self):
        """Test scene header detection with various formats."""
        # Standard formats
        assert self.parser._is_scene_header("INT. COFFEE SHOP - DAY")
        assert self.parser._is_scene_header("EXT. BEACH - SUNSET")
        assert self.parser._is_scene_header("INT./EXT. CAR - MOVING - NIGHT")
        assert self.parser._is_scene_header("I/E. APARTMENT - CONTINUOUS")
        
        # Edge cases
        assert self.parser._is_scene_header("INT. COFFEE SHOP - DAY - CONTINUOUS")
        assert not self.parser._is_scene_header("MIA enters the room")
        assert not self.parser._is_scene_header("                    MIA")
        
        print("✓ Scene header detection working")
    
    def test_location_extraction(self):
        """Test location extraction from scene headers."""
        assert self.parser._extract_location("INT. COFFEE SHOP - DAY") == "COFFEE SHOP"
        assert self.parser._extract_location("EXT. LOS ANGELES SKYLINE - NIGHT") == "LOS ANGELES SKYLINE"
        assert self.parser._extract_location("INT./EXT. CAR - MOVING - NIGHT") == "CAR"
        
        print("✓ Location extraction working")
    
    def test_time_of_day_extraction(self):
        """Test time of day extraction."""
        assert self.parser._extract_time_of_day("INT. ROOM - DAY") == "DAY"
        assert self.parser._extract_time_of_day("EXT. BEACH - SUNSET") == "SUNSET"
        assert self.parser._extract_time_of_day("INT. ROOM - NIGHT") == "NIGHT"
        assert self.parser._extract_time_of_day("INT. ROOM - CONTINUOUS") == "CONTINUOUS"
        
        print("✓ Time of day extraction working")
    
    def test_character_name_detection(self):
        """Test character name detection in dialogue."""
        # Valid character names
        assert self.parser._is_character_name("                    MIA")
        assert self.parser._is_character_name("          SEBASTIAN (V.O.)")
        assert self.parser._is_character_name("          MIA (CONT'D)")
        
        # Invalid
        assert not self.parser._is_character_name("She enters the room")
        assert not self.parser._is_character_name("INT. COFFEE SHOP - DAY")
        
        print("✓ Character name detection working")
    
    def test_character_name_cleaning(self):
        """Test removal of dialogue extensions."""
        assert self.parser._clean_character_name("MIA (V.O.)") == "MIA"
        assert self.parser._clean_character_name("SEBASTIAN (CONT'D)") == "SEBASTIAN"
        assert self.parser._clean_character_name("MIA (O.S.)") == "MIA"
        assert self.parser._clean_character_name("MIA") == "MIA"
        
        print("✓ Character name cleaning working")
    
    def test_full_script_parsing(self):
        """Test parsing a complete script sample."""
        script = """
INT. COFFEE SHOP - DAY

MIA enters, looking harried.

                    MIA
          Sorry I'm late.

                    MANAGER
          This is the third time.

EXT. BEACH - SUNSET

Sebastian walks along the shore.

                    SEBASTIAN (V.O.)
          I never thought I'd end up here.
"""
        
        scenes = self.parser.parse_script(script)
        
        # Should have 2 scenes
        assert len(scenes) == 2, f"Expected 2 scenes, got {len(scenes)}"
        
        # Check scene 1
        assert scenes[0]["location"] == "COFFEE SHOP"
        assert scenes[0]["time_of_day"] == "DAY"
        assert scenes[0]["int_ext"] == "INT"
        assert "MIA" in scenes[0]["characters"]
        assert "MANAGER" in scenes[0]["characters"]
        assert len(scenes[0]["dialogue"]) == 2
        
        # Check scene 2
        assert scenes[1]["location"] == "BEACH"
        assert scenes[1]["time_of_day"] == "SUNSET"
        assert "SEBASTIAN" in scenes[1]["characters"]
        
        print(f"✓ Full script parsing working ({len(scenes)} scenes)")


class TestTimestampAligner:
    """Test timestamp alignment functionality."""
    
    def setup_method(self):
        self.aligner = TimestampAligner()
    
    def test_key_dialogue_extraction(self):
        """Test extraction of searchable dialogue phrases."""
        scene = {
            "dialogue": [
                {"text": "Hello, how are you?"},
                {"text": "I'm fine, thanks for asking."},
                {"text": "Great to hear!"}
            ]
        }
        
        phrases = self.aligner._extract_key_dialogue(scene)
        
        # Should extract meaningful phrases
        assert len(phrases) > 0
        assert any("hello" in p.lower() for p in phrases)
        
        print(f"✓ Key dialogue extraction working ({len(phrases)} phrases)")
    
    def test_empty_dialogue_handling(self):
        """Test handling scenes without dialogue."""
        scene = {
            "dialogue": [],
            "action_lines": ["A beautiful sunset over the ocean."]
        }
        
        phrases = self.aligner._extract_key_dialogue(scene)
        
        # Should return empty list for no dialogue
        assert isinstance(phrases, list)
        
        print("✓ Empty dialogue handling working")
    
    def test_srt_parsing(self):
        """Test SRT subtitle parsing."""
        # Create a minimal SRT sample
        srt_content = """1
00:00:10,500 --> 00:00:13,000
Hello, world!

2
00:00:14,000 --> 00:00:18,000
This is a test subtitle.
"""
        
        # Write to temp file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
            f.write(srt_content)
            temp_path = f.name
        
        try:
            subtitles = self.aligner.parse_srt(temp_path)
            
            assert len(subtitles) == 2
            assert subtitles[0]["t_start"] == 10.5
            assert subtitles[0]["t_end"] == 13.0
            assert "Hello" in subtitles[0]["text"]
            
            print(f"✓ SRT parsing working ({len(subtitles)} cues)")
        finally:
            import os
            os.unlink(temp_path)


def run_unit_tests():
    """Run all unit tests."""
    print("="*70)
    print("STEP 9 - UNIT TESTS")
    print("="*70)
    print()
    
    # Test ScriptParser
    print("[1/2] Testing ScriptParser...")
    parser_tests = TestScriptParser()
    parser_tests.setup_method()
    
    try:
        parser_tests.test_scene_header_detection()
        parser_tests.test_location_extraction()
        parser_tests.test_time_of_day_extraction()
        parser_tests.test_character_name_detection()
        parser_tests.test_character_name_cleaning()
        parser_tests.test_full_script_parsing()
        print("  ✅ All ScriptParser tests passed\n")
    except AssertionError as e:
        print(f"  ❌ ScriptParser test failed: {e}\n")
        return False
    
    # Test TimestampAligner
    print("[2/2] Testing TimestampAligner...")
    aligner_tests = TestTimestampAligner()
    aligner_tests.setup_method()
    
    try:
        aligner_tests.test_key_dialogue_extraction()
        aligner_tests.test_empty_dialogue_handling()
        aligner_tests.test_srt_parsing()
        print("  ✅ All TimestampAligner tests passed\n")
    except AssertionError as e:
        print(f"  ❌ TimestampAligner test failed: {e}\n")
        return False
    
    print("="*70)
    print("✅ ALL UNIT TESTS PASSED")
    print("="*70)
    
    return True


if __name__ == "__main__":
    import sys
    success = run_unit_tests()
    sys.exit(0 if success else 1)

