#!/usr/bin/env python3
"""
Instagram Reels video exporter.
Handles vertical format (9:16) videos with 90-second maximum duration.
"""

import logging
from typing import Dict, List, Any

from .base_exporter import BaseExporter

logger = logging.getLogger(__name__)

class InstagramReelsExporter(BaseExporter):
    """
    Exporter for Instagram Reels format videos.
    
    Handles vertical format (9:16) videos optimized for Instagram's aesthetic-focused
    platform with 90-second maximum duration and visual consistency emphasis.
    """
    
    def __init__(self):
        """
        Initialize Instagram Reels exporter.
        
        Sets up Instagram Reels-specific configuration for vertical video format
        with aesthetic optimization and brand consistency features.
        """
        super().__init__()
        
    def get_format_constraints(self) -> Dict[str, Any]:
        """Get Instagram Reels format constraints."""
        return {
            'max_duration': 90,  # 90 seconds maximum
            'aspect_ratio': '9:16',  # Vertical format
            'min_resolution': (1080, 1920),  # Minimum HD vertical
            'max_file_size': 50 * 1024 * 1024,  # 50MB max
        }
        
    def export_video(self, video_content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Export video in Instagram Reels format.

        Raises:
            NotImplementedError: Always. Rendering the video file is not
                implemented; only the content adaptation below is real.
        """
        constraints = self.get_format_constraints()

        adapted_content = self.adapt_content_for_format(video_content)

        show_name = video_content.get('show_name', 'Unknown')
        season = video_content.get('season', 1)

        safe_show = show_name.replace(' ', '_').replace('/', '_')
        output_filename = f"{safe_show}_S{season}_instagram_reels.mp4"

        raise NotImplementedError(
            f"Instagram Reels video export is not implemented: no file was written for "
            f"'{output_filename}'. Producing it requires a MoviePy re-render of the source "
            f"clips at a {constraints['aspect_ratio']} aspect ratio "
            f"({constraints['min_resolution'][0]}x{constraints['min_resolution'][1]}), the "
            f"timeline capped at {constraints['max_duration']}s (adapted duration would be "
            f"{adapted_content['estimated_duration']}s), and an ffmpeg encode kept under the "
            f"{constraints['max_file_size'] // (1024 * 1024)}MB limit. "
            f"Content adaptation succeeded; only the render step is missing."
        )
            
    def adapt_content_for_format(self, video_content: Dict[str, Any]) -> Dict[str, Any]:
        """Adapt content for Instagram Reels requirements."""
        original_duration = video_content.get('total_duration', 300)
        max_duration = self.get_format_constraints()['max_duration']
        
        adapted_duration = self._calculate_adapted_duration(original_duration, max_duration)
        
        visual_concepts = video_content.get('visual_concepts', [])
        max_concepts = 4  # Keep it concise
        condensed_concepts = visual_concepts[:max_concepts]
        
        enhanced_concepts = self._enhance_hook(condensed_concepts)
        
        adapted = {
            'show_name': video_content.get('show_name'),
            'season': video_content.get('season'),
            'visual_concepts': enhanced_concepts,
            'audio_file': video_content.get('audio_file'),
            'estimated_duration': adapted_duration,
            'hook_enhanced': True,
            'format_optimized': 'instagram_reels'
        }
        
        return adapted
        
    def get_platform_optimization_rules(self) -> Dict[str, Any]:
        """Get Instagram Reels platform optimization rules."""
        return {
            'content_style': 'aesthetic_focused',
            'pacing_preferences': 'medium_fast',
            'hook_strategies': [
                'visual_aesthetics',
                'story_arcs',
                'music_sync',
                'brand_consistency'
            ],
            'engagement_tactics': [
                'story_features',
                'hashtag_optimization',
                'cross_posting'
            ]
        }
