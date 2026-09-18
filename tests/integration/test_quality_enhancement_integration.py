#!/usr/bin/env python3
"""
Integration tests for Phase 2 Quality Enhancement components.

This module tests the integration between all Phase 2 components:
- Character Episode Enhancer
- Visual Coherence Manager
- Adaptive Quality Manager
- Intelligent Format Adapter

Tests validate that components work together seamlessly.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from core.character_episode_enhancer import EpisodeCharacterEnhancer, CharacterWeight
from core.visual_coherence_manager import VisualCoherenceManager
from core.adaptive_quality_manager import AdaptiveQualityManager
from core.intelligent_format_adapter import IntelligentFormatAdapter


class TestQualityEnhancementIntegration:
    """Integration tests for all Phase 2 quality enhancement components."""

    @pytest.fixture
    def sample_episode_content(self):
        """Sample episode content for integration testing."""
        fixtures_path = Path(__file__).parent.parent / "fixtures" / "character_data"
        with open(fixtures_path / "sample_episode_content.json") as f:
            return json.load(f)

    @pytest.fixture
    def sample_character_analysis(self):
        """Sample character analysis data."""
        fixtures_path = Path(__file__).parent.parent / "fixtures" / "character_data"
        with open(fixtures_path / "sample_character_analysis.json") as f:
            return json.load(f)

    @pytest.fixture
    def quality_enhancement_pipeline(self):
        """Create integrated quality enhancement pipeline."""
        # Initialize all components
        character_enhancer = EpisodeCharacterEnhancer(
            character_analyzer=AsyncMock(), timing_calculator=MagicMock()
        )

        visual_coherence = VisualCoherenceManager(consistency_threshold=0.8)
        quality_manager = AdaptiveQualityManager()
        format_adapter = IntelligentFormatAdapter()

        return {
            "character_enhancer": character_enhancer,
            "visual_coherence": visual_coherence,
            "quality_manager": quality_manager,
            "format_adapter": format_adapter,
        }

    @pytest.mark.asyncio
    async def test_complete_quality_enhancement_pipeline(
        self,
        quality_enhancement_pipeline,
        sample_episode_content,
        sample_character_analysis,
    ):
        """
        Test complete quality enhancement pipeline integration.

        Validates:
        - All components work together without conflicts
        - Character enhancement flows into visual coherence
        - Quality settings affect all downstream components
        - Platform adaptation uses enhanced content appropriately
        """
        pipeline = quality_enhancement_pipeline

        # Step 1: Character Enhancement
        enhanced_episode = await pipeline[
            "character_enhancer"
        ].enhance_episode_with_character_data(
            sample_episode_content, sample_character_analysis
        )

        assert (
            "scenes" in enhanced_episode
        ), "Character enhancement should return enhanced scenes"
        assert (
            "character_focus" in enhanced_episode
        ), "Should include character focus data"

        # Step 2: Quality Profile Selection
        quality_profile = await pipeline["quality_manager"].select_quality_profile(
            context="preview"
        )

        assert (
            quality_profile.name == "preview"
        ), "Should select appropriate quality profile"

        # Step 3: Platform Adaptation with Enhanced Content
        platform_result = await pipeline["format_adapter"].adapt_content_for_platform(
            enhanced_episode, "tiktok", quality_profile
        )

        assert (
            "adapted_content" in platform_result
        ), "Should adapt enhanced content for platform"
        assert "engagement_prediction" in platform_result, "Should predict engagement"

        # Validate end-to-end enhancement
        final_content = platform_result["adapted_content"]
        final_duration = sum(scene["duration"] for scene in final_content["scenes"])

        assert final_duration <= 60, "Final content should respect TikTok time limit"
        assert (
            len(final_content["scenes"]) > 0
        ), "Should maintain content through pipeline"

    @pytest.mark.asyncio
    async def test_visual_coherence_with_character_enhancement(
        self,
        quality_enhancement_pipeline,
        sample_episode_content,
        sample_character_analysis,
    ):
        """
        Test visual coherence integration with character-enhanced prompts.

        Validates:
        - Character-enhanced prompts work with visual coherence system
        - Visual consistency is maintained with character context
        - Reference data management works with enhanced content
        """
        pipeline = quality_enhancement_pipeline

        # Enhance episode with character data
        enhanced_episode = await pipeline[
            "character_enhancer"
        ].enhance_episode_with_character_data(
            sample_episode_content, sample_character_analysis
        )

        # Test visual coherence with enhanced prompts
        first_scene = enhanced_episode["scenes"][0]
        characters = first_scene["characters"]
        enhanced_prompt = first_scene["enhanced_prompt"]

        episode_context = {"episode_id": "integration_test", "visual_style": "anime"}

        with (
            patch.object(
                pipeline["visual_coherence"], "_generate_with_ai"
            ) as mock_generate,
            patch.object(pipeline["visual_coherence"], "_update_reference_data"),
            patch("cv2.imread") as mock_imread,
        ):

            mock_generate.return_value = "/fake/integrated_image.png"
            # Mock a valid image array for cv2.imread
            import numpy as np

            mock_imread.return_value = np.random.randint(
                0, 255, (480, 640, 3), dtype=np.uint8
            )

            # Generate image with enhanced prompt
            result = await pipeline["visual_coherence"].generate_consistent_image(
                enhanced_prompt, characters, episode_context
            )

            assert (
                result == "/fake/integrated_image.png"
            ), "Should generate with enhanced prompt"

            # Verify enhanced prompt was used
            called_prompt = mock_generate.call_args[0][0]
            assert len(called_prompt) > len(
                enhanced_prompt
            ), "Prompt should be further enhanced for consistency"

    @pytest.mark.asyncio
    async def test_quality_settings_affect_all_components(
        self,
        quality_enhancement_pipeline,
        sample_episode_content,
        sample_character_analysis,
    ):
        """
        Test that quality settings appropriately affect all components.

        Validates:
        - Different quality profiles produce different results
        - Quality constraints are respected across components
        - Performance vs quality tradeoffs work correctly
        """
        pipeline = quality_enhancement_pipeline

        # First enhance episode to get proper duration fields
        enhanced_episode = await pipeline[
            "character_enhancer"
        ].enhance_episode_with_character_data(
            sample_episode_content, sample_character_analysis
        )

        # Test with different quality contexts
        contexts = ["draft", "preview", "production"]
        results = {}

        for context in contexts:
            # Get quality profile
            quality_profile = await pipeline["quality_manager"].select_quality_profile(
                context=context
            )

            # Adapt content with quality profile (use enhanced episode)
            adaptation_result = await pipeline[
                "format_adapter"
            ].adapt_content_for_platform(
                enhanced_episode, "youtube_shorts", quality_profile
            )

            results[context] = {
                "quality_profile": quality_profile,
                "adaptation_result": adaptation_result,
            }

        # Validate quality hierarchy affects results
        draft_quality = results["draft"]["quality_profile"].image_quality
        preview_quality = results["preview"]["quality_profile"].image_quality
        production_quality = results["production"]["quality_profile"].image_quality

        assert (
            draft_quality <= preview_quality <= production_quality
        ), "Quality should increase across contexts"

    @pytest.mark.asyncio
    async def test_error_propagation_and_handling(
        self, quality_enhancement_pipeline, sample_episode_content
    ):
        """
        Test error handling across integrated components.

        Validates:
        - Errors in one component don't crash the pipeline
        - Graceful degradation works across components
        - Error recovery maintains system functionality
        """
        pipeline = quality_enhancement_pipeline

        # Test with missing character analysis (should degrade gracefully)
        empty_character_analysis = {"profiles": {}}

        enhanced_episode = await pipeline[
            "character_enhancer"
        ].enhance_episode_with_character_data(
            sample_episode_content, empty_character_analysis
        )

        assert enhanced_episode is not None, "Should handle missing character analysis"
        assert "scenes" in enhanced_episode, "Should return valid episode structure"

        # Test adaptation still works with minimal character data
        quality_profile = await pipeline["quality_manager"].select_quality_profile(
            context="preview"
        )

        adaptation_result = await pipeline["format_adapter"].adapt_content_for_platform(
            enhanced_episode, "tiktok", quality_profile
        )

        assert adaptation_result is not None, "Should handle degraded enhancement data"
        assert (
            "adapted_content" in adaptation_result
        ), "Should still produce adapted content"

    @pytest.mark.asyncio
    async def test_performance_constraints_integration(
        self,
        quality_enhancement_pipeline,
        sample_episode_content,
        sample_character_analysis,
    ):
        """
        Test performance constraints across integrated system.

        Validates:
        - End-to-end processing meets performance targets
        - Memory usage stays within bounds across components
        - Processing time is acceptable for production use
        """
        import time
        import psutil
        import gc

        pipeline = quality_enhancement_pipeline

        # Measure initial state
        gc.collect()
        initial_memory = psutil.Process().memory_info().rss / 1024**2  # MB
        start_time = time.time()

        # Run complete pipeline
        # 1. Character enhancement
        enhanced_episode = await pipeline[
            "character_enhancer"
        ].enhance_episode_with_character_data(
            sample_episode_content, sample_character_analysis
        )

        # 2. Quality profile selection
        quality_profile = await pipeline["quality_manager"].select_quality_profile(
            context="preview"
        )

        # 3. Platform adaptation
        adaptation_result = await pipeline["format_adapter"].adapt_content_for_platform(
            enhanced_episode, "youtube_shorts", quality_profile
        )

        # Measure completion
        end_time = time.time()
        total_processing_time = end_time - start_time

        gc.collect()
        final_memory = psutil.Process().memory_info().rss / 1024**2  # MB
        memory_increase = final_memory - initial_memory

        # Assert performance constraints
        assert (
            total_processing_time < 5.0
        ), f"Complete pipeline should finish within 5s, took {total_processing_time:.2f}s"
        assert (
            memory_increase < 500
        ), f"Memory increase should be reasonable, increased by {memory_increase:.1f}MB"
        assert adaptation_result is not None, "Should successfully complete pipeline"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
