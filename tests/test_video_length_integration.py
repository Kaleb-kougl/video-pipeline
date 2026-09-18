#!/usr/bin/env python3
"""
Integration tests for video length configuration with the complete system.
Uses pytest fixtures for better test isolation and resource management.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import tempfile
from pathlib import Path
from typing import Dict, Any

from main import AnimeVideoGenerator
from core.schemas import ProcessingResult, VideoStructureConfig

# Live-network suite: these tests scrape Fandom/Google and hit real HTTP
# endpoints, so they are deselected by default (see the 'network' marker in
# pyproject.toml). Run them explicitly with: pytest -m network
pytestmark = pytest.mark.network

# Pytest fixtures for test setup
@pytest.fixture
def mock_generator():
    """Fixture providing a mocked AnimeVideoGenerator with dependencies.
    
    Creates a mock generator instance with all essential methods stubbed
    to enable testing without actual media generation dependencies.
    
    Returns:
        Mock: Configured mock AnimeVideoGenerator instance
    """
    with patch('main.AnimeVideoGenerator') as mock_gen:
        generator = Mock(spec=AnimeVideoGenerator)
        # Mock essential methods
        generator._calculate_video_structure = Mock()
        generator._calculate_visual_timing = Mock()
        generator._generate_season_summary = Mock()
        generator._create_voice_recording = Mock()
        generator._generate_season_images = Mock()
        generator.db = Mock()
        yield generator

@pytest.fixture
def temp_media_dir():
    """Fixture providing a temporary directory for media files.
    
    Creates a temporary directory structure for testing media file
    operations without affecting the actual file system.
    
    Returns:
        Path: Path to temporary media directory
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        media_path = Path(temp_dir) / "media"
        media_path.mkdir()
        yield media_path

class TestVideoLengthIntegration:
    """Integration test suite for video length configuration with the complete system.
    
    This class validates that video length settings work correctly when
    integrated with the complete video generation pipeline, including
    voice generation, image creation, and final video composition.
    """
    
    @patch('main.AnimeVideoGenerator._create_voice_recording')
    @patch('main.AnimeVideoGenerator._generate_season_images') 
    @pytest.mark.asyncio
    async def test_process_season_with_custom_length(self, mock_images, mock_voice):
        """Test complete season processing with custom video length.
        
        Validates that the complete video generation pipeline respects
        custom duration settings and produces videos with the correct length.
        
        Args:
            mock_images: Mock for image generation functionality
            mock_voice: Mock for voice recording functionality
        """
        generator = AnimeVideoGenerator()
        
        # Mock dependencies
        mock_voice.return_value = "test_audio.wav"
        
        # This should create an 8-minute video
        result = await generator.process_season("Test Show", 1, target_minutes=8)
        
        # Verify the result contains duration information
        assert result.success
        assert result.data['video_config']['total_duration'] == 480  # 8 minutes
        
    def test_cli_integration_with_duration_parameter(self):
        """Test CLI accepts and processes duration parameter."""
        # This test would verify the CLI argument parsing
        # Will be implemented after CLI changes
        pass
