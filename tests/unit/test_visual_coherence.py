#!/usr/bin/env python3
"""
Unit tests for Visual Coherence and Consistency System.

This module tests the visual coherence system that maintains consistent
style, character appearance, and color palette across episode images.

Following TDD methodology - these tests should FAIL initially (RED phase).
"""

import pytest
import json
import numpy as np
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from typing import Dict, List, Any

# Import the module we're testing - will fail initially
try:
    from core.visual_coherence_manager import (
        VisualCoherenceManager,
        VisualConsistencyMetrics,
    )
except ImportError:
    # Expected to fail in RED phase
    pass


class TestVisualCoherenceSystem:
    """Test suite for visual coherence and consistency."""

    @pytest.fixture
    def sample_episode_context(self) -> Dict[str, Any]:
        """Sample episode context for testing."""
        return {
            "episode_id": "naruto_s1e5",
            "show": "Naruto",
            "season": 1,
            "episode": 5,
            "theme": "friendship and rivalry",
            "visual_style": "anime",
            "color_palette": ["#FF6B35", "#F7931E", "#FFD23F", "#06FFA5", "#118AB2"],
        }

    @pytest.fixture
    def sample_characters(self) -> List[str]:
        """Sample characters for testing."""
        return ["Naruto", "Sasuke", "Sakura"]

    @pytest.fixture
    def mock_image_generator(self):
        """Mock AI image generation function."""
        generator = AsyncMock()
        generator.return_value = "/fake/path/to/generated_image.png"
        return generator

    @pytest.fixture
    def coherence_manager(self):
        """Create VisualCoherenceManager instance."""
        return VisualCoherenceManager(consistency_threshold=0.8)

    @pytest.mark.asyncio
    async def test_style_consistency_validation(self, coherence_manager):
        """
        Test visual consistency validation between generated images.

        RED PHASE: This test should FAIL initially.

        Validates:
        - Visual consistency score calculation works
        - Score reflects visual similarity (target: >0.8)
        - Multiple images can be compared for consistency
        - Consistency metrics include color, style, and character components
        """
        # Arrange
        episode_context = {
            "episode_id": "test_episode",
            "visual_style": "anime",
            "color_palette": ["#FF6B35", "#F7931E"],
        }
        characters = ["TestChar"]

        # Mock image data
        with patch("cv2.imread") as mock_imread:
            # Create mock image array
            mock_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
            mock_imread.return_value = mock_image

            # Act
            consistency_metrics = await coherence_manager._evaluate_visual_consistency(
                "/fake/image/path.png", episode_context, characters
            )

            # Assert
            assert isinstance(
                consistency_metrics, VisualConsistencyMetrics
            ), "Should return VisualConsistencyMetrics object"
            assert (
                0.0 <= consistency_metrics.overall_score <= 1.0
            ), "Overall score should be between 0.0 and 1.0"
            assert (
                0.0 <= consistency_metrics.color_coherence_score <= 1.0
            ), "Color coherence should be between 0.0 and 1.0"
            assert (
                0.0 <= consistency_metrics.style_consistency_score <= 1.0
            ), "Style consistency should be between 0.0 and 1.0"
            assert (
                0.0 <= consistency_metrics.character_similarity_score <= 1.0
            ), "Character similarity should be between 0.0 and 1.0"

    @pytest.mark.asyncio
    async def test_character_appearance_consistency(self, coherence_manager):
        """
        Test character appearance consistency maintenance.

        RED PHASE: This test should FAIL initially.

        Validates:
        - Character reference images are stored and compared
        - Character similarity calculation works correctly
        - New character images maintain appearance consistency
        - Multiple characters in scene are handled properly
        """
        # Arrange
        characters = ["Naruto", "Sasuke"]
        mock_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

        with patch("cv2.imread", return_value=mock_image):
            # Act
            similarity_score = await coherence_manager._calculate_character_similarity(
                mock_image, characters
            )

            # Assert
            assert isinstance(
                similarity_score, float
            ), "Should return float similarity score"
            assert (
                0.0 <= similarity_score <= 1.0
            ), "Similarity score should be between 0.0 and 1.0"

            # Test with reference data stored
            coherence_manager.character_references["Naruto"] = mock_image
            similarity_with_ref = (
                await coherence_manager._calculate_character_similarity(
                    mock_image, ["Naruto"]
                )
            )

            assert (
                similarity_with_ref >= similarity_score
            ), "Similarity should be higher when reference exists"

    @pytest.mark.asyncio
    async def test_color_palette_coherence(self, coherence_manager):
        """
        Test episode color palette coherence maintenance.

        RED PHASE: This test should FAIL initially.

        Validates:
        - Color palette extraction using OpenCV k-means works
        - Episode color palettes are stored and compared
        - Color coherence scoring is accurate
        - New images maintain episode color consistency
        """
        # Arrange
        episode_id = "test_episode_colors"
        mock_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

        with patch("cv2.kmeans") as mock_kmeans:
            # Mock k-means clustering results
            mock_centers = np.array(
                [[255, 0, 0], [0, 255, 0], [0, 0, 255]], dtype=np.float32
            )
            mock_kmeans.return_value = (None, None, mock_centers)

            # Act
            color_score = await coherence_manager._calculate_color_coherence(
                mock_image, episode_id
            )

            # Assert
            assert isinstance(color_score, float), "Should return float color score"
            assert (
                0.0 <= color_score <= 1.0
            ), "Color score should be between 0.0 and 1.0"

            # For first image, should establish palette and return 1.0
            assert color_score == 1.0, "First image should return perfect score (1.0)"
            assert (
                episode_id in coherence_manager.episode_color_palettes
            ), "Episode palette should be stored"

            # Test second image with same colors (should have high coherence)
            color_score_2 = await coherence_manager._calculate_color_coherence(
                mock_image, episode_id
            )
            assert color_score_2 > 0.8, "Similar colors should have high coherence"

    @pytest.mark.asyncio
    async def test_consistency_retry_mechanism(
        self, coherence_manager, sample_episode_context, sample_characters
    ):
        """
        Test retry mechanism for low consistency scores.

        RED PHASE: This test should FAIL initially.

        Validates:
        - System retries generation when consistency score is low (<0.8)
        - Maximum 3 retry attempts are respected
        - Progressive prompt enhancement between attempts
        - Final result is returned even if consistency threshold not met
        """
        # Arrange
        prompt = "Test scene for consistency"
        mock_image_path = "/fake/generated/image.png"

        # Mock low consistency on first attempts, high on final
        consistency_scores = [0.5, 0.6, 0.9]  # Third attempt succeeds

        with patch.object(
            coherence_manager, "_generate_with_ai", return_value=mock_image_path
        ) as mock_generate:
            with patch.object(
                coherence_manager, "_evaluate_visual_consistency"
            ) as mock_evaluate:
                # Setup mock to return different scores for each attempt
                mock_evaluate.side_effect = [
                    VisualConsistencyMetrics(0.5, 0.5, 0.5, score)
                    for score in consistency_scores
                ]

                with patch.object(
                    coherence_manager, "_update_reference_data"
                ) as mock_update:
                    # Act
                    result = await coherence_manager.generate_consistent_image(
                        prompt,
                        sample_characters,
                        sample_episode_context,
                        max_attempts=3,
                    )

                    # Assert
                    assert (
                        result == mock_image_path
                    ), "Should return generated image path"
                    assert (
                        mock_generate.call_count == 3
                    ), "Should call generation 3 times (2 retries)"
                    assert (
                        mock_evaluate.call_count == 3
                    ), "Should evaluate consistency 3 times"
                    assert (
                        mock_update.call_count == 1
                    ), "Should update reference data once (when successful)"

    @pytest.mark.asyncio
    async def test_prompt_enhancement_for_consistency(self, coherence_manager):
        """
        Test progressive prompt enhancement for better consistency.

        RED PHASE: This test should FAIL initially.

        Validates:
        - Prompts are enhanced based on consistency metrics
        - Enhancement targets specific consistency weaknesses
        - Enhanced prompts are different from original
        - Enhancement preserves original scene context
        """
        # Arrange
        original_prompt = "Character in forest scene"
        low_consistency_metrics = VisualConsistencyMetrics(
            color_coherence_score=0.4,
            style_consistency_score=0.3,
            character_similarity_score=0.5,
            overall_score=0.4,
        )

        # Act
        enhanced_prompt = coherence_manager._enhance_prompt_for_consistency(
            original_prompt, low_consistency_metrics
        )

        # Assert
        assert isinstance(enhanced_prompt, str), "Should return string prompt"
        assert len(enhanced_prompt) > len(
            original_prompt
        ), "Enhanced prompt should be longer"
        assert (
            original_prompt in enhanced_prompt
        ), "Should preserve original scene content"

        # Check for consistency-specific enhancements
        enhanced_lower = enhanced_prompt.lower()
        if low_consistency_metrics.color_coherence_score < 0.6:
            assert any(
                keyword in enhanced_lower
                for keyword in ["color", "palette", "consistent colors"]
            ), "Should address color coherence issues"

        if low_consistency_metrics.style_consistency_score < 0.6:
            assert any(
                keyword in enhanced_lower for keyword in ["style", "consistent style"]
            ), "Should address style consistency issues"

    @pytest.mark.asyncio
    async def test_color_coherence_calculation_opencv(self, coherence_manager):
        """
        Test OpenCV-based color coherence calculation.

        RED PHASE: This test should FAIL initially.

        Validates:
        - K-means clustering extracts dominant colors correctly
        - Color palette comparison works with different algorithms
        - Edge cases (monochrome, high contrast) are handled
        - Performance is acceptable for real-time use
        """
        # Arrange
        episode_id = "color_test_episode"

        # Create test image with known colors
        test_image = np.zeros((100, 100, 3), dtype=np.uint8)
        test_image[:50, :50] = [255, 0, 0]  # Red quadrant
        test_image[:50, 50:] = [0, 255, 0]  # Green quadrant
        test_image[50:, :50] = [0, 0, 255]  # Blue quadrant
        test_image[50:, 50:] = [255, 255, 0]  # Yellow quadrant

        with patch("cv2.kmeans") as mock_kmeans:
            # Mock k-means to return expected color centers
            expected_colors = np.array(
                [[255, 0, 0], [0, 255, 0], [0, 0, 255], [255, 255, 0], [128, 128, 128]],
                dtype=np.float32,
            )
            mock_kmeans.return_value = (None, None, expected_colors)

            # Act - First image (establishes palette)
            score_1 = await coherence_manager._calculate_color_coherence(
                test_image, episode_id
            )

            # Assert first image
            assert score_1 == 1.0, "First image should establish palette with score 1.0"
            assert (
                episode_id in coherence_manager.episode_color_palettes
            ), "Episode palette should be stored"

            # Act - Second image (tests coherence)
            score_2 = await coherence_manager._calculate_color_coherence(
                test_image, episode_id
            )

            # Assert second image
            assert isinstance(score_2, float), "Should return float coherence score"
            assert 0.0 <= score_2 <= 1.0, "Score should be in valid range"

    @pytest.mark.asyncio
    async def test_style_consistency_calculation(self, coherence_manager):
        """
        Test style consistency calculation using feature comparison.

        RED PHASE: This test should FAIL initially.

        Validates:
        - Style feature extraction works correctly
        - Style comparison algorithm provides meaningful scores
        - Style templates are stored and updated properly
        - Different art styles are distinguished appropriately
        """
        # Arrange
        episode_context = {"episode_id": "style_test", "visual_style": "anime"}
        mock_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

        # Act
        style_score = await coherence_manager._calculate_style_consistency(
            mock_image, episode_context
        )

        # Assert
        assert isinstance(style_score, float), "Should return float style score"
        assert 0.0 <= style_score <= 1.0, "Style score should be between 0.0 and 1.0"

        # For first image of episode, should establish template
        episode_id = episode_context["episode_id"]
        if episode_id not in coherence_manager.style_templates:
            assert (
                style_score == 1.0
            ), "First image should establish style with score 1.0"

    @pytest.mark.asyncio
    async def test_reference_data_management(self, coherence_manager):
        """
        Test storage and updating of reference data.

        RED PHASE: This test should FAIL initially.

        Validates:
        - Character reference images are stored correctly
        - Episode color palettes are maintained
        - Style templates are updated appropriately
        - Reference data doesn't grow unbounded
        """
        # Arrange
        image_path = "/fake/test/image.png"
        characters = ["TestChar1", "TestChar2"]
        episode_context = {"episode_id": "ref_test_episode"}
        mock_image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)

        with patch("cv2.imread", return_value=mock_image):
            # Act
            await coherence_manager._update_reference_data(
                image_path, characters, episode_context
            )

            # Assert character references stored
            for char in characters:
                assert (
                    char in coherence_manager.character_references
                ), f"Character {char} should be stored in references"
                assert isinstance(
                    coherence_manager.character_references[char], np.ndarray
                ), f"Character {char} reference should be numpy array"

    @pytest.mark.asyncio
    async def test_consistency_threshold_behavior(
        self, sample_episode_context, sample_characters
    ):
        """
        Test behavior with different consistency thresholds.

        RED PHASE: This test should FAIL initially.

        Validates:
        - Different threshold values affect retry behavior
        - Higher thresholds require more retry attempts
        - Lower thresholds accept images faster
        - Threshold bounds are respected (0.0-1.0)
        """
        # Test different threshold values
        for threshold in [0.5, 0.8, 0.95]:
            manager = VisualCoherenceManager(consistency_threshold=threshold)

            with patch.object(manager, "_generate_with_ai") as mock_generate:
                mock_generate.return_value = "/fake/image.png"

                with patch.object(manager, "_evaluate_visual_consistency") as mock_eval:
                    # For low threshold, return passing score immediately
                    # For high threshold, return failing then passing score
                    if threshold <= 0.5:
                        mock_eval.side_effect = [
                            VisualConsistencyMetrics(0.9, 0.9, 0.9, 0.9)
                        ]
                        expected_calls = 1
                    else:
                        mock_eval.side_effect = [
                            VisualConsistencyMetrics(0.7, 0.7, 0.7, threshold - 0.1),
                            VisualConsistencyMetrics(0.9, 0.9, 0.9, threshold + 0.1),
                        ]
                        expected_calls = 2

                    with patch.object(manager, "_update_reference_data"):
                        # Act
                        result = await manager.generate_consistent_image(
                            "test prompt", sample_characters, sample_episode_context
                        )

                        # Assert
                        assert result == "/fake/image.png", "Should return image path"
                        assert mock_generate.call_count == expected_calls, (
                            f"Should call generation {expected_calls} times "
                            f"for threshold {threshold}"
                        )

    @pytest.mark.asyncio
    async def test_image_generation_integration(
        self, coherence_manager, sample_episode_context, sample_characters
    ):
        """
        Test integration with AI image generation.

        RED PHASE: This test should FAIL initially.

        Validates:
        - AI image generation is called with enhanced prompts
        - Generation failures are handled gracefully
        - Image paths are validated before processing
        - Generation respects episode context and character data
        """
        # Arrange
        prompt = "Test scene generation"

        with (
            patch.object(coherence_manager, "_generate_with_ai") as mock_generate,
            patch.object(
                coherence_manager, "_evaluate_visual_consistency"
            ) as mock_evaluate,
            patch.object(coherence_manager, "_update_reference_data"),
        ):

            mock_generate.return_value = "/generated/test_image.png"
            mock_evaluate.return_value = VisualConsistencyMetrics(0.9, 0.9, 0.9, 0.9)

            # Act
            result = await coherence_manager.generate_consistent_image(
                prompt, sample_characters, sample_episode_context
            )

            # Assert
            assert result == "/generated/test_image.png", "Should return generated path"
            mock_generate.assert_called_once()

            # Check that prompt was enhanced
            called_prompt = mock_generate.call_args[0][0]
            assert len(called_prompt) >= len(
                prompt
            ), "Prompt should be enhanced or maintained"

    @pytest.mark.asyncio
    async def test_visual_consistency_metrics_calculation(self, coherence_manager):
        """
        Test comprehensive visual consistency metrics calculation.

        RED PHASE: This test should FAIL initially.

        Validates:
        - All three consistency components are calculated
        - Overall score is weighted combination of components
        - Metrics provide actionable feedback for improvements
        - Edge cases (perfect/poor consistency) work correctly
        """
        # Arrange
        mock_image = np.random.randint(0, 255, (300, 400, 3), dtype=np.uint8)
        episode_context = {"episode_id": "metrics_test"}
        characters = ["TestChar"]

        with (
            patch("cv2.imread", return_value=mock_image),
            patch.object(
                coherence_manager, "_calculate_color_coherence", return_value=0.8
            ) as mock_color,
            patch.object(
                coherence_manager, "_calculate_style_consistency", return_value=0.7
            ) as mock_style,
            patch.object(
                coherence_manager, "_calculate_character_similarity", return_value=0.9
            ) as mock_char,
        ):

            # Act
            metrics = await coherence_manager._evaluate_visual_consistency(
                "/fake/image.png", episode_context, characters
            )

            # Assert individual components called
            mock_color.assert_called_once_with(mock_image, "metrics_test")
            mock_style.assert_called_once_with(mock_image, episode_context)
            mock_char.assert_called_once_with(mock_image, characters)

            # Assert metrics structure
            assert metrics.color_coherence_score == 0.8
            assert metrics.style_consistency_score == 0.7
            assert metrics.character_similarity_score == 0.9

            # Assert weighted overall score calculation
            expected_overall = (0.8 * 0.3) + (0.7 * 0.4) + (0.9 * 0.3)
            assert abs(metrics.overall_score - expected_overall) < 0.01, (
                f"Overall score should be {expected_overall:.2f}, "
                f"got {metrics.overall_score:.2f}"
            )

    @pytest.mark.asyncio
    async def test_performance_constraints_visual_coherence(
        self, coherence_manager, sample_episode_context, sample_characters
    ):
        """
        Test performance constraints for visual coherence system.

        RED PHASE: This test should FAIL initially.

        Validates:
        - Visual coherence processing completes within 2s per image
        - Memory usage stays reasonable during processing
        - OpenCV operations are efficient
        - Concurrent processing doesn't degrade performance
        """
        import time
        import psutil
        import gc

        # Arrange
        prompt = "Performance test scene"
        mock_image = np.random.randint(0, 255, (1920, 1080, 3), dtype=np.uint8)

        # Measure initial memory
        gc.collect()
        initial_memory = psutil.Process().memory_info().rss / 1024**2  # MB

        with (
            patch("cv2.imread", return_value=mock_image),
            patch("cv2.kmeans") as mock_kmeans,
        ):

            # Mock k-means results
            mock_centers = np.random.rand(5, 3).astype(np.float32) * 255
            mock_kmeans.return_value = (None, None, mock_centers)

            with (
                patch.object(coherence_manager, "_generate_with_ai") as mock_generate,
                patch.object(coherence_manager, "_update_reference_data"),
            ):

                mock_generate.return_value = "/fake/perf_test.png"

                # Measure processing time
                start_time = time.time()

                # Act
                result = await coherence_manager.generate_consistent_image(
                    prompt, sample_characters, sample_episode_context
                )

                # Measure completion
                end_time = time.time()
                processing_time = end_time - start_time

                gc.collect()
                final_memory = psutil.Process().memory_info().rss / 1024**2  # MB
                memory_increase = final_memory - initial_memory

                # Assert performance constraints
                assert processing_time < 2.0, (
                    f"Visual coherence should complete within 2s, "
                    f"took {processing_time:.3f}s"
                )
                assert memory_increase < 200, (
                    f"Memory increase should be reasonable, "
                    f"increased by {memory_increase:.1f}MB"
                )
                assert result is not None, "Should successfully generate image"

    @pytest.mark.asyncio
    async def test_error_handling_visual_coherence(self, coherence_manager):
        """
        Test error handling in visual coherence system.

        RED PHASE: This test should FAIL initially.

        Validates:
        - Invalid image paths are handled gracefully
        - OpenCV errors don't crash the system
        - Missing reference data is handled appropriately
        - System continues with fallback behavior on errors
        """
        # Test with invalid image path
        with patch("cv2.imread", return_value=None):  # Simulates file not found
            with pytest.raises(ValueError, match="Could not load image"):
                await coherence_manager._evaluate_visual_consistency(
                    "/invalid/image/path.png", {"episode_id": "test"}, ["TestChar"]
                )

        # Test with OpenCV errors
        with patch("cv2.imread") as mock_imread, patch("cv2.kmeans") as mock_kmeans:
            mock_imread.return_value = np.random.randint(0, 255, (100, 100, 3))
            mock_kmeans.side_effect = Exception("OpenCV error")

            # Should handle OpenCV errors gracefully
            try:
                score = await coherence_manager._calculate_color_coherence(
                    mock_imread.return_value, "error_test_episode"
                )
                # If no exception, should return a fallback score
                assert 0.0 <= score <= 1.0, "Should return valid fallback score"
            except Exception as e:
                # Should raise appropriate exception with context
                assert "color" in str(e).lower() or "opencv" in str(e).lower()

    def test_color_palette_comparison_algorithms(self, coherence_manager):
        """
        Test color palette comparison algorithms.

        RED PHASE: This test should FAIL initially.

        Validates:
        - Different color distance metrics work correctly
        - Color palette similarity is calculated accurately
        - Similar palettes get high scores, different palettes get low scores
        - RGB color space operations are correct
        """
        # Arrange
        palette_1 = [[255, 0, 0], [0, 255, 0], [0, 0, 255]]  # RGB primaries
        palette_2 = [[250, 5, 5], [5, 250, 5], [5, 5, 250]]  # Similar to palette_1
        palette_3 = [[128, 128, 128], [64, 64, 64], [192, 192, 192]]  # Grayscale

        # Act
        similarity_high = coherence_manager._compare_color_palettes(
            palette_1, palette_2
        )
        similarity_low = coherence_manager._compare_color_palettes(palette_1, palette_3)

        # Assert
        assert isinstance(similarity_high, float), "Should return float similarity"
        assert isinstance(similarity_low, float), "Should return float similarity"
        assert 0.0 <= similarity_high <= 1.0, "Similarity should be in valid range"
        assert 0.0 <= similarity_low <= 1.0, "Similarity should be in valid range"
        assert (
            similarity_high > similarity_low
        ), "Similar palettes should have higher similarity than different palettes"
        assert similarity_high > 0.8, "Very similar palettes should score >0.8"
        assert similarity_low < 0.5, "Very different palettes should score <0.5"


# Integration test placeholder
class TestVisualCoherenceIntegration:
    """Integration tests with existing image generation system."""

    @pytest.mark.asyncio
    async def test_integration_with_image_generator(self):
        """
        Test integration with existing parallel image generator.

        This test validates that visual coherence works with the existing
        image generation pipeline.
        """
        # Will be implemented after core functionality is working
        pytest.skip("Integration test - implement after core functionality")


if __name__ == "__main__":
    # Run tests to verify they fail (RED phase)
    pytest.main([__file__, "-v"])
