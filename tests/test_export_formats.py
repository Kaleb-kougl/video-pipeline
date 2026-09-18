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
    
    @pytest.mark.parametrize("format_type", [
        "youtube_shorts",
        "tiktok",
        "instagram_reels",
        "twitter",
    ])
    def test_export_video_is_not_implemented(self, format_type, sample_video_content):
        """Platform video export must fail loudly instead of faking success.

        No exporter actually renders or writes a video file, so export_video()
        must raise NotImplementedError rather than returning a success dict that
        would be persisted to the database as a real export.
        """
        exporter = self._get_exporter(format_type)

        with pytest.raises(NotImplementedError) as exc_info:
            exporter.export_video(sample_video_content)

        message = str(exc_info.value)
        assert 'not implemented' in message.lower()
        # The message should name what a real implementation would require.
        assert 'MoviePy' in message
        assert f'_{format_type}.mp4' in message

    def test_export_video_never_returns_a_result(self, sample_video_content):
        """export_video() must not return anything, even a failure dict.

        Guards against a regression where the raise is swallowed by a broad
        ``except Exception`` and turned back into a dict.
        """
        exporter = YouTubeShortsExporter()

        try:
            result = exporter.export_video(sample_video_content)
        except NotImplementedError:
            return

        pytest.fail(f"export_video() returned {result!r} instead of raising")


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
    
    @pytest.mark.parametrize("format_type", [
        "youtube_shorts",
        "tiktok",
        "instagram_reels",
        "twitter",
    ])
    def test_pipeline_caller_degrades_gracefully(self, format_type, sample_video_content):
        """The pipeline must absorb NotImplementedError, not crash and not lie.

        export_video_format() is the only caller of export_video(); it must
        return an honest failure marker so nothing resembling a successful
        export is written to the database.
        """
        from main_refactored import AnimeVideoGenerator

        generator = AnimeVideoGenerator()

        result = generator.export_video_format(
            sample_video_content['show_name'],
            sample_video_content['season'],
            sample_video_content['visual_concepts'],
            sample_video_content['audio_file'],
            format_type,
        )

        assert result['success'] is False
        assert result['status'] == 'skipped_not_implemented'
        assert result['output_path'] is None
        assert 'not implemented' in result['error'].lower()

    def _get_exporter(self, format_type: str):
        """Helper to get appropriate exporter for format type."""
        exporters = {
            "youtube_shorts": YouTubeShortsExporter(),
            "tiktok": TikTokExporter(),
            "instagram_reels": InstagramReelsExporter(),
            "twitter": TwitterVideoExporter()
        }
        return exporters[format_type]
