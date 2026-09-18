#!/usr/bin/env python3
"""
Base exporter class for platform-specific video formats.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class BaseExporter(ABC):
    """
    Abstract base class for video format exporters.

    Defines the interface for platform-specific video exporters that
    adapt content for different social media platforms and formats.
    """

    def __init__(self):
        """
        Initialize the base exporter.

        Sets up the platform name based on the class name for identification.
        """
        self.platform_name = self.__class__.__name__.replace("Exporter", "").lower()

    @abstractmethod
    def get_format_constraints(self) -> dict[str, Any]:
        """
        Get platform-specific format constraints.

        Returns:
            Dictionary containing format constraints like max duration,
            aspect ratio, resolution, and file size limits
        """
        pass

    @abstractmethod
    def export_video(self, video_content: dict[str, Any]) -> dict[str, Any]:
        """
        Export video in platform-specific format.

        Args:
            video_content: Dictionary containing video content and metadata

        Returns:
            Dictionary containing export results, file paths, and status information

        Raises:
            NotImplementedError: If the subclass can adapt the content but cannot
                actually render/write a video file. Callers must handle this and
                must not record a successful export.
        """
        pass

    @abstractmethod
    def adapt_content_for_format(self, video_content: dict[str, Any]) -> dict[str, Any]:
        """
        Adapt content for platform-specific requirements.

        Args:
            video_content: Original video content dictionary

        Returns:
            Adapted content dictionary optimized for the target platform
        """
        pass

    @abstractmethod
    def get_platform_optimization_rules(self) -> dict[str, Any]:
        """
        Get platform-specific optimization rules.

        Returns:
            Dictionary containing optimization strategies and engagement tactics
            specific to the platform
        """
        pass

    def _calculate_adapted_duration(self, original_duration: int, max_duration: int) -> int:
        """
        Calculate adapted duration for platform constraints.

        Args:
            original_duration: Original content duration in seconds
            max_duration: Maximum allowed duration for the platform

        Returns:
            Adapted duration that fits platform constraints
        """
        return min(original_duration, max_duration)

    def _enhance_hook(self, visual_concepts: list[dict]) -> list[dict]:
        """
        Enhance opening hook for short-form content.

        Args:
            visual_concepts: List of visual concept dictionaries

        Returns:
            Enhanced visual concepts with improved opening hook
        """
        if not visual_concepts:
            return visual_concepts

        # Move most engaging content to the beginning
        enhanced = visual_concepts.copy()
        if len(enhanced) > 1:
            # Simple enhancement: ensure first concept is engaging
            enhanced[0]["text"] = f"🔥 {enhanced[0]['text']}"

        return enhanced
