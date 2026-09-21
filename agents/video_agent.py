"""
Agent for video generation tasks including image generation and timing calculations.
"""

import logging
import os
from typing import Any

# google-genai is an *optional* dependency of this module, and always was in
# substance: `generate_optimized_images` builds prompt strings and
# `adaptive_duration_calculation` is arithmetic over word counts. Neither
# touches the package. The only thing that ever did was the Gemini client
# below, and an unguarded module-scope import of it made the whole agent - and,
# through `agents/workflow_orchestrator.py`, the whole pipeline - unimportable
# on a machine without the package, which is the opposite of optional.
# `media/media_utils.py` (f2597bf) and `agents/character_analysis_agent.py`
# (b6fde06) already take this shape: a guarded import, a module-level flag, and
# a failure raised where the package is actually used.
try:
    from google import genai

    GENAI_AVAILABLE = True
except ImportError as exc:  # pragma: no cover - exercised by a subprocess test
    genai = None  # type: ignore[assignment]
    _GENAI_IMPORT_ERROR: str | None = str(exc) or "google-genai is not installed"
    GENAI_AVAILABLE = False
else:
    _GENAI_IMPORT_ERROR = None

logger = logging.getLogger(__name__)


class GeminiClientUnavailable(RuntimeError):
    """
    No Gemini client could be built, and the message says why.

    Raised at the point of use rather than at import time, so that an install
    without google-genai still gets a usable ``VideoGenerationAgent`` - the
    prompt and timing methods need nothing from the package - and only a caller
    that actually reaches for the client is told what to install. The parallel
    is ``media.media_utils.ImageGeneratorUnavailable``.
    """


class VideoGenerationAgent:
    """
    Agent responsible for tasks related to video generation.

    This agent handles image generation, duration calculations, and video composition.
    It coordinates with AI image generation models to create visual content that
    matches the episode's plot points and maintains visual consistency.
    """

    def __init__(self):
        """
        Initialize the VideoGenerationAgent.

        Attempts to set up the Gemini AI client, but never depends on it:
        construction succeeds with ``self.client = None`` whatever goes wrong,
        including google-genai not being installed at all. The two methods this
        class exposes do not use the client, so an agent without one is fully
        functional for everything the orchestrator asks of it.
        """
        # Attempted, not required. A caller that genuinely needs a client calls
        # build_client() and gets an exception naming the reason; here the
        # reason is logged and the agent carries on without one.
        self.client: Any | None = None
        try:
            self.client = self.build_client()
        except Exception as e:
            logger.warning(f"Failed to initialize Gemini client: {e}")
            self.client = None

    def build_client(self) -> Any:
        """
        Build the Gemini client, or explain why it cannot be built.

        This is the only part of this class that needs google-genai. It is a
        method rather than inline constructor code so that the missing-package
        failure has somewhere to be raised *at the point of use*, with a message
        naming the package and how to install it.

        Returns:
            Any: A configured Gemini model client.

        Raises:
            GeminiClientUnavailable: google-genai is not installed.
        """
        if genai is None:
            raise GeminiClientUnavailable(
                f"google-genai is not installed ({_GENAI_IMPORT_ERROR}). "
                "Install it with: pip install google-genai"
            )

        # NOTE: `configure`/`GenerativeModel` belong to the older
        # `google-generativeai` package; the pinned `google-genai` exposes
        # `genai.Client` instead, so this call raises AttributeError even when
        # the package *is* installed and __init__ has always ended up with
        # `self.client is None`. Left as-is deliberately: nothing reads
        # `self.client`, and changing it would start constructing a real client
        # on every pipeline run. Fixing it is a separate change.
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY", ""))
        return genai.GenerativeModel("gemini-pro")

    def generate_optimized_images(
        self, plot_points: list[str], episode_context: dict[str, Any]
    ) -> list[str]:
        """
        Create enhanced prompts for generating images with a consistent visual style.

        This method takes raw plot points and enhances them with style instructions
        to ensure visual consistency across all generated images in the video.

        Args:
            plot_points (List[str]): A list of sentences describing key scenes/moments
            episode_context (Dict[str, Any]): Context about the episode including show title, season, etc.

        Returns:
            List[str]: Enhanced prompts optimized for AI image generation with consistent styling
        """
        # Define the base style prompt for visual consistency
        # This ensures all images have a cohesive anime art style
        style_prompt = f"""
        Create images in a consistent anime art style for {episode_context.get("show", "anime series")}.
        Use vibrant colors, dynamic compositions, and maintain visual continuity.
        Style: Modern anime, high quality, detailed backgrounds.
        """

        enhanced_prompts = []
        # Process each plot point to create a styled image generation prompt
        for point in plot_points:
            # Combine the consistent style instructions with the specific scene description
            enhanced_prompt = f"{style_prompt}\n\nScene: {point}"
            enhanced_prompts.append(enhanced_prompt)

        return enhanced_prompts

    def adaptive_duration_calculation(
        self, sentences: list[str], total_duration: float
    ) -> list[float]:
        """
        Calculate the display duration for each image based on sentence length.

        This creates a proportional timing system where longer descriptions get more screen time.

        Args:
            sentences (List[str]): The list of sentences (plot points) to calculate timing for
            total_duration (float): The total duration of the audio track in seconds

        Returns:
            List[float]: A list of durations (in seconds) for each image, proportional to sentence length
        """
        # Count words in each sentence to determine relative complexity/length
        word_counts = [len(sentence.split()) for sentence in sentences]
        total_words = sum(word_counts)

        durations = []
        for word_count in word_counts:
            # Calculate duration based on the proportional word count
            # Longer sentences get more time on screen for better pacing
            ratio = word_count / total_words if total_words > 0 else 0
            duration = total_duration * ratio
            # Ensure a minimum duration of 2 seconds for readability
            # Even short sentences need enough time to be processed visually
            durations.append(max(duration, 2.0))

        return durations
