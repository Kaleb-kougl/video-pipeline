"""
Agent for video generation tasks including image generation and timing calculations.
"""

import os
import logging
from typing import List, Dict, Any
from google import genai

logger = logging.getLogger(__name__)


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
        
        Sets up the Gemini AI client for image generation capabilities.
        """
        # Initialize Gemini client for AI image generation
        try:
            genai.configure(api_key=os.getenv('GOOGLE_API_KEY', ''))
            self.client = genai.GenerativeModel('gemini-pro')
        except Exception as e:
            logger.warning(f"Failed to initialize Gemini client: {e}")
            self.client = None
    
    def generate_optimized_images(self, plot_points: List[str], episode_context: Dict[str, Any]) -> List[str]:
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
        Create images in a consistent anime art style for {episode_context.get('show', 'anime series')}.
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
    
    def adaptive_duration_calculation(self, sentences: List[str], total_duration: float) -> List[float]:
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
