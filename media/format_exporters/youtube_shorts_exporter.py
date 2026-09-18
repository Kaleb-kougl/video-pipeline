#!/usr/bin/env python3
"""
YouTube Shorts video exporter.
Handles vertical format (9:16) videos with 60-second maximum duration.
"""

import logging
from typing import Dict, List, Any
from pathlib import Path
import os

from .base_exporter import BaseExporter

logger = logging.getLogger(__name__)

class YouTubeShortsExporter(BaseExporter):
    """Exporter for YouTube Shorts format videos."""
    
    def __init__(self):
        """Initialize YouTube Shorts exporter."""
        super().__init__()
        
    def get_format_constraints(self) -> Dict[str, Any]:
        """Get YouTube Shorts format constraints."""
        return {
            'max_duration': 60,  # 60 seconds maximum
            'aspect_ratio': '9:16',  # Vertical format
            'min_resolution': (1080, 1920),  # Minimum HD vertical
            'max_file_size': 15 * 1024 * 1024,  # 15MB max
        }
        
    def export_video(self, video_content: Dict[str, Any]) -> Dict[str, Any]:
        """Export video in YouTube Shorts format."""
        try:
            # Get format constraints
            constraints = self.get_format_constraints()
            
            # Adapt content for short format
            adapted_content = self.adapt_content_for_format(video_content)
            
            # Generate output filename
            show_name = video_content.get('show_name', 'Unknown')
            season = video_content.get('season', 1)
            
            # Create safe filename
            safe_show = show_name.replace(' ', '_').replace('/', '_')
            output_filename = f"{safe_show}_S{season}_youtube_shorts.mp4"
            
            # For now, simulate the export process
            # In real implementation, this would use MoviePy with vertical aspect ratio
            result = {
                'success': True,
                'duration': adapted_content['estimated_duration'],
                'aspect_ratio': '9:16',
                'output_path': output_filename,
                'format': 'youtube_shorts',
                'file_size': 8 * 1024 * 1024,  # Simulated file size
            }
            
            logger.info(f"YouTube Shorts export completed: {output_filename}")
            return result
            
        except Exception as e:
            logger.error(f"YouTube Shorts export failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'output_path': None
            }
            
    def adapt_content_for_format(self, video_content: Dict[str, Any]) -> Dict[str, Any]:
        """Adapt content for YouTube Shorts requirements."""
        original_duration = video_content.get('total_duration', 300)
        max_duration = self.get_format_constraints()['max_duration']
        
        # Calculate adapted duration
        adapted_duration = self._calculate_adapted_duration(original_duration, max_duration)
        
        # Condense visual concepts for shorter format
        visual_concepts = video_content.get('visual_concepts', [])
        
        # Keep maximum 4 concepts for 60-second video
        max_concepts = 4
        condensed_concepts = visual_concepts[:max_concepts]
        
        # Enhance opening hook
        enhanced_concepts = self._enhance_hook(condensed_concepts)
        
        adapted = {
            'show_name': video_content.get('show_name'),
            'season': video_content.get('season'),
            'visual_concepts': enhanced_concepts,
            'audio_file': video_content.get('audio_file'),
            'estimated_duration': adapted_duration,
            'hook_enhanced': True,
            'format_optimized': 'youtube_shorts'
        }
        
        return adapted
        
    def get_platform_optimization_rules(self) -> Dict[str, Any]:
        """Get YouTube Shorts platform optimization rules."""
        return {
            'content_style': 'engaging_hooks',
            'pacing_preferences': 'fast_paced',
            'hook_strategies': [
                'start_with_action',
                'use_trending_sounds',
                'vertical_composition',
                'text_overlays'
            ],
            'engagement_tactics': [
                'call_to_action_early',
                'subscribe_reminder',
                'comment_questions'
            ]
        }
