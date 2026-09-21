#!/usr/bin/env python3
"""
End-to-end test for the episode processing pipeline.

This drives ``WorkflowOrchestrator.process_episode`` from a URL all the way to
persisted records and media artifacts, with every *external* dependency faked:

* HTTP  -- ``requests.get`` is replaced, so no site is scraped. The real
  BeautifulSoup parsing in ``utils/web_utils.py`` still runs against canned HTML.
* Gemini -- ``init_chat_model`` returns the ``fake_chat_model`` fixture. No API
  key is read and no provider package is contacted.
* ChromaDB / sentence-transformers -- the character analysis agent is replaced
  with a stand-in returning canned profiles (the real one opens a persistent
  vector store and downloads an embedding model).
* Media encoding -- ``create_images`` / ``wave_file`` / ``mp4_file_enhanced``
  are replaced with fakes that write real placeholder files into ``tmp_path``.

Everything between those boundaries is the production code path: content
extraction, structured summarisation, quality validation, SQLite persistence,
character-aware timing, adaptive quality selection and visual-coherence prompt
construction.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from agents.workflow_orchestrator import WorkflowOrchestrator

EPISODE_URL = "https://example.invalid/naruto/season-1/episode-5"


class FakeHTTPResponse:
    """Just enough of ``requests.Response`` for ``utils.web_utils.get_html_content``."""

    def __init__(self, text: str):
        self.text = text
        self.status_code = 200

    def raise_for_status(self) -> None:
        return None


class FakeCharacterAnalysisAgent:
    """
    Stand-in for the ChromaDB-backed ``CharacterAnalysisAgent``.

    Returns canned profiles in the same ``{name: profile}`` shape the real agent
    produces, so the downstream ``EpisodeCharacterEnhancer`` runs for real.
    """

    def __init__(self, *args, profiles=None, **kwargs):
        self.profiles = profiles or {}
        self.calls = []

    def analyze_episode_characters(self, show_name, season, episode, transcript):
        self.calls.append((show_name, season, episode, transcript))
        return self.profiles


class RecordedMedia:
    """Fake media backend that writes real placeholder artifacts to disk."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.image_prompts = None
        self.image_generator = None
        self.audio_text = None
        self.video_durations = None

    def create_images(self, sentences, episode, season, show, image_generator=None):
        self.image_prompts = list(sentences)
        self.image_generator = image_generator
        episode_dir = self.output_dir / show / f"Season {season}" / f"Episode {episode}"
        episode_dir.mkdir(parents=True, exist_ok=True)
        for index, _prompt in enumerate(sentences):
            (episode_dir / f"image_{index}.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    def wave_file(self, show, season, episode, contents, **kwargs):
        self.audio_text = contents
        episode_dir = self.output_dir / show / f"Season {season}" / f"Episode {episode}"
        episode_dir.mkdir(parents=True, exist_ok=True)
        (episode_dir / "audio.wav").write_bytes(b"RIFF\x00\x00\x00\x00WAVE")
        return 30.0  # pretend the narration runs 30 seconds

    def mp4_file_enhanced(self, show, season, episode, sentences, durations, **kwargs):
        self.video_durations = list(durations)
        episode_dir = self.output_dir / show / f"Season {season}" / f"Episode {episode}"
        episode_dir.mkdir(parents=True, exist_ok=True)
        (episode_dir / "video.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42")


@pytest.fixture
def episode_html(sample_transcript) -> str:
    """Canned transcript page in the shape ``parse_html_with_beautifulsoup`` expects."""
    return (
        "<html><body>"
        "<h1>Naruto - Season 1, Episode 5</h1>"
        f'<div class="full-script">{sample_transcript}</div>'
        "</body></html>"
    )


@pytest.fixture
def media(tmp_path) -> RecordedMedia:
    return RecordedMedia(tmp_path / "media_output")


@pytest.fixture
def orchestrator(temp_db_path, fake_chat_model, sample_character_analysis, episode_html, media):
    """A real WorkflowOrchestrator with only its external boundaries faked out."""
    character_agent = FakeCharacterAnalysisAgent(profiles=sample_character_analysis["profiles"])

    with (
        patch("agents.workflow_orchestrator.init_chat_model", return_value=fake_chat_model),
        patch(
            "agents.workflow_orchestrator.CharacterAnalysisAgent",
            return_value=character_agent,
        ),
        patch(
            "utils.web_utils.requests.get", return_value=FakeHTTPResponse(episode_html)
        ) as http_get,
        patch("agents.workflow_orchestrator.create_images", side_effect=media.create_images),
        patch("agents.workflow_orchestrator.wave_file", side_effect=media.wave_file),
        patch(
            "agents.workflow_orchestrator.mp4_file_enhanced",
            side_effect=media.mp4_file_enhanced,
        ),
    ):
        instance = WorkflowOrchestrator(db_path=temp_db_path)
        instance.test_http_get = http_get
        instance.test_character_agent = character_agent
        yield instance


async def test_process_episode_produces_records_and_artifacts(
    orchestrator, media, temp_db_path, sample_transcript, sample_episode_summary
):
    """
    The full pipeline turns a transcript URL into a database row and media files.

    This is the whole point of the project, exercised without touching the
    network, an API key or a real encoder.
    """
    result = await orchestrator.process_episode(EPISODE_URL, "Naruto")

    assert result["success"] is True, result.get("error")
    assert result["job_id"].startswith("Naruto_")

    # The scrape went through our fake transport, against the URL we asked for.
    orchestrator.test_http_get.assert_called_with(EPISODE_URL)

    # --- persisted record -------------------------------------------------
    stored = orchestrator.db.get_episode("Naruto", "1", "5")
    assert stored is not None, "Episode should be persisted to SQLite"
    assert stored["url"] == EPISODE_URL
    assert "Shadow Clone Jutsu" in stored["transcript"], (
        "The real BeautifulSoup parse of the canned page should be stored"
    )
    assert stored["summary"] == sample_episode_summary.youtube_transcript
    assert stored["plot_points"] is not None

    # The database file really exists on disk, not just in memory.
    assert Path(temp_db_path).exists()

    # --- what the model was actually asked --------------------------------
    structured_prompts = orchestrator.model_with_structure.prompts
    assert len(structured_prompts) == 1, "Summarisation should happen exactly once"
    prompt_text = str(structured_prompts[0])
    assert "Naruto" in prompt_text
    assert "Shadow Clone Jutsu" in prompt_text, "Transcript should reach the model"

    # --- character analysis was driven with the episode identity ----------
    assert orchestrator.test_character_agent.calls == [("Naruto", "1", "5", "")]

    # --- media artifacts --------------------------------------------------
    expected_plot_points = sample_episode_summary.plot_points
    assert media.image_prompts is not None, "Image generation should have been driven"
    assert len(media.image_prompts) == len(expected_plot_points)
    for plot_point, prompt in zip(expected_plot_points, media.image_prompts, strict=True):
        assert plot_point in prompt, "Each scene prompt must carry its plot point"
        assert len(prompt) > len(plot_point), "Visual coherence should have enriched the prompt"
    assert any("anime" in prompt.lower() for prompt in media.image_prompts), (
        "Coherence prompts should carry the episode's visual style"
    )

    assert media.audio_text == sample_episode_summary.youtube_transcript
    assert media.video_durations is not None
    assert len(media.video_durations) == len(expected_plot_points)
    assert all(duration > 0 for duration in media.video_durations)

    episode_dir = media.output_dir / "Naruto" / "Season 1" / "Episode 5"
    written = sorted(path.name for path in episode_dir.iterdir())
    assert "audio.wav" in written
    assert "video.mp4" in written
    assert sum(name.endswith(".png") for name in written) == len(expected_plot_points)


async def test_process_episode_reports_failure_when_page_is_unavailable(
    orchestrator,
):
    """
    A dead source URL must surface as a failed result, not a half-written episode.
    """
    orchestrator.test_http_get.return_value = FakeHTTPResponse("")

    result = await orchestrator.process_episode(EPISODE_URL, "Naruto")

    assert result["success"] is False
    assert "Content extraction failed" in result["error"]
    assert orchestrator.db.get_episode("Naruto", "1", "5") is None, (
        "Nothing should be persisted when extraction fails"
    )
