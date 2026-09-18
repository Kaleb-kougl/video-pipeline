#!/usr/bin/env python3
"""
Test suite for multi-format video export functionality.
Following TDD - these tests should FAIL initially.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from media.format_exporters import (  # NEW MODULES
    YouTubeShortsExporter,
    TikTokExporter, 
    InstagramReelsExporter,
    TwitterVideoExporter
)
from core.schemas import ExportFormat, VideoSpec

class TestExportFormats:
    """Test suite for multi-format video export functionality.
    
    This class validates the system's ability to export videos in different
    formats optimized for various social media platforms, each with specific
    duration, aspect ratio, and quality constraints.
    """
    
    @pytest.fixture
    def sample_video_content(self):
        """Sample video content for export testing."""
        return {
            "show_name": "My Hero Academia",
            "season": 1,
            "visual_concepts": [
                {"text": "Concept 1", "image_path": "img1.png"},
                {"text": "Concept 2", "image_path": "img2.png"}
            ],
            "audio_file": "narration.wav",
            "total_duration": 300  # 5 minutes
        }
    
    @pytest.mark.parametrize("format_type,expected_duration,expected_aspect", [
        ("youtube_shorts", 60, "9:16"),    # 60 seconds max, vertical
        ("tiktok", 60, "9:16"),           # 60 seconds max, vertical  
        ("instagram_reels", 90, "9:16"),   # 90 seconds max, vertical
        ("twitter", 140, "16:9"),         # 140 seconds max, horizontal
    ])
    def test_format_specific_constraints(self, format_type, expected_duration, expected_aspect):
        """Test format-specific duration and aspect ratio constraints.
        
        Validates that each export format correctly enforces platform-specific
        limitations on video duration and aspect ratio to ensure compatibility.
        
        Args:
            format_type (str): Target export format identifier
            expected_duration (int): Expected maximum duration in seconds
            expected_aspect (str): Expected aspect ratio string
        """
        exporter = self._get_exporter(format_type)
        
        constraints = exporter.get_format_constraints()
        
        assert constraints['max_duration'] == expected_duration
        assert constraints['aspect_ratio'] == expected_aspect
    
    def test_youtube_shorts_export(self, sample_video_content):
        """Test YouTube Shorts export with vertical format and 60s limit."""
        exporter = YouTubeShortsExporter()
        
        result = exporter.export_video(sample_video_content)
        
        # Should create vertical video under 60 seconds
        assert result['success'] == True
        assert result['duration'] <= 60
        assert result['aspect_ratio'] == "9:16"
        assert result['output_path'].endswith('_youtube_shorts.mp4')
    
    def test_content_adaptation_for_short_format(self, sample_video_content):
        """Test content adaptation for shorter video formats."""
        exporter = TikTokExporter()
        
        # Original content is 5 minutes, should be condensed for TikTok
        adapted_content = exporter.adapt_content_for_format(sample_video_content)
        
        # Should condense content
        assert len(adapted_content['visual_concepts']) <= 4  # Fewer concepts
        assert adapted_content['estimated_duration'] <= 60  # Under 60 seconds
        assert 'hook_enhanced' in adapted_content  # Enhanced opening hook
    
    def test_platform_specific_optimization(self):
        """Test platform-specific content optimization."""
        exporters = [
            YouTubeShortsExporter(),
            TikTokExporter(),
            InstagramReelsExporter()
        ]
        
        for exporter in exporters:
            optimization = exporter.get_platform_optimization_rules()
            
            # Each platform should have specific rules
            assert 'content_style' in optimization
            assert 'pacing_preferences' in optimization  
            assert 'hook_strategies' in optimization
    
    def _get_exporter(self, format_type: str):
        """Helper to get appropriate exporter for format type."""
        exporters = {
            "youtube_shorts": YouTubeShortsExporter(),
            "tiktok": TikTokExporter(),
            "instagram_reels": InstagramReelsExporter(),
            "twitter": TwitterVideoExporter()
        }
        return exporters[format_type]
