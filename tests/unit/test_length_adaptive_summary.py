"""
Tests that the length-adaptive season summary actually honours target_minutes.

``_generate_season_summary_with_length`` used to build a length-adaptive prompt,
discard it, and delegate to ``_generate_season_summary``, which hard-codes a
5-minute structure. ``target_minutes`` therefore had no effect on the generated
summary at all.
"""

from unittest.mock import Mock

import pytest

from main import AnimeVideoGenerator


@pytest.fixture
def generator() -> AnimeVideoGenerator:
    return AnimeVideoGenerator()


SEASON_ANALYSIS = {
    "season_info": {"total_episodes": 12, "episode_range": "1-12"},
    "character_insights": {
        "total_characters": 3,
        "top_developing_characters": [("Tanjiro", 0.9), ("Nezuko", 0.7)],
    },
    "story_insights": {
        "pivotal_moments_count": 5,
        "dominant_themes": [("perseverance", 0.8), ("family", 0.6)],
        "narrative_arcs": 2,
    },
    "relationship_insights": {"strongest_relationships": [("Tanjiro-Nezuko", 0.95)]},
    "episode_analysis": {"most_significant_episodes": [("S1E11", 0.9)]},
}


class TestLengthAdaptivePromptIsUsed:
    def test_summary_generation_uses_the_length_adaptive_prompt(self, generator):
        """The prompt sent to the model must be the length-adaptive one."""
        generator.model = Mock()
        generator.model.invoke.return_value = Mock(content="a summary")
        generator.content_agent = Mock()

        result = generator._generate_season_summary_with_length(
            "Demon Slayer", 1, SEASON_ANALYSIS, target_minutes=12
        )

        assert result == "a summary"
        generator.model.invoke.assert_called_once()
        sent_prompt = generator.model.invoke.call_args[0][0]
        assert "12-minute" in sent_prompt
        # A 12-minute video gets the most detailed variant.
        assert "comprehensive exploration" in sent_prompt

    def test_target_minutes_changes_the_prompt(self, generator):
        """Different target lengths must produce different prompts."""
        generator.model = Mock()
        generator.model.invoke.return_value = Mock(content="s")
        generator.content_agent = Mock()

        generator._generate_season_summary_with_length(
            "Demon Slayer", 1, SEASON_ANALYSIS, target_minutes=5
        )
        short_prompt = generator.model.invoke.call_args[0][0]

        generator._generate_season_summary_with_length(
            "Demon Slayer", 1, SEASON_ANALYSIS, target_minutes=12
        )
        long_prompt = generator.model.invoke.call_args[0][0]

        assert short_prompt != long_prompt
        assert "5-minute" in short_prompt
        assert "12-minute" in long_prompt

    def test_falls_back_to_basic_summary_without_a_model(self, generator):
        """With no AI model there is nothing to send the prompt to."""
        generator.model = None
        generator.content_agent = None

        result = generator._generate_season_summary_with_length(
            "Demon Slayer", 1, SEASON_ANALYSIS, target_minutes=8
        )

        assert isinstance(result, str) and result


class TestPromptCarriesAnalysisData:
    def test_analysis_data_is_embedded_in_the_prompt(self, generator):
        """
        The adaptive prompt must carry the real analysis data.

        It previously contained the literal placeholder
        ``[Analysis data insertion here...]``, which is why it could not
        replace the fixed-length prompt.
        """
        prompt = generator._generate_length_adaptive_prompt(
            "Demon Slayer", 1, SEASON_ANALYSIS, 10
        )

        assert "[Analysis data insertion here...]" not in prompt
        assert "Tanjiro" in prompt
        assert "perseverance" in prompt
        assert "S1E11" in prompt
        assert "Episode Range: 1-12" in prompt

    def test_empty_analysis_does_not_raise(self, generator):
        """Partial or empty analysis data must degrade, not explode."""
        prompt = generator._generate_length_adaptive_prompt("Demon Slayer", 1, {}, 5)

        assert "5-minute" in prompt
        assert "unknown" in prompt

    def test_partial_analysis_does_not_raise(self, generator):
        partial = {"season_info": {"total_episodes": 4}}
        prompt = generator._generate_length_adaptive_prompt("Demon Slayer", 1, partial, 5)

        assert "Total Episodes: 4" in prompt
        assert "Episode Range: unknown" in prompt
