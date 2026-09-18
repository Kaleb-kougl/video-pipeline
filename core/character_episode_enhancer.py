#!/usr/bin/env python3
"""
Character Episode Enhancer - Phase 2 Quality Enhancement

Integrates character analysis data into episode processing to enhance
video quality through character-aware timing, prompt enhancement, and
visual consistency based on character importance and development.
"""

import logging
from typing import Dict, List, Any
from dataclasses import dataclass


@dataclass
class CharacterWeight:
    """Character importance weight for scene timing and visual enhancement."""

    character_name: str
    importance_score: float  # 0.0 to 1.0
    character_development: float  # Character arc progression
    screen_time_ratio: float  # Percentage of episode presence


class EpisodeCharacterEnhancer:
    """
    Integrate character analysis insights into episode processing.

    This class enhances episode content by:
    - Calculating character importance weights from analysis data
    - Adjusting scene timing based on character significance
    - Enhancing visual prompts with character appearance consistency
    - Maintaining character development context throughout episodes
    """

    def __init__(self, character_analyzer, timing_calculator):
        """
        Initialize the Episode Character Enhancer.

        Args:
            character_analyzer: Character analysis agent for data retrieval
            timing_calculator: Timing calculation utilities
        """
        self.character_analyzer = character_analyzer
        self.timing_calculator = timing_calculator
        self.logger = logging.getLogger(__name__)

    async def enhance_episode_with_character_data(
        self, episode_content: Dict[str, Any], character_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Integrate character insights into episode processing.

        Args:
            episode_content: Raw episode content from transcript
            character_analysis: Character analysis from ChromaDB

        Returns:
            Enhanced episode with character-aware timing and prompts
        """
        self.logger.info("Starting episode enhancement with character data")

        # Extract all characters mentioned in this episode
        episode_characters = await self._extract_episode_characters(episode_content)
        enhanced_scenes = []

        # Process each scene with character enhancement
        for scene in episode_content["scenes"]:
            # Identify characters in this specific scene
            scene_characters = self._identify_scene_characters(
                scene, episode_characters
            )

            # Calculate character importance weights for this scene
            character_weights = await self._calculate_character_weights(
                scene_characters, character_analysis
            )

            # Adjust timing based on character importance
            enhanced_duration = self._adjust_timing_for_characters(
                scene["base_duration"], character_weights
            )

            # Enhance visual prompt with character context
            enhanced_prompt = await self._enhance_prompt_with_character_context(
                scene["prompt"], scene_characters, character_analysis
            )

            # Create enhanced scene with all improvements
            enhanced_scene = {
                **scene,
                "duration": enhanced_duration,
                "enhanced_prompt": enhanced_prompt,
                "character_weights": character_weights,
            }
            enhanced_scenes.append(enhanced_scene)

        # Calculate total enhanced duration
        total_duration = sum(scene["duration"] for scene in enhanced_scenes)

        self.logger.info(
            f"Enhanced episode with {len(enhanced_scenes)} scenes, "
            f"total duration: {total_duration:.1f}s"
        )

        return {
            "scenes": enhanced_scenes,
            "character_focus": episode_characters,
            "total_duration": total_duration,
        }

    async def _extract_episode_characters(
        self, episode_content: Dict[str, Any]
    ) -> List[str]:
        """
        Extract all unique characters mentioned across episode scenes.

        Args:
            episode_content: Episode content with scenes

        Returns:
            List of unique character names in the episode
        """
        all_characters = set()

        for scene in episode_content.get("scenes", []):
            scene_chars = scene.get("characters", [])
            all_characters.update(scene_chars)

        return sorted(list(all_characters))

    def _identify_scene_characters(
        self, scene: Dict[str, Any], episode_characters: List[str]
    ) -> List[str]:
        """
        Identify which characters are present in a specific scene.

        Args:
            scene: Scene data with character information
            episode_characters: All characters in the episode

        Returns:
            List of character names present in this scene
        """
        scene_characters = scene.get("characters", [])

        # Filter to only include known episode characters
        identified_characters = [
            char for char in scene_characters if char in episode_characters
        ]

        return identified_characters

    async def _calculate_character_weights(
        self, scene_characters: List[str], character_analysis: Dict[str, Any]
    ) -> List[CharacterWeight]:
        """
        Calculate character importance weights for timing adjustment.

        Args:
            scene_characters: Characters present in the scene
            character_analysis: Character analysis data from ChromaDB

        Returns:
            List of CharacterWeight objects for the scene
        """
        weights = []
        character_profiles = character_analysis.get("profiles", {})

        for character in scene_characters:
            if character in character_profiles:
                profile = character_profiles[character]

                # Extract and clamp values to valid ranges
                importance_score = max(
                    0.0, min(1.0, profile.get("importance_score", 0.5))
                )
                development_factor = max(
                    0.0, min(1.0, profile.get("character_development", 0.5))
                )
                screen_time_ratio = max(
                    0.0, min(1.0, profile.get("screen_time_percentage", 0.1))
                )

                weight = CharacterWeight(
                    character_name=character,
                    importance_score=importance_score,
                    character_development=development_factor,
                    screen_time_ratio=screen_time_ratio,
                )
                weights.append(weight)

                self.logger.debug(
                    f"Calculated weight for {character}: "
                    f"importance={importance_score:.2f}, "
                    f"development={development_factor:.2f}"
                )

        return weights

    def _adjust_timing_for_characters(
        self, base_duration: float, character_weights: List[CharacterWeight]
    ) -> float:
        """
        Adjust scene timing based on character importance weights.

        Args:
            base_duration: Original scene duration in seconds
            character_weights: Character importance weights for the scene

        Returns:
            Adjusted duration in seconds (constrained to 1.5-15.0 range)
        """
        if not character_weights:
            return max(1.5, min(15.0, base_duration))

        # Calculate combined character importance
        # Use maximum importance for scenes with multiple important characters
        max_importance = max(w.importance_score for w in character_weights)
        avg_importance = sum(w.importance_score for w in character_weights) / len(
            character_weights
        )

        # Use weighted importance (favor maximum but consider average)
        combined_importance = (max_importance * 0.7) + (avg_importance * 0.3)

        # Calculate development bonus (characters with growth get more time)
        max_development = max(w.character_development for w in character_weights)
        avg_development = sum(w.character_development for w in character_weights) / len(
            character_weights
        )
        combined_development = (max_development * 0.6) + (avg_development * 0.4)

        # Multiple character bonus (more characters = more interaction time needed)
        character_count_bonus = min(0.2, len(character_weights) * 0.05)

        # Adjustment factor: 0.7 to 1.3 (±30% as specified)
        importance_multiplier = 0.7 + (combined_importance * 0.6)  # 0.7-1.3 range
        development_bonus = (
            combined_development * 0.2
        )  # Up to 20% bonus for development

        adjustment_factor = (
            importance_multiplier + development_bonus + character_count_bonus
        )
        adjusted_duration = base_duration * adjustment_factor

        # Enforce constraints: 1.5-15.0 seconds
        final_duration = max(1.5, min(15.0, adjusted_duration))

        self.logger.debug(
            f"Timing adjustment: {base_duration:.1f}s -> {final_duration:.1f}s "
            f"(factor: {adjustment_factor:.2f})"
        )

        return final_duration

    async def _enhance_prompt_with_character_context(
        self,
        base_prompt: str,
        scene_characters: List[str],
        character_analysis: Dict[str, Any],
    ) -> str:
        """
        Enhance visual prompt with character appearance consistency.

        Args:
            base_prompt: Original scene description
            scene_characters: Characters present in the scene
            character_analysis: Character analysis data

        Returns:
            Enhanced prompt with character appearance and personality context
        """
        if not scene_characters:
            return base_prompt

        character_profiles = character_analysis.get("profiles", {})
        character_descriptions = []

        for character in scene_characters:
            if character in character_profiles:
                profile = character_profiles[character]

                # Build character appearance description
                personality_traits = profile.get("personality_traits", [])

                char_description = f"{character}"

                # Add personality-based visual cues
                if personality_traits:
                    trait_descriptions = {
                        "determined": "with determined expression and strong stance",
                        "kind": "with gentle eyes and warm demeanor",
                        "brave": "with confident posture and fearless gaze",
                        "intelligent": "with thoughtful expression and sharp eyes",
                        "stubborn": "with intense gaze and defiant posture",
                        "confident": "with self-assured stance and commanding presence",
                        "anxious": "with worried expression and hesitant posture",
                    }

                    # Include both trait names and visual descriptions
                    trait_visuals = []
                    for trait in personality_traits[:2]:  # Limit to top 2 traits
                        visual_desc = trait_descriptions.get(
                            trait, f"showing {trait} characteristics"
                        )
                        trait_visuals.append(f"{trait} ({visual_desc})")

                    if trait_visuals:
                        char_description += f" [{', '.join(trait_visuals)}]"

                character_descriptions.append(char_description)

        # Combine character descriptions with base prompt
        if character_descriptions:
            character_context = ", ".join(character_descriptions)
            enhanced_prompt = (
                f"{base_prompt}. Characters: {character_context}. "
                f"Maintain consistent character appearance and anime art style."
            )
        else:
            enhanced_prompt = f"{base_prompt}. Maintain consistent anime art style."

        self.logger.debug(
            f"Enhanced prompt from {len(base_prompt)} to {len(enhanced_prompt)} chars"
        )

        return enhanced_prompt
