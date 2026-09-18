#!/usr/bin/env python3
"""
Unit tests for Intelligent Platform Format Adaptation System.

This module tests the platform adaptation system that optimizes content
for different social media platforms with AI-powered content analysis,
engagement prediction, and multi-platform batch export.

Following TDD methodology - these tests should FAIL initially (RED phase).
"""

import pytest
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, List, Any

# Import the module we're testing - will fail initially
try:
    from core.intelligent_format_adapter import (
        IntelligentFormatAdapter,
        PlatformConfig,
        EngagementPrediction,
    )
    from core.adaptive_quality_manager import QualityProfile
except ImportError:
    # Expected to fail in RED phase
    pass


class TestIntelligentFormatAdapter:
    """Test suite for enhanced platform format adaptation."""

    @pytest.fixture
    def sample_content(self) -> Dict[str, Any]:
        """Sample episode content for testing (>60s to test condensation)."""
        return {
            "scenes": [
                {
                    "prompt": "Naruto training with Rasengan",
                    "duration": 18.0,
                    "characters": ["Naruto"],
                    "emotional_intensity": 0.8,
                },
                {
                    "prompt": "Sasuke and Naruto final battle",
                    "duration": 25.0,
                    "characters": ["Naruto", "Sasuke"],
                    "emotional_intensity": 1.0,
                },
                {
                    "prompt": "Sakura's medical training",
                    "duration": 12.0,
                    "characters": ["Sakura"],
                    "emotional_intensity": 0.6,
                },
                {
                    "prompt": "Team 7 reunion",
                    "duration": 15.0,
                    "characters": ["Naruto", "Sasuke", "Sakura"],
                    "emotional_intensity": 0.9,
                },
            ]
        }

    @pytest.fixture
    def sample_quality_profile(self) -> "QualityProfile":
        """Sample quality profile for testing."""
        return QualityProfile(
            name="test_profile",
            image_quality=0.8,
            video_resolution=(1920, 1080),
            compression_level=85,
            processing_priority="balanced",
            max_concurrent_jobs=4,
            memory_limit_mb=2048,
        )

    @pytest.fixture
    def format_adapter(self):
        """Create IntelligentFormatAdapter instance."""
        return IntelligentFormatAdapter()

    @pytest.mark.asyncio
    async def test_tiktok_content_optimization(
        self, format_adapter, sample_content, sample_quality_profile
    ):
        """
        Test content optimization specifically for TikTok algorithm.

        RED PHASE: This test should FAIL initially.

        Validates:
        - Content longer than 60s is condensed appropriately
        - TikTok-specific optimization (viral hooks, fast pacing)
        - Content maintains narrative coherence after condensation
        - Engagement prediction provides meaningful scores
        """
        # Arrange
        platform = "tiktok"
        total_duration = sum(scene["duration"] for scene in sample_content["scenes"])
        assert (
            total_duration > 60
        ), "Sample content should exceed TikTok limit for testing"

        # Act
        adaptation_result = await format_adapter.adapt_content_for_platform(
            sample_content, platform, sample_quality_profile
        )

        # Assert structure
        assert "adapted_content" in adaptation_result, "Should contain adapted content"
        assert (
            "platform_optimized_hook" in adaptation_result
        ), "Should contain optimized hook"
        assert (
            "engagement_prediction" in adaptation_result
        ), "Should contain engagement prediction"
        assert (
            "adaptation_metadata" in adaptation_result
        ), "Should contain adaptation metadata"

        # Assert TikTok-specific adaptations
        adapted_content = adaptation_result["adapted_content"]
        adapted_duration = sum(scene["duration"] for scene in adapted_content["scenes"])

        assert adapted_duration <= 60, "Adapted content should fit TikTok time limit"
        assert adapted_duration >= 15, "Should maintain minimum meaningful duration"

        # Assert engagement prediction
        engagement = adaptation_result["engagement_prediction"]
        assert isinstance(
            engagement, EngagementPrediction
        ), "Should return EngagementPrediction"
        assert 0.0 <= engagement.retention_rate <= 1.0, "Retention rate should be valid"
        assert 0.0 <= engagement.confidence_score <= 1.0, "Confidence should be valid"

        # Assert metadata
        metadata = adaptation_result["adaptation_metadata"]
        assert (
            metadata["original_duration"] == total_duration
        ), "Should track original duration"
        assert (
            metadata["adapted_duration"] == adapted_duration
        ), "Should track adapted duration"
        assert (
            metadata["compression_ratio"] > 1.0
        ), "Should indicate compression occurred"

    @pytest.mark.asyncio
    async def test_youtube_shorts_adaptation(
        self, format_adapter, sample_content, sample_quality_profile
    ):
        """
        Test content adaptation for YouTube Shorts format.

        RED PHASE: This test should FAIL initially.

        Validates:
        - YouTube Shorts optimization (informative hooks, watch time focus)
        - Content fits 60s limit while maximizing information density
        - Hook generation is platform-appropriate
        - Engagement focuses on watch time rather than viral metrics
        """
        # Arrange
        platform = "youtube_shorts"

        # Act
        adaptation_result = await format_adapter.adapt_content_for_platform(
            sample_content, platform, sample_quality_profile
        )

        # Assert platform-specific adaptations
        adapted_content = adaptation_result["adapted_content"]
        adapted_duration = sum(scene["duration"] for scene in adapted_content["scenes"])

        assert adapted_duration <= 60, "Should fit YouTube Shorts time limit"

        # Assert YouTube-specific hook
        hook = adaptation_result["platform_optimized_hook"]
        assert isinstance(hook, str), "Should return string hook"
        assert len(hook) > 10, "Hook should be substantial"

        # Hook should be informative (YouTube Shorts style)
        hook_lower = hook.lower()
        informative_keywords = [
            "learn",
            "discover",
            "understand",
            "explained",
            "how",
            "why",
            "strategy",
            "breakdown",
        ]
        assert any(
            keyword in hook_lower for keyword in informative_keywords
        ), "YouTube Shorts hook should be informative"

        # Assert engagement prediction focuses on watch time
        engagement = adaptation_result["engagement_prediction"]
        assert engagement.completion_rate >= 0.0, "Should predict completion rate"

    @pytest.mark.asyncio
    async def test_instagram_reels_adaptation(
        self, format_adapter, sample_content, sample_quality_profile
    ):
        """
        Test content adaptation for Instagram Reels format.

        RED PHASE: This test should FAIL initially.

        Validates:
        - Instagram Reels optimization (aesthetic focus, share-ability)
        - 90s time limit respected
        - Visual aesthetics prioritized over information density
        - Engagement prediction emphasizes shares and visual appeal
        """
        # Arrange
        platform = "instagram_reels"

        # Act
        adaptation_result = await format_adapter.adapt_content_for_platform(
            sample_content, platform, sample_quality_profile
        )

        # Assert platform-specific adaptations
        adapted_content = adaptation_result["adapted_content"]
        adapted_duration = sum(scene["duration"] for scene in adapted_content["scenes"])

        assert adapted_duration <= 90, "Should fit Instagram Reels time limit"

        # Assert Instagram-specific hook (aesthetic focus)
        hook = adaptation_result["platform_optimized_hook"]
        aesthetic_keywords = [
            "beautiful",
            "stunning",
            "amazing",
            "incredible",
            "visual",
            "breathtaking",
        ]
        hook_lower = hook.lower()
        assert any(
            keyword in hook_lower for keyword in aesthetic_keywords
        ), "Instagram Reels hook should focus on aesthetics"

        # Assert engagement prediction emphasizes shares
        engagement = adaptation_result["engagement_prediction"]
        assert engagement.share_probability >= 0.0, "Should predict share probability"

    @pytest.mark.asyncio
    async def test_ai_content_condensation_major(self, format_adapter, sample_content):
        """
        Test AI-powered content condensation for major duration reduction.

        RED PHASE: This test should FAIL initially.

        Validates:
        - AI selects key scenes when major condensation needed (>80% reduction)
        - Scene selection preserves narrative arc
        - Most important/emotional scenes are retained
        - Condensation maintains story coherence
        """
        # Arrange
        target_duration = 15  # Requires major condensation from ~35s to 15s
        pacing = "fast"

        # Act
        condensed_content = await format_adapter._ai_condense_content(
            sample_content, target_duration, pacing
        )

        # Assert
        condensed_duration = sum(
            scene["duration"] for scene in condensed_content["scenes"]
        )
        assert (
            condensed_duration <= target_duration + 2
        ), f"Condensed duration {condensed_duration}s should be close to target {target_duration}s"
        assert len(condensed_content["scenes"]) < len(
            sample_content["scenes"]
        ), "Should remove some scenes for major condensation"

        # Assert key scenes preserved (highest emotional intensity)
        original_intensities = [
            scene["emotional_intensity"] for scene in sample_content["scenes"]
        ]
        condensed_intensities = [
            scene["emotional_intensity"] for scene in condensed_content["scenes"]
        ]

        max_original_intensity = max(original_intensities)
        assert (
            max_original_intensity in condensed_intensities
        ), "Should preserve scenes with highest emotional intensity"

    @pytest.mark.asyncio
    async def test_ai_content_condensation_minor(self, format_adapter, sample_content):
        """
        Test proportional trimming for minor content condensation.

        RED PHASE: This test should FAIL initially.

        Validates:
        - Minor condensation uses proportional trimming
        - All scenes are preserved with reduced duration
        - Narrative structure is maintained
        - Proportional reduction is applied correctly
        """
        # Arrange - Minor condensation (reduce by ~20%)
        original_duration = sum(scene["duration"] for scene in sample_content["scenes"])
        target_duration = original_duration * 0.8  # 80% of original
        pacing = "medium"

        # Act
        condensed_content = await format_adapter._ai_condense_content(
            sample_content, target_duration, pacing
        )

        # Assert
        condensed_duration = sum(
            scene["duration"] for scene in condensed_content["scenes"]
        )
        compression_ratio = original_duration / condensed_duration

        assert (
            1.2 <= compression_ratio <= 1.3
        ), f"Should achieve ~20% compression, got {compression_ratio:.2f}x"
        assert len(condensed_content["scenes"]) == len(
            sample_content["scenes"]
        ), "Minor condensation should preserve all scenes"

        # Assert proportional reduction
        for original, condensed in zip(
            sample_content["scenes"], condensed_content["scenes"]
        ):
            reduction_ratio = condensed["duration"] / original["duration"]
            assert 0.7 <= reduction_ratio <= 0.9, (
                f"Scene duration should be proportionally reduced, "
                f"got {reduction_ratio:.2f} for scene"
            )

    @pytest.mark.asyncio
    async def test_engagement_prediction_accuracy(self, format_adapter, sample_content):
        """
        Test engagement prediction with reasonable accuracy.

        RED PHASE: This test should FAIL initially.

        Validates:
        - Engagement predictions include all required metrics
        - Predictions are based on content analysis
        - Confidence scores reflect prediction reliability
        - Platform-specific engagement factors are considered
        """
        # Test engagement prediction for different platforms
        platforms = ["tiktok", "youtube_shorts", "instagram_reels"]

        for platform in platforms:
            # Act
            engagement = await format_adapter._predict_engagement(
                sample_content, platform
            )

            # Assert structure
            assert isinstance(
                engagement, EngagementPrediction
            ), f"Should return EngagementPrediction for {platform}"

            # Assert valid ranges
            assert (
                0.0 <= engagement.retention_rate <= 1.0
            ), f"Retention rate should be valid for {platform}"
            assert (
                0.0 <= engagement.completion_rate <= 1.0
            ), f"Completion rate should be valid for {platform}"
            assert (
                0.0 <= engagement.share_probability <= 1.0
            ), f"Share probability should be valid for {platform}"
            assert (
                0.0 <= engagement.confidence_score <= 1.0
            ), f"Confidence score should be valid for {platform}"

            # Platform-specific assertions
            if platform == "tiktok":
                # TikTok prioritizes retention and viral content
                assert (
                    engagement.retention_rate > 0.0
                ), "TikTok should predict retention"
            elif platform == "youtube_shorts":
                # YouTube focuses on completion rate
                assert (
                    engagement.completion_rate > 0.0
                ), "YouTube should predict completion"
            elif platform == "instagram_reels":
                # Instagram focuses on shares and aesthetics
                assert (
                    engagement.share_probability > 0.0
                ), "Instagram should predict shares"

    @pytest.mark.asyncio
    async def test_multi_platform_batch_export(
        self, format_adapter, sample_content, sample_quality_profile
    ):
        """
        Test efficient multi-platform batch export functionality.

        RED PHASE: This test should FAIL initially.

        Validates:
        - Multiple platforms can be processed simultaneously
        - Each platform receives optimized content
        - Batch processing is more efficient than individual processing
        - Platform-specific optimizations are applied correctly
        """
        # Arrange
        target_platforms = ["tiktok", "youtube_shorts", "instagram_reels"]

        # Act
        batch_results = await format_adapter.batch_adapt_for_platforms(
            sample_content, target_platforms, sample_quality_profile
        )

        # Assert batch structure
        assert isinstance(batch_results, dict), "Should return results dictionary"
        assert len(batch_results) == len(
            target_platforms
        ), "Should return results for all platforms"

        # Assert each platform adaptation
        for platform in target_platforms:
            assert platform in batch_results, f"Should contain results for {platform}"

            platform_result = batch_results[platform]
            assert (
                "adapted_content" in platform_result
            ), f"Should contain adapted content for {platform}"
            assert (
                "engagement_prediction" in platform_result
            ), f"Should contain engagement prediction for {platform}"

            # Check platform-specific constraints
            adapted_duration = sum(
                scene["duration"]
                for scene in platform_result["adapted_content"]["scenes"]
            )

            config = format_adapter.platform_configs[platform]
            assert (
                adapted_duration <= config.max_duration
            ), f"{platform} content should respect duration limit {config.max_duration}s"

    @pytest.mark.asyncio
    async def test_platform_hook_generation(self, format_adapter):
        """
        Test platform-specific hook generation.

        RED PHASE: This test should FAIL initially.

        Validates:
        - Different hook styles for different platforms
        - Hooks are engaging and platform-appropriate
        - Hook generation considers scene content and platform algorithm
        - Generated hooks are substantial and meaningful
        """
        # Arrange
        test_scene = {
            "prompt": "Epic battle between heroes and villains",
            "characters": ["Naruto", "Sasuke"],
            "emotional_intensity": 0.9,
        }

        # Test different hook styles
        hook_styles = ["viral", "informative", "aesthetic"]

        for style in hook_styles:
            # Act
            hook = await format_adapter._generate_platform_hook(test_scene, style)

            # Assert
            assert isinstance(hook, str), f"Should return string hook for {style}"
            assert len(hook) >= 20, f"Hook should be substantial for {style}"
            assert (
                "battle" in hook.lower()
                or "epic" in hook.lower()
                or any(
                    char.lower() in hook.lower() for char in test_scene["characters"]
                )
            ), f"Hook should relate to scene content for {style}"

            # Style-specific assertions
            if style == "viral":
                viral_keywords = [
                    "amazing",
                    "incredible",
                    "unbelievable",
                    "epic",
                    "insane",
                ]
                assert any(
                    keyword in hook.lower() for keyword in viral_keywords
                ), "Viral hook should use engaging language"
            elif style == "informative":
                info_keywords = [
                    "learn",
                    "discover",
                    "explained",
                    "analysis",
                    "breakdown",
                ]
                assert any(
                    keyword in hook.lower() for keyword in info_keywords
                ), "Informative hook should be educational"
            elif style == "aesthetic":
                aesthetic_keywords = [
                    "beautiful",
                    "stunning",
                    "visual",
                    "artistic",
                    "amazing",
                    "breathtaking",
                ]
                assert any(
                    keyword in hook.lower() for keyword in aesthetic_keywords
                ), "Aesthetic hook should emphasize visuals"

    @pytest.mark.asyncio
    async def test_platform_algorithm_optimization(
        self, format_adapter, sample_content
    ):
        """
        Test optimization for specific platform algorithms.

        RED PHASE: This test should FAIL initially.

        Validates:
        - Content is optimized for platform-specific engagement factors
        - Algorithm optimization affects content structure appropriately
        - Different engagement focuses produce different optimizations
        - Optimization maintains content quality and coherence
        """
        # Test different engagement focus types
        engagement_focuses = ["retention", "watch_time", "shares"]

        for focus in engagement_focuses:
            # Act
            optimized_content = await format_adapter._optimize_for_platform_algorithm(
                sample_content, focus
            )

            # Assert
            assert (
                "scenes" in optimized_content
            ), f"Should contain scenes for {focus} optimization"
            assert (
                len(optimized_content["scenes"]) > 0
            ), f"Should maintain content for {focus} optimization"

            # Focus-specific optimizations
            if focus == "retention":
                # Should prioritize high-intensity scenes early
                first_scene = optimized_content["scenes"][0]
                assert (
                    first_scene["emotional_intensity"] >= 0.8
                ), "Retention optimization should lead with high-intensity content"

            elif focus == "watch_time":
                # Should maintain balanced pacing for completion
                durations = [scene["duration"] for scene in optimized_content["scenes"]]
                duration_variance = max(durations) - min(durations)
                assert (
                    duration_variance <= 6.0
                ), "Watch time optimization should balance scene durations"

            elif focus == "shares":
                # Should include highly shareable moments
                total_intensity = sum(
                    scene["emotional_intensity"]
                    for scene in optimized_content["scenes"]
                )
                avg_intensity = total_intensity / len(optimized_content["scenes"])
                assert (
                    avg_intensity >= 0.7
                ), "Share optimization should maintain high emotional intensity"

    @pytest.mark.asyncio
    async def test_content_analysis_and_scene_selection(self, format_adapter):
        """
        Test AI-powered content analysis and key scene selection.

        RED PHASE: This test should FAIL initially.

        Validates:
        - AI analyzes content for importance and emotional impact
        - Scene selection algorithm works correctly
        - Selected scenes maintain narrative coherence
        - Selection criteria can be customized per platform
        """
        # Arrange
        test_scenes = [
            {"duration": 5.0, "emotional_intensity": 0.3, "characters": ["Minor1"]},
            {
                "duration": 8.0,
                "emotional_intensity": 0.9,
                "characters": ["Naruto", "Sasuke"],
            },
            {"duration": 4.0, "emotional_intensity": 0.5, "characters": ["Sakura"]},
            {
                "duration": 10.0,
                "emotional_intensity": 1.0,
                "characters": ["Naruto", "Sasuke", "Sakura"],
            },
            {"duration": 3.0, "emotional_intensity": 0.2, "characters": ["Background"]},
        ]

        content = {"scenes": test_scenes}
        target_duration = 15  # Should select ~2-3 scenes

        # Act
        selected_scenes = await format_adapter._ai_select_key_scenes(
            test_scenes, target_duration, "fast"
        )

        # Assert
        selected_duration = sum(scene["duration"] for scene in selected_scenes)
        assert (
            selected_duration <= target_duration + 3
        ), "Selected scenes should fit target duration"
        assert len(selected_scenes) < len(test_scenes), "Should select subset of scenes"

        # Assert selection quality
        selected_intensities = [
            scene["emotional_intensity"] for scene in selected_scenes
        ]
        avg_selected_intensity = sum(selected_intensities) / len(selected_intensities)

        original_intensities = [scene["emotional_intensity"] for scene in test_scenes]
        avg_original_intensity = sum(original_intensities) / len(original_intensities)

        assert (
            avg_selected_intensity >= avg_original_intensity
        ), "Selected scenes should have higher average emotional intensity"

    @pytest.mark.asyncio
    async def test_engagement_factors_analysis(self, format_adapter, sample_content):
        """
        Test analysis of engagement factors for prediction.

        RED PHASE: This test should FAIL initially.

        Validates:
        - Content features are analyzed for engagement potential
        - Analysis considers character appeal, action density, emotional impact
        - Feature extraction provides meaningful engagement indicators
        - Analysis results inform prediction algorithms
        """
        # Act
        engagement_factors = await format_adapter._analyze_engagement_factors(
            sample_content
        )

        # Assert
        assert isinstance(
            engagement_factors, dict
        ), "Should return engagement factors dict"

        required_factors = [
            "action_density",
            "emotional_variance",
            "character_appeal",
            "narrative_coherence",
            "pacing_score",
        ]

        for factor in required_factors:
            assert factor in engagement_factors, f"Should include {factor} in analysis"
            assert isinstance(
                engagement_factors[factor], (int, float)
            ), f"{factor} should be numeric"
            assert (
                0.0 <= engagement_factors[factor] <= 1.0
            ), f"{factor} should be normalized (0.0-1.0)"

    @pytest.mark.asyncio
    async def test_platform_configuration_validation(self, format_adapter):
        """
        Test platform configuration validation and constraints.

        RED PHASE: This test should FAIL initially.

        Validates:
        - Platform configurations are valid and consistent
        - All required platforms are configured
        - Configuration constraints are logical
        - Platform-specific parameters are appropriate
        """
        # Assert required platforms exist
        required_platforms = ["tiktok", "youtube_shorts", "instagram_reels"]
        for platform in required_platforms:
            assert (
                platform in format_adapter.platform_configs
            ), f"Should have configuration for {platform}"

            config = format_adapter.platform_configs[platform]
            assert isinstance(
                config, PlatformConfig
            ), f"Should have PlatformConfig for {platform}"

            # Validate configuration parameters
            assert (
                config.max_duration > 0
            ), f"{platform} should have positive max duration"
            assert (
                config.optimal_length > 0
            ), f"{platform} should have positive optimal length"
            assert (
                config.optimal_length <= config.max_duration
            ), f"{platform} optimal length should not exceed max duration"
            assert (
                config.aspect_ratio[0] > 0 and config.aspect_ratio[1] > 0
            ), f"{platform} should have valid aspect ratio"

        # Assert platform differences
        tiktok_config = format_adapter.platform_configs["tiktok"]
        youtube_config = format_adapter.platform_configs["youtube_shorts"]
        instagram_config = format_adapter.platform_configs["instagram_reels"]

        assert tiktok_config.hook_style == "viral", "TikTok should use viral hooks"
        assert (
            youtube_config.hook_style == "informative"
        ), "YouTube should use informative hooks"
        assert (
            instagram_config.hook_style == "aesthetic"
        ), "Instagram should use aesthetic hooks"

    @pytest.mark.asyncio
    async def test_performance_constraints_platform_adaptation(
        self, format_adapter, sample_content, sample_quality_profile
    ):
        """
        Test performance constraints for platform adaptation.

        RED PHASE: This test should FAIL initially.

        Validates:
        - Platform adaptation completes within 30s for multi-platform export
        - Memory usage stays reasonable during adaptation
        - Concurrent platform processing works efficiently
        - Performance scales acceptably with content size
        """
        import time
        import psutil
        import gc

        # Arrange
        platforms = ["tiktok", "youtube_shorts", "instagram_reels"]

        # Measure initial state
        gc.collect()
        initial_memory = psutil.Process().memory_info().rss / 1024**2  # MB
        start_time = time.time()

        # Act
        batch_results = await format_adapter.batch_adapt_for_platforms(
            sample_content, platforms, sample_quality_profile
        )

        # Measure completion
        end_time = time.time()
        processing_time = end_time - start_time

        gc.collect()
        final_memory = psutil.Process().memory_info().rss / 1024**2  # MB
        memory_increase = final_memory - initial_memory

        # Assert performance constraints
        assert processing_time < 30.0, (
            f"Multi-platform adaptation should complete within 30s, "
            f"took {processing_time:.1f}s"
        )
        assert memory_increase < 300, (
            f"Memory increase should be reasonable, "
            f"increased by {memory_increase:.1f}MB"
        )
        assert len(batch_results) == len(
            platforms
        ), "Should successfully process all platforms"

    def test_platform_config_data_structures(self, format_adapter):
        """
        Test platform configuration data structures.

        RED PHASE: This test should FAIL initially.

        Validates:
        - PlatformConfig objects are properly structured
        - Configuration values are within expected ranges
        - Data structures support required operations
        """
        # Test PlatformConfig creation
        config = PlatformConfig(
            max_duration=60,
            hook_style="viral",
            pacing="fast",
            engagement_focus="retention",
            aspect_ratio=(9, 16),
            optimal_length=15,
        )

        assert config.max_duration == 60
        assert config.hook_style == "viral"
        assert config.pacing == "fast"
        assert config.engagement_focus == "retention"
        assert config.aspect_ratio == (9, 16)
        assert config.optimal_length == 15

    def test_engagement_prediction_data_structures(self):
        """
        Test engagement prediction data structures.

        RED PHASE: This test should FAIL initially.

        Validates:
        - EngagementPrediction objects are properly structured
        - Prediction values are within valid ranges
        - Data structures support comparison and analysis
        """
        # Test EngagementPrediction creation
        prediction = EngagementPrediction(
            retention_rate=0.75,
            completion_rate=0.60,
            share_probability=0.30,
            confidence_score=0.85,
        )

        assert prediction.retention_rate == 0.75
        assert prediction.completion_rate == 0.60
        assert prediction.share_probability == 0.30
        assert prediction.confidence_score == 0.85


if __name__ == "__main__":
    # Run tests to verify they fail (RED phase)
    pytest.main([__file__, "-v"])
