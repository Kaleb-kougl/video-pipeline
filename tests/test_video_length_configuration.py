#!/usr/bin/env python3
"""
Test suite for video length configuration functionality.

Uses pytest with advanced fixtures and parametrization for comprehensive testing.

These tests exercise pure timing arithmetic and prompt construction, neither of
which involves embeddings. They used to call ``AnimeVideoGenerator()`` bare,
which builds the optional ``CharacterAnalysisAgent`` and therefore downloads the
``all-MiniLM-L6-v2`` sentence-transformers model. That passed only on a machine
whose ``~/.cache/huggingface`` already held the model; on a clean runner it
raised ``OSError: We couldn't connect to 'https://huggingface.co'``. The
``generator`` fixture below replaces the three boundaries that want a key, a
vector store or the network, exactly as ``tests/unit/test_main_composition.py``
does, so the real constructor and the real settings are still under test.
"""

from unittest.mock import patch

import pytest

from config.settings import get_settings


class FakeVectorSearchManager:
    """Stand-in for the optional vector search backend."""


class FakeCharacterAgent:
    """Stand-in for the ChromaDB/sentence-transformers character analysis agent."""


@pytest.fixture
def generator(tmp_path, fake_chat_model):
    """A real ``AnimeVideoGenerator`` confined to ``tmp_path``, with no downloads."""
    import main

    settings = get_settings().model_copy(
        update={
            "database_path": str(tmp_path / "video_generator.db"),
            "output_directory": str(tmp_path / "output"),
        }
    )

    with (
        patch("main.get_settings", return_value=settings),
        patch("langchain.chat_models.init_chat_model", return_value=fake_chat_model),
        patch("main.CharacterAnalysisAgent", return_value=FakeCharacterAgent()),
        patch("main.VectorSearchManager", return_value=FakeVectorSearchManager()),
    ):
        return main.AnimeVideoGenerator()


class TestVideoLengthConfiguration:
    """Test suite for video length configuration functionality.

    This class contains comprehensive tests for video duration settings,
    scaling behavior, and constraint validation to ensure videos are
    generated with appropriate lengths for different target audiences.
    """

    def test_default_video_length_is_5_minutes(self, generator):
        """Test that default video length remains 5 minutes for backward compatibility.

        Validates that when no explicit duration is specified, the system defaults
        to generating 5-minute videos to maintain consistency with existing behavior.
        """
        config = generator._calculate_video_structure()
        assert config["total_duration"] == 300  # 5 minutes in seconds

    def test_minimum_video_length_5_minutes(self, generator):
        """Test that minimum video length is enforced at 5 minutes.

        Validates that the system prevents creation of videos shorter than 5 minutes
        to ensure sufficient content depth and viewer engagement.
        """
        config = generator._calculate_video_structure(target_minutes=3)
        assert config["total_duration"] >= 300

    def test_maximum_video_length_15_minutes(self, generator):
        """Test that maximum video length is enforced at 15 minutes."""
        config = generator._calculate_video_structure(target_minutes=20)
        assert config["total_duration"] <= 900  # 15 minutes in seconds

    @pytest.mark.parametrize(
        "target_minutes,expected_total", [(5, 300), (7, 420), (10, 600), (12, 720), (15, 900)]
    )
    def test_video_structure_scaling(self, generator, target_minutes: int, expected_total: int):
        """Test video structure scales correctly with target duration."""
        config = generator._calculate_video_structure(target_minutes=target_minutes)

        # Validate total duration
        assert config["total_duration"] == expected_total

        # Validate proportional scaling (within 1 second tolerance for rounding)
        expected_ratios = {
            "opening_hook": 0.10,
            "character_arcs": 0.30,
            "plot_progression": 0.40,
            "relationship_evolution": 0.10,
            "climax_resolution": 0.10,
        }

        for section, expected_ratio in expected_ratios.items():
            expected_duration = expected_total * expected_ratio
            actual_duration = config[section]
            assert abs(actual_duration - expected_duration) <= 1, (
                f"{section} duration {actual_duration} not within 1s of expected {expected_duration}"
            )

    def test_visual_concept_duration_scales_with_video_length(self, generator):
        """Test that visual concept duration adapts to video length."""
        # 5-minute video should have 5-second concepts
        short_config = generator._calculate_visual_timing(target_minutes=5, concept_count=6)
        assert short_config["concept_duration"] == 5.0

        # 10-minute video should have ~10-second concepts
        long_config = generator._calculate_visual_timing(target_minutes=10, concept_count=6)
        assert short_config["concept_duration"] < long_config["concept_duration"]

    def test_content_prompt_adapts_to_video_length(self, generator):
        """Test that AI content generation prompt adapts to target length."""
        short_prompt = generator._generate_length_adaptive_prompt("Test Show", 1, {}, 5)
        long_prompt = generator._generate_length_adaptive_prompt("Test Show", 1, {}, 12)

        # Longer videos should have more detailed prompts
        assert len(long_prompt) > len(short_prompt)
        assert "detailed analysis" in long_prompt
        assert "comprehensive exploration" in long_prompt
