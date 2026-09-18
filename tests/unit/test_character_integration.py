#!/usr/bin/env python3
"""
Unit tests for Character Integration with Episode Processing.

This module tests the integration of character analysis data into episode
processing, including character weight calculation, timing adjustments,
and prompt enhancement with character context.

Following TDD methodology - these tests should FAIL initially (RED phase).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

# Import the module we're testing - will fail initially
try:
    from core.character_episode_enhancer import (
        EpisodeCharacterEnhancer,
        CharacterWeight,
    )
except ImportError:
    # Expected to fail in RED phase
    pass


class TestEpisodeCharacterEnhancer:
    """Test suite for character analysis integration into episode processing."""

    # sample_episode_content / sample_character_analysis come from tests/conftest.py

    @pytest.fixture
    def mock_character_analyzer(self):
        """Mock character analyzer dependency."""
        analyzer = AsyncMock()
        analyzer.get_character_profile = AsyncMock(
            return_value={
                "importance_score": 0.8,
                "character_development": 0.7,
                "screen_time_percentage": 0.3,
            }
        )
        return analyzer

    @pytest.fixture
    def mock_timing_calculator(self):
        """Mock timing calculator dependency."""
        calculator = MagicMock()
        calculator.calculate_base_duration = MagicMock(return_value=3.0)
        return calculator

    @pytest.fixture
    def enhancer(self, mock_character_analyzer, mock_timing_calculator):
        """Create EpisodeCharacterEnhancer instance."""
        return EpisodeCharacterEnhancer(
            character_analyzer=mock_character_analyzer,
            timing_calculator=mock_timing_calculator,
        )

    @pytest.mark.asyncio
    async def test_character_weight_calculation_accuracy(
        self, enhancer, sample_character_analysis
    ):
        """
        Test accurate character weight calculation from analysis data.

        RED PHASE: This test should FAIL initially because the implementation doesn't exist.

        Validates:
        - Character weights are calculated correctly from importance scores
        - Weights include all required fields (importance, development, screen_time)
        - Weights are properly ordered by importance
        """
        # Arrange
        scene_characters = ["Naruto", "Sasuke"]

        # Act
        weights = await enhancer._calculate_character_weights(
            scene_characters, sample_character_analysis
        )

        # Assert
        assert len(weights) == 2, "Should calculate weights for both characters"
        assert all(
            isinstance(w, CharacterWeight) for w in weights
        ), "Should return CharacterWeight objects"

        # Find specific character weights
        naruto_weight = next((w for w in weights if w.character_name == "Naruto"), None)
        sasuke_weight = next((w for w in weights if w.character_name == "Sasuke"), None)

        assert naruto_weight is not None, "Should find Naruto's character weight"
        assert sasuke_weight is not None, "Should find Sasuke's character weight"

        # Validate weight values
        assert (
            naruto_weight.importance_score == 0.9
        ), "Naruto should have 0.9 importance score"
        assert (
            sasuke_weight.importance_score == 0.85
        ), "Sasuke should have 0.85 importance score"
        assert (
            naruto_weight.character_development == 0.8
        ), "Naruto should have 0.8 development factor"
        assert (
            sasuke_weight.character_development == 0.9
        ), "Sasuke should have 0.9 development factor"

        # Validate ordering
        assert (
            naruto_weight.importance_score > sasuke_weight.importance_score
        ), "Naruto should have higher importance than Sasuke"

    @pytest.mark.asyncio
    async def test_timing_adjustment_with_character_weights(self, enhancer):
        """
        Test timing adjustment based on character importance weights.

        RED PHASE: This test should FAIL initially.

        Validates:
        - Base duration is adjusted based on character weights
        - Important characters get longer scene durations
        - Adjustments stay within reasonable bounds (1.5-15.0 seconds)
        - Multiple characters combine weights appropriately
        """
        # Arrange
        base_duration = 3.0
        character_weights = [
            CharacterWeight("Naruto", 0.9, 0.8, 0.4),
            CharacterWeight("Sasuke", 0.85, 0.9, 0.3),
        ]

        # Act
        adjusted_duration = enhancer._adjust_timing_for_characters(
            base_duration, character_weights
        )

        # Assert
        assert isinstance(adjusted_duration, float), "Should return float duration"
        assert (
            adjusted_duration > base_duration
        ), "Duration should be extended for important characters"
        assert (
            1.5 <= adjusted_duration <= 15.0
        ), "Adjusted duration should be within reasonable bounds"

        # Test with single low-importance character
        low_importance_weights = [CharacterWeight("Minor Character", 0.2, 0.1, 0.05)]
        low_adjusted_duration = enhancer._adjust_timing_for_characters(
            base_duration, low_importance_weights
        )
        assert (
            low_adjusted_duration <= adjusted_duration
        ), "Low importance characters should get less time"

    @pytest.mark.asyncio
    async def test_prompt_enhancement_with_character_context(
        self, enhancer, sample_character_analysis
    ):
        """
        Test prompt enhancement with character appearance consistency.

        RED PHASE: This test should FAIL initially.

        Validates:
        - Base prompts are enhanced with character appearance details
        - Character personality traits are incorporated
        - Multiple characters are handled correctly
        - Enhanced prompts maintain original scene context
        """
        # Arrange
        base_prompt = "Naruto and Sasuke facing each other in battle"
        scene_characters = ["Naruto", "Sasuke"]

        # Act
        enhanced_prompt = await enhancer._enhance_prompt_with_character_context(
            base_prompt, scene_characters, sample_character_analysis
        )

        # Assert
        assert isinstance(enhanced_prompt, str), "Should return string prompt"
        assert len(enhanced_prompt) > len(
            base_prompt
        ), "Enhanced prompt should be longer than base prompt"
        assert (
            base_prompt in enhanced_prompt
        ), "Enhanced prompt should contain original scene description"
        assert "Naruto" in enhanced_prompt, "Should include Naruto's name"
        assert "Sasuke" in enhanced_prompt, "Should include Sasuke's name"

        # Check for personality trait inclusion
        assert any(
            trait in enhanced_prompt.lower()
            for trait in ["determined", "brave", "kind"]
        ), "Should include Naruto's personality traits"
        assert any(
            trait in enhanced_prompt.lower() for trait in ["intelligent", "confident"]
        ), "Should include Sasuke's personality traits"

    @pytest.mark.asyncio
    async def test_full_episode_enhancement_workflow(
        self, enhancer, sample_episode_content, sample_character_analysis
    ):
        """
        Test complete episode enhancement workflow.

        RED PHASE: This test should FAIL initially.

        Validates:
        - Complete episode processing with character integration
        - All scenes are enhanced with character data
        - Episode structure is preserved with enhancements
        - Total duration is calculated correctly
        - Character focus data is included
        """
        # Act
        enhanced_episode = await enhancer.enhance_episode_with_character_data(
            sample_episode_content, sample_character_analysis
        )

        # Assert episode structure
        assert isinstance(enhanced_episode, dict), "Should return episode dictionary"
        assert "scenes" in enhanced_episode, "Should contain scenes"
        assert (
            "character_focus" in enhanced_episode
        ), "Should contain character focus data"
        assert "total_duration" in enhanced_episode, "Should contain total duration"

        # Assert scene enhancements
        enhanced_scenes = enhanced_episode["scenes"]
        original_scenes = sample_episode_content["scenes"]

        assert len(enhanced_scenes) == len(
            original_scenes
        ), "Should maintain same number of scenes"

        for i, (original, enhanced) in enumerate(zip(original_scenes, enhanced_scenes)):
            # Check required enhancements
            assert "duration" in enhanced, f"Scene {i} should have enhanced duration"
            assert (
                "enhanced_prompt" in enhanced
            ), f"Scene {i} should have enhanced prompt"
            assert (
                "character_weights" in enhanced
            ), f"Scene {i} should have character weights"

            # Check that durations are adjusted (not equal to base_duration)
            assert (
                enhanced["duration"] != original["base_duration"]
            ), f"Scene {i} duration should be adjusted from base duration"

            # Check character weights structure
            weights = enhanced["character_weights"]
            assert isinstance(weights, list), f"Scene {i} weights should be a list"
            assert all(
                isinstance(w, CharacterWeight) for w in weights
            ), f"Scene {i} should contain CharacterWeight objects"

        # Assert total duration calculation
        calculated_total = sum(scene["duration"] for scene in enhanced_scenes)
        assert (
            abs(enhanced_episode["total_duration"] - calculated_total) < 0.1
        ), "Total duration should match sum of scene durations"

    @pytest.mark.asyncio
    async def test_scene_character_identification(
        self, enhancer, sample_episode_content
    ):
        """
        Test identification of characters in individual scenes.

        RED PHASE: This test should FAIL initially.

        Validates:
        - Characters are correctly identified from scene data
        - Character lists are cleaned and normalized
        - Edge cases (no characters, unknown characters) are handled
        """
        # Arrange
        scene_with_characters = sample_episode_content["scenes"][0]  # Naruto, Sasuke
        scene_single_character = sample_episode_content["scenes"][1]  # Sakura only

        # Act
        multi_char_result = enhancer._identify_scene_characters(
            scene_with_characters, ["Naruto", "Sasuke", "Sakura"]
        )
        single_char_result = enhancer._identify_scene_characters(
            scene_single_character, ["Naruto", "Sasuke", "Sakura"]
        )

        # Assert
        assert (
            "Naruto" in multi_char_result
        ), "Should identify Naruto in multi-character scene"
        assert (
            "Sasuke" in multi_char_result
        ), "Should identify Sasuke in multi-character scene"
        assert len(multi_char_result) == 2, "Should identify exactly 2 characters"

        assert (
            "Sakura" in single_char_result
        ), "Should identify Sakura in single-character scene"
        assert len(single_char_result) == 1, "Should identify exactly 1 character"

    @pytest.mark.asyncio
    async def test_character_weight_edge_cases(
        self, enhancer, sample_character_analysis
    ):
        """
        Test character weight calculation edge cases.

        RED PHASE: This test should FAIL initially.

        Validates:
        - Unknown characters are handled gracefully
        - Empty character lists are handled
        - Missing analysis data is handled with defaults
        - Character weights are bounded correctly
        """
        # Test with unknown character
        unknown_characters = ["Unknown Character"]
        weights_unknown = await enhancer._calculate_character_weights(
            unknown_characters, sample_character_analysis
        )
        assert (
            len(weights_unknown) == 0
        ), "Unknown characters should return empty weights"

        # Test with empty character list
        empty_characters = []
        weights_empty = await enhancer._calculate_character_weights(
            empty_characters, sample_character_analysis
        )
        assert (
            len(weights_empty) == 0
        ), "Empty character list should return empty weights"

        # Test with partial data
        partial_analysis = {
            "profiles": {
                "TestChar": {
                    "importance_score": 1.5,  # Above maximum
                    "character_development": -0.1,  # Below minimum
                    # Missing screen_time_percentage
                }
            }
        }

        weights_partial = await enhancer._calculate_character_weights(
            ["TestChar"], partial_analysis
        )
        assert len(weights_partial) == 1, "Should handle partial data"
        weight = weights_partial[0]
        assert (
            0.0 <= weight.importance_score <= 1.0
        ), "Should clamp importance score to valid range"
        assert (
            0.0 <= weight.character_development <= 1.0
        ), "Should clamp development to valid range"

    @pytest.mark.asyncio
    async def test_timing_adjustment_constraints(self, enhancer):
        """
        Test timing adjustment stays within specified constraints.

        RED PHASE: This test should FAIL initially.

        Validates:
        - Minimum duration constraint (1.5 seconds)
        - Maximum duration constraint (15.0 seconds)
        - Proportional adjustment based on character importance
        - Zero or negative base durations are handled
        """
        # Test minimum constraint
        short_duration = 0.5
        high_importance_weights = [CharacterWeight("MainChar", 1.0, 1.0, 0.5)]

        adjusted_short = enhancer._adjust_timing_for_characters(
            short_duration, high_importance_weights
        )
        assert adjusted_short >= 1.5, "Should enforce minimum duration of 1.5 seconds"

        # Test maximum constraint
        long_duration = 20.0
        adjusted_long = enhancer._adjust_timing_for_characters(
            long_duration, high_importance_weights
        )
        assert adjusted_long <= 15.0, "Should enforce maximum duration of 15.0 seconds"

        # Test proportional adjustment
        medium_duration = 5.0
        low_importance_weights = [CharacterWeight("MinorChar", 0.1, 0.1, 0.02)]

        adjusted_low = enhancer._adjust_timing_for_characters(
            medium_duration, low_importance_weights
        )
        adjusted_high = enhancer._adjust_timing_for_characters(
            medium_duration, high_importance_weights
        )

        assert (
            adjusted_high > adjusted_low
        ), "High importance characters should get longer durations"

    @pytest.mark.asyncio
    async def test_character_context_prompt_structure(
        self, enhancer, sample_character_analysis
    ):
        """
        Test structure and quality of character-enhanced prompts.

        RED PHASE: This test should FAIL initially.

        Validates:
        - Enhanced prompts follow expected structure
        - Character appearance details are included
        - Personality traits influence visual description
        - Multiple characters are balanced in prompt
        """
        # Arrange
        base_prompt = "Epic battle scene"
        characters = ["Naruto", "Sasuke"]

        # Act
        enhanced_prompt = await enhancer._enhance_prompt_with_character_context(
            base_prompt, characters, sample_character_analysis
        )

        # Assert prompt structure
        assert (
            "Epic battle scene" in enhanced_prompt
        ), "Should preserve original scene description"

        # Check character-specific enhancements
        naruto_traits = sample_character_analysis["profiles"]["Naruto"][
            "personality_traits"
        ]
        sasuke_traits = sample_character_analysis["profiles"]["Sasuke"][
            "personality_traits"
        ]

        enhanced_lower = enhanced_prompt.lower()
        assert any(
            trait in enhanced_lower for trait in naruto_traits
        ), "Should include Naruto's personality traits"
        assert any(
            trait in enhanced_lower for trait in sasuke_traits
        ), "Should include Sasuke's personality traits"

        # Check for visual consistency keywords
        consistency_keywords = ["consistent", "appearance", "style", "character design"]
        assert any(
            keyword in enhanced_lower for keyword in consistency_keywords
        ), "Should include visual consistency instructions"

    @pytest.mark.asyncio
    async def test_episode_character_extraction(self, enhancer, sample_episode_content):
        """
        Test extraction of episode characters from content.

        RED PHASE: This test should FAIL initially.

        Validates:
        - All characters across scenes are identified
        - Character names are deduplicated
        - Character list is properly formatted
        """
        # Act
        episode_characters = await enhancer._extract_episode_characters(
            sample_episode_content
        )

        # Assert
        expected_characters = {"Naruto", "Sasuke", "Sakura"}
        assert (
            set(episode_characters) == expected_characters
        ), f"Should extract all characters: {expected_characters}"
        assert len(episode_characters) == 3, "Should have exactly 3 unique characters"

    @pytest.mark.asyncio
    async def test_performance_constraints(
        self, enhancer, sample_episode_content, sample_character_analysis
    ):
        """
        Test that character integration meets performance constraints.

        RED PHASE: This test should FAIL initially.

        Validates:
        - Character integration completes within 500ms
        - Memory usage stays reasonable
        - Processing scales with episode size
        """
        import time
        import psutil
        import gc

        # Measure initial memory
        gc.collect()
        initial_memory = psutil.Process().memory_info().rss / 1024**2  # MB

        # Measure processing time
        start_time = time.time()

        # Act
        enhanced_episode = await enhancer.enhance_episode_with_character_data(
            sample_episode_content, sample_character_analysis
        )

        # Measure completion
        end_time = time.time()
        processing_time = (end_time - start_time) * 1000  # Convert to milliseconds

        gc.collect()
        final_memory = psutil.Process().memory_info().rss / 1024**2  # MB
        memory_increase = final_memory - initial_memory

        # Assert performance constraints
        assert (
            processing_time < 500
        ), f"Character integration should complete within 500ms, took {processing_time:.1f}ms"
        assert (
            memory_increase < 100
        ), f"Memory increase should be minimal, increased by {memory_increase:.1f}MB"
        assert enhanced_episode is not None, "Should successfully process episode"

    @pytest.mark.asyncio
    async def test_error_handling_graceful_degradation(
        self, enhancer, sample_episode_content
    ):
        """
        Test graceful error handling when character analysis is unavailable.

        RED PHASE: This test should FAIL initially.

        Validates:
        - System continues functioning without character analysis
        - Default timing is used when character data is missing
        - Prompts are minimally enhanced or left unchanged
        - Error conditions don't crash the system
        """
        # Test with empty character analysis
        empty_analysis = {"profiles": {}}

        enhanced_episode = await enhancer.enhance_episode_with_character_data(
            sample_episode_content, empty_analysis
        )

        assert enhanced_episode is not None, "Should handle empty character analysis"
        assert "scenes" in enhanced_episode, "Should return valid episode structure"

        # Test with malformed character analysis
        malformed_analysis = {"invalid": "structure"}

        try:
            enhanced_episode = await enhancer.enhance_episode_with_character_data(
                sample_episode_content, malformed_analysis
            )
            # Should either work with defaults or raise appropriate exception
            assert (
                enhanced_episode is not None
            ), "Should handle malformed analysis gracefully"
        except (KeyError, ValueError) as e:
            # Acceptable to raise specific exceptions for malformed data
            assert "profiles" in str(e) or "character" in str(
                e
            ), "Should raise descriptive error about missing character data"

    @pytest.mark.asyncio
    async def test_character_weight_combination_logic(self, enhancer):
        """
        Test how multiple character weights combine in scenes.

        RED PHASE: This test should FAIL initially.

        Validates:
        - Multiple character weights are combined logically
        - Weight combination follows specified algorithm
        - Edge cases (single character, many characters) work
        """
        # Test single character
        single_weight = [CharacterWeight("Solo", 0.8, 0.7, 0.3)]
        single_duration = enhancer._adjust_timing_for_characters(3.0, single_weight)

        # Test multiple characters with different importance
        multiple_weights = [
            CharacterWeight("Main", 0.9, 0.8, 0.4),
            CharacterWeight("Support", 0.5, 0.4, 0.2),
            CharacterWeight("Minor", 0.2, 0.2, 0.1),
        ]
        multiple_duration = enhancer._adjust_timing_for_characters(
            3.0, multiple_weights
        )

        # Test many characters (should handle efficiently)
        many_weights = [CharacterWeight(f"Char{i}", 0.3, 0.3, 0.1) for i in range(10)]
        many_duration = enhancer._adjust_timing_for_characters(3.0, many_weights)

        # Assert logical relationships
        assert (
            multiple_duration > single_duration
        ), "Multiple important characters should extend duration more"
        assert (
            1.5 <= many_duration <= 15.0
        ), "Many characters should still respect duration bounds"


# Integration test placeholder (will be implemented in integration phase)
class TestCharacterIntegrationWithExistingAgents:
    """Integration tests with existing character analysis agent."""

    @pytest.mark.asyncio
    async def test_integration_with_character_analysis_agent(self):
        """
        Test integration with existing CharacterAnalysisAgent.

        This test will validate that the new enhancer works correctly
        with the existing character analysis infrastructure.
        """
        # Will be implemented after core functionality is working
        pytest.skip("Integration test - implement after core functionality")


if __name__ == "__main__":
    # Run tests to verify they fail (RED phase)
    pytest.main([__file__, "-v"])
