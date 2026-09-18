#!/usr/bin/env python3
"""
Visual Coherence Manager - Phase 2 Quality Enhancement

Maintains visual consistency and coherence across episode images through
style validation, character appearance consistency, color palette coherence,
and intelligent retry mechanisms with OpenCV-based analysis.
"""

import inspect
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

# An image generator takes a fully enhanced prompt and returns the path of the
# image file it wrote to disk. It may be a coroutine function or a plain one.
ImageGenerator = Callable[[str], str | Awaitable[str]]


@dataclass
class VisualConsistencyMetrics:
    """Metrics for visual consistency evaluation."""

    color_coherence_score: float
    style_consistency_score: float
    character_similarity_score: float
    overall_score: float


class VisualCoherenceManager:
    """
    Maintain visual consistency and coherence across episode images.

    This class provides:
    - Coherence-aware prompt construction (style + character + scene)
    - Visual consistency scoring using OpenCV and computer vision
    - Character appearance consistency tracking
    - Episode color palette coherence maintenance
    - Intelligent retry mechanism for low-consistency images
    - Reference data management for style and character templates

    This class does NOT generate images. `generate_consistent_image` drives a
    generate/score/retry loop around an image generator that the caller must
    inject; without one it raises NotImplementedError rather than inventing a
    path. Callers that only want the prompt-construction half (which needs no
    generator at all) should use `build_coherent_prompt`.
    """

    def __init__(
        self,
        consistency_threshold: float = 0.8,
        image_generator: ImageGenerator | None = None,
    ):
        """
        Initialize the Visual Coherence Manager.

        Args:
            consistency_threshold: Minimum consistency score to accept (0.0-1.0)
            image_generator: Callable that takes an enhanced prompt, generates an
                image, writes it to disk and returns its path. Required only for
                `generate_consistent_image`; may be sync or async.
        """
        self.consistency_threshold = max(0.0, min(1.0, consistency_threshold))
        self.image_generator = image_generator
        self.style_templates: dict[str, dict] = {}
        self.character_references: dict[str, np.ndarray] = {}
        self.episode_color_palettes: dict[str, list[list[int]]] = {}
        self.logger = logging.getLogger(__name__)

        self.logger.info(
            f"Visual Coherence Manager initialized with threshold {self.consistency_threshold}"
        )

    async def generate_consistent_image(
        self,
        prompt: str,
        characters: list[str],
        episode_context: dict[str, Any],
        max_attempts: int = 3,
    ) -> str:
        """
        Generate image with consistent style and character appearance.

        Args:
            prompt: Base scene description for image generation
            characters: List of characters present in the scene
            episode_context: Episode context including style and color info
            max_attempts: Maximum retry attempts for consistency

        Returns:
            Path to generated image that meets consistency threshold

        Raises:
            NotImplementedError: If no image generator has been injected.
        """
        if self.image_generator is None:
            raise NotImplementedError(
                "VisualCoherenceManager cannot generate images on its own. "
                "Inject an image generator (VisualCoherenceManager(image_generator=...) "
                "or manager.image_generator = ...) that takes an enhanced prompt, "
                "renders the image, writes it to disk and returns its path. "
                "Use build_coherent_prompt() if you only need the enhanced prompt."
            )

        self.logger.info(f"Generating consistent image for {len(characters)} characters")

        # Build enhanced prompt with consistency requirements
        enhanced_prompt = await self.build_coherent_prompt(prompt, characters, episode_context)

        # Attempt generation with retry mechanism
        for attempt in range(max_attempts):
            self.logger.debug(f"Generation attempt {attempt + 1}/{max_attempts}")

            # Generate image using AI
            image_result = await self._generate_with_ai(enhanced_prompt)

            # Evaluate visual consistency
            consistency_metrics = await self._evaluate_visual_consistency(
                image_result, episode_context, characters
            )

            self.logger.debug(
                f"Consistency score: {consistency_metrics.overall_score:.3f} "
                f"(threshold: {self.consistency_threshold})"
            )

            # Check if consistency meets threshold
            if consistency_metrics.overall_score >= self.consistency_threshold:
                # Update reference data for future consistency checks
                await self._update_reference_data(image_result, characters, episode_context)
                self.logger.info(f"Generated consistent image on attempt {attempt + 1}")
                return image_result

            elif attempt < max_attempts - 1:
                # Enhance prompt for next attempt based on consistency issues
                enhanced_prompt = self._enhance_prompt_for_consistency(
                    enhanced_prompt, consistency_metrics
                )
                self.logger.info(
                    f"Retrying generation (attempt {attempt + 2}/{max_attempts}) "
                    f"due to low consistency: {consistency_metrics.overall_score:.3f}"
                )

        # Max attempts reached - log warning and return best result
        self.logger.warning(
            f"Could not achieve desired visual consistency "
            f"(score: {consistency_metrics.overall_score:.3f}, "
            f"threshold: {self.consistency_threshold:.3f}) after {max_attempts} attempts"
        )
        return image_result

    async def build_coherent_prompt(
        self, prompt: str, characters: list[str], episode_context: dict[str, Any]
    ) -> str:
        """
        Build a coherence-enhanced image prompt from scene, characters and style.

        This is the generator-independent half of the subsystem: it combines the
        episode style, the known character references and the scene description
        into a single prompt. Useful on its own for pipelines that hand prompts
        to an external image generator.

        Args:
            prompt: Base scene description
            characters: Characters present in the scene
            episode_context: Episode context with style/theme information

        Returns:
            Enhanced prompt carrying style and character consistency instructions
        """
        style_prompt = self._build_style_prompt(episode_context)
        character_prompt = await self._build_character_consistency_prompt(characters)

        return self._create_enhanced_prompt(style_prompt, character_prompt, prompt, episode_context)

    async def _evaluate_visual_consistency(
        self, image_path: str, episode_context: dict[str, Any], characters: list[str]
    ) -> VisualConsistencyMetrics:
        """
        Evaluate visual consistency using OpenCV and computer vision.

        Args:
            image_path: Path to generated image
            episode_context: Episode context with style and color data
            characters: Characters present in the image

        Returns:
            VisualConsistencyMetrics with detailed scoring

        Raises:
            ValueError: If image cannot be loaded
        """
        # Load current image using OpenCV
        current_image = cv2.imread(image_path)
        if current_image is None:
            raise ValueError(f"Could not load image: {image_path}")

        # Calculate individual consistency components
        color_score = await self._calculate_color_coherence(
            current_image, episode_context.get("episode_id")
        )

        style_score = await self._calculate_style_consistency(current_image, episode_context)

        character_score = await self._calculate_character_similarity(current_image, characters)

        # Calculate weighted overall score (style weighted highest)
        overall_score = (color_score * 0.3) + (style_score * 0.4) + (character_score * 0.3)

        return VisualConsistencyMetrics(
            color_coherence_score=color_score,
            style_consistency_score=style_score,
            character_similarity_score=character_score,
            overall_score=overall_score,
        )

    async def _calculate_color_coherence(self, image: np.ndarray, episode_id: str) -> float:
        """
        Calculate color palette coherence using OpenCV k-means clustering.

        Args:
            image: OpenCV image array (BGR format)
            episode_id: Episode identifier for palette storage

        Returns:
            Color coherence score (0.0-1.0)
        """
        try:
            # Extract dominant colors using k-means clustering
            pixels = image.reshape(-1, 3).astype(np.float32)
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)

            # Perform k-means clustering to find 5 dominant colors
            _, _, centers = cv2.kmeans(pixels, 5, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)

            dominant_colors = centers.astype(int).tolist()

            # Compare with existing episode color palette
            if episode_id in self.episode_color_palettes:
                episode_palette = self.episode_color_palettes[episode_id]
                coherence_score = self._compare_color_palettes(dominant_colors, episode_palette)
                self.logger.debug(f"Color coherence for {episode_id}: {coherence_score:.3f}")
                return coherence_score
            else:
                # First image - establish color palette for episode
                self.episode_color_palettes[episode_id] = dominant_colors
                self.logger.debug(f"Established color palette for {episode_id}")
                return 1.0

        except Exception as e:
            self.logger.error(f"Error calculating color coherence: {e}")
            return 0.5  # Fallback score

    async def _calculate_style_consistency(
        self, image: np.ndarray, episode_context: dict[str, Any]
    ) -> float:
        """
        Calculate style consistency using feature comparison.

        Args:
            image: OpenCV image array
            episode_context: Episode context with style information

        Returns:
            Style consistency score (0.0-1.0)
        """
        episode_id = episode_context.get("episode_id")

        try:
            # Extract style features (simplified - using edge detection and texture)
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # Edge density as style feature
            edges = cv2.Canny(gray, 50, 150)
            edge_density = np.sum(edges > 0) / edges.size

            # Texture features using local binary patterns (simplified)
            texture_variance = np.var(gray)

            current_style_features = {
                "edge_density": edge_density,
                "texture_variance": float(texture_variance),
                "mean_brightness": float(np.mean(gray)),
                "contrast": float(np.std(gray)),
            }

            # Compare with stored style template
            if episode_id in self.style_templates:
                stored_features = self.style_templates[episode_id]
                similarity = self._compare_style_features(current_style_features, stored_features)
                self.logger.debug(f"Style consistency for {episode_id}: {similarity:.3f}")
                return similarity
            else:
                # First image - establish style template
                self.style_templates[episode_id] = current_style_features
                self.logger.debug(f"Established style template for {episode_id}")
                return 1.0

        except Exception as e:
            self.logger.error(f"Error calculating style consistency: {e}")
            return 0.5  # Fallback score

    async def _calculate_character_similarity(
        self, image: np.ndarray, characters: list[str]
    ) -> float:
        """
        Calculate character appearance similarity with reference images.

        Args:
            image: OpenCV image array
            characters: List of characters in the image

        Returns:
            Character similarity score (0.0-1.0)
        """
        if not characters:
            return 1.0  # No characters to compare

        try:
            similarities = []

            for character in characters:
                if character in self.character_references:
                    # Compare with stored character reference
                    ref_image = self.character_references[character]
                    similarity = self._compare_character_features(image, ref_image)
                    similarities.append(similarity)
                    self.logger.debug(f"Character similarity for {character}: {similarity:.3f}")
                else:
                    # No reference - store current image as reference
                    self.character_references[character] = image.copy()
                    similarities.append(1.0)  # Perfect score for first appearance
                    self.logger.debug(f"Stored reference for {character}")

            # Return average similarity across all characters
            avg_similarity = sum(similarities) / len(similarities)
            return avg_similarity

        except Exception as e:
            self.logger.error(f"Error calculating character similarity: {e}")
            return 0.5  # Fallback score

    def _compare_color_palettes(
        self, palette_1: list[list[int]], palette_2: list[list[int]]
    ) -> float:
        """
        Compare two color palettes for similarity.

        Args:
            palette_1: First color palette as list of RGB values
            palette_2: Second color palette as list of RGB values

        Returns:
            Similarity score (0.0-1.0) based on color distance
        """
        try:
            # Convert to numpy arrays for vectorized operations
            p1 = np.array(palette_1)
            p2 = np.array(palette_2)

            # Calculate bidirectional similarity for better accuracy
            similarities_1to2 = []
            similarities_2to1 = []

            # Palette 1 to Palette 2
            for color1 in p1:
                distances = np.sqrt(np.sum((p2 - color1) ** 2, axis=1))
                min_distance = np.min(distances)
                # More strict similarity calculation
                similarity = max(0.0, 1.0 - (min_distance / (255 * np.sqrt(3))))
                # Apply stricter threshold for similar colors
                similarity = similarity**2  # Square to emphasize differences
                similarities_1to2.append(similarity)

            # Palette 2 to Palette 1 (bidirectional)
            for color2 in p2:
                distances = np.sqrt(np.sum((p1 - color2) ** 2, axis=1))
                min_distance = np.min(distances)
                similarity = max(0.0, 1.0 - (min_distance / (255 * np.sqrt(3))))
                similarity = similarity**2  # Square to emphasize differences
                similarities_2to1.append(similarity)

            # Return average of bidirectional similarities
            avg_sim_1to2 = sum(similarities_1to2) / len(similarities_1to2)
            avg_sim_2to1 = sum(similarities_2to1) / len(similarities_2to1)
            return (avg_sim_1to2 + avg_sim_2to1) / 2.0

        except Exception as e:
            self.logger.error(f"Error comparing color palettes: {e}")
            return 0.0

    def _compare_style_features(
        self, features_1: dict[str, float], features_2: dict[str, float]
    ) -> float:
        """
        Compare style features for consistency.

        Args:
            features_1: First set of style features
            features_2: Second set of style features

        Returns:
            Style similarity score (0.0-1.0)
        """
        try:
            similarities = []

            for feature_name in features_1.keys():
                if feature_name in features_2:
                    val1 = features_1[feature_name]
                    val2 = features_2[feature_name]

                    # Normalize based on feature type
                    if feature_name == "edge_density":
                        # Edge density is 0-1 range
                        diff = abs(val1 - val2)
                        similarity = 1.0 - diff
                    elif feature_name == "texture_variance":
                        # Texture variance can be large - normalize differently
                        max_val = max(val1, val2, 1.0)
                        diff = abs(val1 - val2) / max_val
                        similarity = 1.0 - min(1.0, diff)
                    else:
                        # Brightness and contrast (0-255 range)
                        diff = abs(val1 - val2) / 255.0
                        similarity = 1.0 - min(1.0, diff)

                    similarities.append(max(0.0, similarity))

            return sum(similarities) / len(similarities) if similarities else 0.0

        except Exception as e:
            self.logger.error(f"Error comparing style features: {e}")
            return 0.0

    def _compare_character_features(self, image1: np.ndarray, image2: np.ndarray) -> float:
        """
        Compare character features between two images.

        Args:
            image1: First image array
            image2: Second image array (reference)

        Returns:
            Character similarity score (0.0-1.0)
        """
        try:
            # Resize images to same size for comparison
            size = (256, 256)
            img1_resized = cv2.resize(image1, size)
            img2_resized = cv2.resize(image2, size)

            # Convert to grayscale for feature extraction
            gray1 = cv2.cvtColor(img1_resized, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(img2_resized, cv2.COLOR_BGR2GRAY)

            # Calculate histogram correlation
            hist1 = cv2.calcHist([gray1], [0], None, [256], [0, 256])
            hist2 = cv2.calcHist([gray2], [0], None, [256], [0, 256])
            correlation = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)

            # Calculate structural similarity (simplified)
            # Using mean squared error as inverse similarity measure
            mse = np.mean((gray1.astype(float) - gray2.astype(float)) ** 2)
            structural_sim = 1.0 / (1.0 + mse / 1000.0)  # Normalize MSE

            # Combine metrics
            similarity = (correlation * 0.6) + (structural_sim * 0.4)
            return max(0.0, min(1.0, similarity))

        except Exception as e:
            self.logger.error(f"Error comparing character features: {e}")
            return 0.0

    def _build_style_prompt(self, episode_context: dict[str, Any]) -> str:
        """
        Build style consistency prompt from episode context.

        Args:
            episode_context: Episode context with style information

        Returns:
            Style prompt for consistent generation
        """
        visual_style = episode_context.get("visual_style", "anime")
        theme = episode_context.get("theme", "")

        style_prompt = f"Create in consistent {visual_style} art style"
        if theme:
            style_prompt += f" with {theme} theme"

        return style_prompt

    async def _build_character_consistency_prompt(self, characters: list[str]) -> str:
        """
        Build character consistency prompt based on reference data.

        Args:
            characters: Characters present in the scene

        Returns:
            Character consistency prompt
        """
        if not characters:
            return ""

        char_descriptions = []
        for character in characters:
            if character in self.character_references:
                char_descriptions.append(f"{character} with consistent appearance")
            else:
                char_descriptions.append(f"{character}")

        return f"Characters: {', '.join(char_descriptions)}"

    def _create_enhanced_prompt(
        self,
        style_prompt: str,
        character_prompt: str,
        scene_prompt: str,
        episode_context: dict[str, Any],
    ) -> str:
        """
        Create comprehensive enhanced prompt for generation.

        Args:
            style_prompt: Style consistency instructions
            character_prompt: Character consistency instructions
            scene_prompt: Original scene description
            episode_context: Episode context for additional enhancement

        Returns:
            Comprehensive enhanced prompt
        """
        enhanced_parts = [scene_prompt]

        if character_prompt:
            enhanced_parts.append(character_prompt)

        if style_prompt:
            enhanced_parts.append(style_prompt)

        # Add visual consistency requirements
        enhanced_parts.append("Maintain visual consistency and coherent art style")

        return ". ".join(enhanced_parts)

    def _enhance_prompt_for_consistency(
        self, original_prompt: str, consistency_metrics: VisualConsistencyMetrics
    ) -> str:
        """
        Enhance prompt based on consistency weaknesses.

        Args:
            original_prompt: Current prompt that produced low consistency
            consistency_metrics: Metrics showing consistency issues

        Returns:
            Enhanced prompt targeting specific consistency problems
        """
        enhancements = []

        # Address specific consistency issues
        if consistency_metrics.color_coherence_score < 0.6:
            enhancements.append("maintain consistent color palette and harmony")

        if consistency_metrics.style_consistency_score < 0.6:
            enhancements.append("preserve consistent art style and visual approach")

        if consistency_metrics.character_similarity_score < 0.6:
            enhancements.append("ensure character appearance consistency and recognition")

        # Combine original prompt with enhancements
        if enhancements:
            enhancement_text = ", ".join(enhancements)
            enhanced_prompt = f"{original_prompt}. Focus on: {enhancement_text}"
        else:
            enhanced_prompt = f"{original_prompt}. Improve overall visual consistency"

        return enhanced_prompt

    async def _generate_with_ai(self, enhanced_prompt: str) -> str:
        """
        Generate an image by delegating to the injected image generator.

        Args:
            enhanced_prompt: Enhanced prompt for generation

        Returns:
            Path to the generated image file, as reported by the generator

        Raises:
            NotImplementedError: If no image generator was injected.
            ValueError: If the generator did not return a usable path.
        """
        if self.image_generator is None:
            raise NotImplementedError(
                "No image generator injected into VisualCoherenceManager. "
                "Real integration requires a callable that renders the prompt to "
                "an image file on disk and returns its path, so that the OpenCV "
                "consistency scoring below has something to read."
            )

        result = self.image_generator(enhanced_prompt)
        if inspect.isawaitable(result):
            result = await result

        if not isinstance(result, str) or not result:
            raise ValueError(
                f"Image generator must return a path to a generated image file, got {result!r}"
            )

        return result

    async def _update_reference_data(
        self, image_path: str, characters: list[str], episode_context: dict[str, Any]
    ) -> None:
        """
        Update reference data with successful generation.

        Args:
            image_path: Path to successfully generated image
            characters: Characters in the image
            episode_context: Episode context for data organization

        Raises:
            ValueError: If the image cannot be read. The reference data drives
                every later consistency score, so a silent no-op here would leave
                the feedback loop permanently inert.
        """
        # Load the successful image
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Could not load image for reference update: {image_path}")

        # Update character references
        for character in characters:
            self.character_references[character] = image.copy()
            self.logger.debug(f"Updated reference for character: {character}")

        # Note: Color palette and style template are updated during calculation
        # to avoid redundant processing
