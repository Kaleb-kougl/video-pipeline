#!/usr/bin/env python3
"""
Intelligent Format Adapter - Phase 2 Quality Enhancement

AI-powered content adaptation for different social media platforms with
intelligent content condensation, engagement prediction, and multi-platform
batch export optimization.
"""

import asyncio
import logging
import zlib
from dataclasses import dataclass
from typing import Any


@dataclass
class PlatformConfig:
    """Platform-specific configuration and constraints."""

    max_duration: int
    hook_style: str  # 'viral', 'informative', 'aesthetic'
    pacing: str  # 'fast', 'medium', 'slow'
    engagement_focus: str  # 'retention', 'watch_time', 'shares'
    aspect_ratio: tuple[int, int]  # (width, height)
    optimal_length: int  # seconds for best engagement


@dataclass
class EngagementPrediction:
    """Predicted engagement metrics for platform content."""

    retention_rate: float
    completion_rate: float
    share_probability: float
    confidence_score: float


class IntelligentFormatAdapter:
    """
    AI-powered content adaptation for different social media platforms.

    This class provides:
    - Platform-specific content optimization
    - AI-powered content condensation
    - Engagement prediction and optimization
    - Multi-platform batch export
    - Hook generation tailored to platform algorithms
    """

    def __init__(self) -> None:
        """Initialize the Intelligent Format Adapter with platform configurations."""
        self.platform_configs = {
            "tiktok": PlatformConfig(
                max_duration=60,
                hook_style="viral",
                pacing="fast",
                engagement_focus="retention",
                aspect_ratio=(9, 16),
                optimal_length=15,
            ),
            "youtube_shorts": PlatformConfig(
                max_duration=60,
                hook_style="informative",
                pacing="medium",
                engagement_focus="watch_time",
                aspect_ratio=(9, 16),
                optimal_length=30,
            ),
            "instagram_reels": PlatformConfig(
                max_duration=90,
                hook_style="aesthetic",
                pacing="medium",
                engagement_focus="shares",
                aspect_ratio=(9, 16),
                optimal_length=25,
            ),
        }
        self.logger = logging.getLogger(__name__)

        self.logger.info("Intelligent Format Adapter initialized with platform configs")

    async def adapt_content_for_platform(
        self, content: dict[str, Any], platform: str, quality_profile: Any
    ) -> dict[str, Any]:
        """
        Intelligently adapt content for platform-specific requirements.

        Args:
            content: Original episode content with scenes
            platform: Target platform ('tiktok', 'youtube_shorts', 'instagram_reels')
            quality_profile: Quality profile for processing constraints

        Returns:
            Dictionary with adapted content and engagement predictions

        Raises:
            ValueError: If platform is not supported
        """
        if platform not in self.platform_configs:
            raise ValueError(f"Unsupported platform: {platform}")

        config = self.platform_configs[platform]
        self.logger.info(f"Adapting content for {platform} (max: {config.max_duration}s)")

        # Calculate current content duration
        current_duration = sum(scene["duration"] for scene in content["scenes"])

        # AI-powered content condensation if needed
        if current_duration > config.max_duration:
            condensed_content = await self._ai_condense_content(
                content, config.max_duration, config.pacing
            )
        else:
            condensed_content = content

        # Generate platform-specific hook
        enhanced_hook = await self._generate_platform_hook(
            condensed_content["scenes"][0], config.hook_style
        )

        # Optimize for platform algorithm
        optimized_content = await self._optimize_for_platform_algorithm(
            condensed_content, config.engagement_focus
        )

        # Predict engagement
        engagement_prediction = await self._predict_engagement(optimized_content, platform)

        # Calculate adaptation metadata
        final_duration = sum(scene["duration"] for scene in optimized_content["scenes"])
        compression_ratio = current_duration / final_duration if final_duration > 0 else 1.0

        self.logger.info(
            f"Content adapted for {platform}: {current_duration:.1f}s -> {final_duration:.1f}s "
            f"(compression: {compression_ratio:.2f}x)"
        )

        return {
            "adapted_content": optimized_content,
            "platform_optimized_hook": enhanced_hook,
            "engagement_prediction": engagement_prediction,
            "adaptation_metadata": {
                "original_duration": current_duration,
                "adapted_duration": final_duration,
                "compression_ratio": compression_ratio,
                "quality_profile": quality_profile.name,
            },
        }

    async def batch_adapt_for_platforms(
        self, content: dict[str, Any], platforms: list[str], quality_profile: Any
    ) -> dict[str, dict[str, Any]]:
        """
        Efficiently adapt content for multiple platforms simultaneously.

        Args:
            content: Original episode content
            platforms: List of target platforms
            quality_profile: Quality profile for processing

        Returns:
            Dictionary mapping platform names to adaptation results
        """
        self.logger.info(f"Batch adapting content for {len(platforms)} platforms")

        # Create concurrent adaptation tasks
        adaptation_tasks = []
        for platform in platforms:
            task = asyncio.create_task(
                self.adapt_content_for_platform(content, platform, quality_profile)
            )
            adaptation_tasks.append((platform, task))

        # Wait for all adaptations to complete
        results = {}
        for platform, task in adaptation_tasks:
            try:
                results[platform] = await task
                self.logger.debug(f"Completed adaptation for {platform}")
            except Exception as e:
                self.logger.error(f"Failed to adapt content for {platform}: {e}")
                results[platform] = {"error": str(e)}

        self.logger.info(f"Batch adaptation completed for {len(results)} platforms")
        return results

    async def _ai_condense_content(
        self, content: dict[str, Any], target_duration: int, pacing: str
    ) -> dict[str, Any]:
        """
        Use AI to intelligently condense content to target duration.

        Args:
            content: Original content with scenes
            target_duration: Target duration in seconds
            pacing: Desired pacing ('fast', 'medium', 'slow')

        Returns:
            Condensed content that fits target duration
        """
        current_duration = sum(scene["duration"] for scene in content["scenes"])
        compression_ratio = target_duration / current_duration

        self.logger.debug(
            f"Condensing content: {current_duration:.1f}s -> {target_duration}s "
            f"(ratio: {compression_ratio:.2f})"
        )

        if compression_ratio >= 0.8:
            # Minor trimming needed - use proportional reduction
            condensed_scenes = await self._trim_scenes_proportionally(
                content["scenes"], compression_ratio
            )
        else:
            # Major condensation needed - use AI to select key scenes
            condensed_scenes = await self._ai_select_key_scenes(
                content["scenes"], target_duration, pacing
            )

        return {"scenes": condensed_scenes}

    async def _trim_scenes_proportionally(
        self, scenes: list[dict[str, Any]], compression_ratio: float
    ) -> list[dict[str, Any]]:
        """
        Trim scenes proportionally to achieve target compression.

        Args:
            scenes: Original scenes list
            compression_ratio: Target compression ratio (0.0-1.0)

        Returns:
            Scenes with proportionally reduced durations
        """
        trimmed_scenes = []

        for scene in scenes:
            trimmed_scene = scene.copy()
            # Reduce duration proportionally
            trimmed_scene["duration"] = scene["duration"] * compression_ratio
            # Ensure minimum duration
            trimmed_scene["duration"] = max(1.0, trimmed_scene["duration"])
            trimmed_scenes.append(trimmed_scene)

        return trimmed_scenes

    async def _ai_select_key_scenes(
        self, scenes: list[dict[str, Any]], target_duration: int, pacing: str
    ) -> list[dict[str, Any]]:
        """
        Use AI to select key scenes for major content condensation.

        Args:
            scenes: Original scenes list
            target_duration: Target total duration
            pacing: Desired pacing style

        Returns:
            Selected key scenes that fit target duration
        """
        # Calculate scene importance scores
        scene_scores = []
        for i, scene in enumerate(scenes):
            # Score based on emotional intensity, character count, and duration
            emotional_weight = scene.get("emotional_intensity", 0.5)
            character_weight = len(scene.get("characters", [])) * 0.1
            duration_weight = min(1.0, scene["duration"] / 10.0)  # Normalize duration

            # Pacing-based adjustments
            if pacing == "fast":
                # Favor high-intensity, shorter scenes
                importance_score = (
                    emotional_weight * 0.6 + character_weight * 0.3 + (1 - duration_weight) * 0.1
                )
            else:
                # Favor well-developed scenes
                importance_score = (
                    emotional_weight * 0.4 + character_weight * 0.3 + duration_weight * 0.3
                )

            scene_scores.append((i, scene, importance_score))

        # Sort by importance score
        scene_scores.sort(key=lambda x: x[2], reverse=True)

        # Select scenes to fit target duration
        selected_scenes = []
        accumulated_duration = 0

        for _, scene, _score in scene_scores:
            if accumulated_duration + scene["duration"] <= target_duration:
                selected_scenes.append(scene)
                accumulated_duration += scene["duration"]
            elif len(selected_scenes) == 0:
                # Must include at least one scene, even if it exceeds target
                # Trim it to fit
                trimmed_scene = scene.copy()
                trimmed_scene["duration"] = target_duration
                selected_scenes.append(trimmed_scene)
                break

        # Sort selected scenes back to original order for narrative coherence
        selected_scenes.sort(key=lambda s: scenes.index(s) if s in scenes else 999)

        self.logger.debug(
            f"Selected {len(selected_scenes)} key scenes from {len(scenes)} "
            f"for {accumulated_duration:.1f}s total"
        )

        return selected_scenes

    async def _generate_platform_hook(self, first_scene: dict[str, Any], hook_style: str) -> str:
        """
        Generate platform-specific hook for the opening scene.

        Args:
            first_scene: First scene of the adapted content
            hook_style: Hook style ('viral', 'informative', 'aesthetic')

        Returns:
            Platform-optimized hook text
        """
        scene_content = first_scene.get("prompt", "")
        characters = first_scene.get("characters", [])

        if hook_style == "viral":
            # TikTok-style viral hook
            hook_templates = [
                "You won't believe what happens when {characters} {action}!",
                "This amazing {scene_type} will blow your mind!",
                "Wait until you see this incredible {scene_type}!",
                "The most insane {scene_type} you'll ever see!",
                "Epic {scene_type} that's absolutely unbelievable!",
            ]
        elif hook_style == "informative":
            # YouTube Shorts-style informative hook
            hook_templates = [
                "Here's how {characters} master this incredible technique:",
                "Learn the strategy behind this epic {scene_type}:",
                "Discover the hidden meaning in this {scene_type}:",
                "The complete breakdown of this amazing {scene_type}:",
            ]
        elif hook_style == "aesthetic":
            # Instagram Reels-style aesthetic hook
            hook_templates = [
                "The most beautiful {scene_type} featuring {characters}",
                "Stunning visuals as {characters} {action}",
                "Breathtaking animation in this {scene_type}",
                "Visual masterpiece: {characters} in action",
            ]
        else:
            hook_templates = ["Amazing scene featuring {characters}"]

        # Extract scene elements
        action = "battle" if "battle" in scene_content.lower() else "scene"
        scene_type = "battle" if "battle" in scene_content.lower() else "moment"
        character_text = " and ".join(characters[:2]) if characters else "heroes"

        # Select and format hook template.
        # crc32, not hash(): str hashing is PYTHONHASHSEED-randomized per
        # process, so hash() here picked a different template between runs.
        index = zlib.crc32(scene_content.encode("utf-8")) % len(hook_templates)
        template = hook_templates[index]
        hook = template.format(characters=character_text, action=action, scene_type=scene_type)

        return hook

    async def _optimize_for_platform_algorithm(
        self, content: dict[str, Any], engagement_focus: str
    ) -> dict[str, Any]:
        """
        Optimize content for specific platform algorithm requirements.

        Args:
            content: Content to optimize
            engagement_focus: Platform engagement focus ('retention', 'watch_time', 'shares')

        Returns:
            Algorithm-optimized content
        """
        scenes = content["scenes"].copy()

        if engagement_focus == "retention":
            # TikTok-style: Lead with highest intensity
            scenes.sort(key=lambda s: s.get("emotional_intensity", 0.5), reverse=True)
            # Reorder to put most engaging scene first, maintain some narrative flow
            if len(scenes) > 1:
                most_engaging = scenes[0]
                remaining_scenes = scenes[1:]
                # Sort remaining by original order for coherence
                optimized_scenes = [most_engaging] + remaining_scenes

        elif engagement_focus == "watch_time":
            # YouTube-style: Balanced pacing for completion
            # Adjust durations for optimal watch time
            total_duration = sum(scene["duration"] for scene in scenes)
            target_avg = total_duration / len(scenes)

            for scene in scenes:
                # More aggressive duration balancing
                if scene["duration"] > target_avg * 1.2:
                    scene["duration"] = target_avg * 1.1
                elif scene["duration"] < target_avg * 0.8:
                    scene["duration"] = target_avg * 0.9

            optimized_scenes = scenes

        elif engagement_focus == "shares":
            # Instagram-style: Emphasize visually appealing content
            # Filter and prioritize high-intensity, visually rich scenes
            high_impact_scenes = [
                scene for scene in scenes if scene.get("emotional_intensity", 0.5) >= 0.7
            ]

            # If we filtered too much, add back some medium-intensity scenes
            if len(high_impact_scenes) < 2 and len(scenes) > 2:
                medium_scenes = [
                    scene for scene in scenes if 0.5 <= scene.get("emotional_intensity", 0.5) < 0.7
                ]
                high_impact_scenes.extend(medium_scenes[:2])

            optimized_scenes = high_impact_scenes if high_impact_scenes else scenes

        else:
            # Default: no specific optimization
            optimized_scenes = scenes

        self.logger.debug(
            f"Optimized content for {engagement_focus}: "
            f"{len(scenes)} -> {len(optimized_scenes)} scenes"
        )

        return {"scenes": optimized_scenes}

    async def _predict_engagement(
        self, content: dict[str, Any], platform: str
    ) -> EngagementPrediction:
        """
        Predict engagement metrics for platform content.

        Args:
            content: Adapted content for prediction
            platform: Target platform

        Returns:
            EngagementPrediction with platform-specific metrics
        """
        # Analyze content for engagement factors
        engagement_factors = await self._analyze_engagement_factors(content)

        # Platform-specific prediction algorithms
        if platform == "tiktok":
            # TikTok algorithm factors
            retention_rate = min(
                1.0,
                engagement_factors["action_density"] * 0.4
                + engagement_factors["emotional_variance"] * 0.3
                + engagement_factors["pacing_score"] * 0.3,
            )
            completion_rate = retention_rate * 0.7  # TikTok has lower completion rates
            share_probability = retention_rate * 0.8  # High retention -> high shares

        elif platform == "youtube_shorts":
            # YouTube algorithm factors (watch time focused)
            completion_rate = min(
                1.0,
                engagement_factors["narrative_coherence"] * 0.4
                + engagement_factors["character_appeal"] * 0.3
                + (1 - engagement_factors["emotional_variance"]) * 0.3,
            )  # Less variance = better completion
            retention_rate = completion_rate * 0.9
            share_probability = completion_rate * 0.5  # Lower share rate than TikTok

        elif platform == "instagram_reels":
            # Instagram algorithm factors (aesthetic and shares focused)
            share_probability = min(
                1.0,
                engagement_factors["emotional_variance"] * 0.4
                + engagement_factors["character_appeal"] * 0.3
                + engagement_factors["action_density"] * 0.3,
            )
            retention_rate = share_probability * 0.8
            completion_rate = share_probability * 0.6

        else:
            # Default predictions
            retention_rate = completion_rate = share_probability = 0.5

        # Calculate confidence based on content analysis quality
        confidence_score = min(
            1.0,
            (
                engagement_factors.get("narrative_coherence", 0.5)
                + engagement_factors.get("character_appeal", 0.5)
            )
            / 2.0,
        )

        return EngagementPrediction(
            retention_rate=retention_rate,
            completion_rate=completion_rate,
            share_probability=share_probability,
            confidence_score=confidence_score,
        )

    async def _analyze_engagement_factors(self, content: dict[str, Any]) -> dict[str, float]:
        """
        Analyze content for engagement prediction factors.

        Args:
            content: Content to analyze

        Returns:
            Dictionary of engagement factors (0.0-1.0 normalized)
        """
        scenes = content["scenes"]

        if not scenes:
            return {
                "action_density": 0.0,
                "emotional_variance": 0.0,
                "character_appeal": 0.0,
                "narrative_coherence": 0.0,
                "pacing_score": 0.0,
            }

        # Calculate action density (based on emotional intensity)
        intensities = [scene.get("emotional_intensity", 0.5) for scene in scenes]
        action_density = sum(intensities) / len(intensities)

        # Calculate emotional variance (variety keeps interest)
        if len(intensities) > 1:
            import statistics

            emotional_variance = statistics.stdev(intensities) / 0.5  # Normalize by max stdev
            emotional_variance = min(1.0, emotional_variance)
        else:
            emotional_variance = 0.0

        # Calculate character appeal (more unique characters = higher appeal)
        all_characters = set()
        for scene in scenes:
            all_characters.update(scene.get("characters", []))

        character_appeal = min(1.0, len(all_characters) / 5.0)  # Normalize by typical cast size

        # Calculate narrative coherence (scene connection and flow)
        # Simplified: based on character continuity between scenes
        coherence_score = 0.0
        if len(scenes) > 1:
            continuity_count = 0
            for i in range(len(scenes) - 1):
                current_chars = set(scenes[i].get("characters", []))
                next_chars = set(scenes[i + 1].get("characters", []))
                if current_chars & next_chars:  # Common characters
                    continuity_count += 1

            coherence_score = continuity_count / (len(scenes) - 1)

        # Calculate pacing score (duration variance affects pacing)
        durations = [scene["duration"] for scene in scenes]
        if len(durations) > 1:
            import statistics

            avg_duration = statistics.mean(durations)
            duration_variance = statistics.stdev(durations)
            # Good pacing has moderate variance
            pacing_score = 1.0 - min(1.0, duration_variance / avg_duration)
        else:
            pacing_score = 1.0

        return {
            "action_density": action_density,
            "emotional_variance": emotional_variance,
            "character_appeal": character_appeal,
            "narrative_coherence": coherence_score,
            "pacing_score": pacing_score,
        }
