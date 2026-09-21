"""
The per-video scene cap: the ceiling on how many paid images one run can buy.

``create_images`` renders one image per scene, and the scene count comes from a
model response -- plot points in the episode path, prose length in the season
path. Neither is bounded by anything the code controls, so a single Gemini reply
used to decide the image bill. These tests pin the ceiling, the fact that
truncation is *announced* rather than silent, and the invariant that makes
truncation safe: the images, the durations and the sentence list handed to the
encoder are all cut to the same length. ``mp4_file_enhanced`` resolves images by
index, so a cap applied to one of the three and not the others is a crash or a
mistimed video, not a saving.
"""

import logging
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from agents.workflow_orchestrator import WorkflowOrchestrator  # noqa: E402
from config.settings import VideoConfig, get_settings  # noqa: E402
from core.schemas import enforce_scene_cap  # noqa: E402

# Above the 5-concept floor `_parse_summary_to_concepts` pads short summaries
# up to, so the two mechanisms can be tested without colliding.
CAP = 6


# ---------------------------------------------------------------------------
# Stubs: every boundary that would cost money or need a model
# ---------------------------------------------------------------------------


class StubCharacterEnhancer:
    """Returns the scenes it was given, timed, as the real enhancer does."""

    async def enhance_episode_with_character_data(
        self, episode_content: dict[str, Any], profiles: dict[str, Any]
    ) -> dict[str, Any]:
        scenes = [dict(scene, duration=3.0) for scene in episode_content["scenes"]]
        return {"scenes": scenes, "character_focus": {}}


class StubVisualCoherence:
    async def build_coherent_prompt(
        self, prompt: str, characters: list[Any], context: dict[str, Any]
    ) -> str:
        return f"{prompt} [coherent]"


class StubQualityProfile:
    name = "stub"


class StubQualityManager:
    async def select_quality_profile(self, context: str, deadline: Any) -> StubQualityProfile:
        return StubQualityProfile()

    def record_quality_metrics(self, profile: Any, metrics: dict[str, Any]) -> None:
        pass


class StubCharacterAnalyzer:
    def analyze_episode_characters(
        self, show_name: str, season: Any, episode: Any, transcript: str
    ) -> dict[str, Any]:
        return {}


class MediaRecorder:
    """Records what the media layer was asked to render instead of rendering it."""

    def __init__(self) -> None:
        self.image_prompts: list[str] | None = None
        self.image_generator: Any = None
        self.mp4_sentences: list[str] | None = None
        self.mp4_durations: list[float] | None = None

    def create_images(
        self,
        sentences: list[str],
        episode: str,
        season: str,
        show: str,
        image_generator: Any = None,
    ) -> None:
        self.image_prompts = list(sentences)
        self.image_generator = image_generator

    def mp4_file_enhanced(self, **kwargs: Any) -> None:
        self.mp4_sentences = list(kwargs["sentences"])
        self.mp4_durations = list(kwargs["durations"])


def _settings_with_cap(cap: int):
    """The real settings with only ``max_scenes`` changed."""
    base = get_settings()
    return base.model_copy(
        update={"video_config": base.video_config.model_copy(update={"max_scenes": cap})}
    )


@pytest.fixture
def media() -> MediaRecorder:
    return MediaRecorder()


@pytest.fixture
def orchestrator(database_manager, fake_chat_model, media, monkeypatch):
    """A real orchestrator with a cap of ``CAP`` and no paid media calls."""
    monkeypatch.setattr("agents.workflow_orchestrator.create_images", media.create_images)
    monkeypatch.setattr("agents.workflow_orchestrator.wave_file", lambda **k: 60.0)
    monkeypatch.setattr("agents.workflow_orchestrator.mp4_file_enhanced", media.mp4_file_enhanced)
    monkeypatch.setattr(
        "agents.workflow_orchestrator.get_settings", lambda: _settings_with_cap(CAP)
    )

    return WorkflowOrchestrator(
        db=database_manager,
        model=fake_chat_model,
        content_agent=object(),
        video_agent=object(),
        qa_agent=object(),
        discovery_agent=object(),
        transcript_agent=object(),
        config_manager=object(),
        character_analysis_agent=StubCharacterAnalyzer(),
        character_enhancer=StubCharacterEnhancer(),
        visual_coherence=StubVisualCoherence(),
        quality_manager=StubQualityManager(),
        format_adapter=object(),
    )


def episode_data(plot_point_count: int) -> dict[str, Any]:
    return {
        "show": "Naruto",
        "season": "1",
        "episode": "5",
        "youtube_transcript": "Team 7 retrieves the scroll. Like, comment and subscribe.",
        "transcript": "NARUTO: believe it.",
        "plot_points": [f"Plot point {i} happens." for i in range(plot_point_count)],
    }


# ---------------------------------------------------------------------------
# The episode path: plot points -> scenes -> create_images
# ---------------------------------------------------------------------------


async def test_a_model_over_the_cap_buys_exactly_the_cap(orchestrator, media, caplog):
    """The image bill is the cap's, not the model's."""
    caplog.set_level(logging.WARNING)

    await orchestrator.generate_all_media(episode_data(CAP * 5))

    assert len(media.image_prompts) == CAP

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    truncations = [r for r in warnings if "Scene cap applied" in r.getMessage()]
    assert len(truncations) == 1, "truncation must be announced exactly once"

    # Both counts, so the log says what was dropped and not merely that
    # something was.
    message = truncations[0].getMessage()
    assert str(CAP * 5) in message, message
    assert str(CAP) in message, message
    assert "Naruto S1E5" in message, message


async def test_a_model_under_the_cap_is_untouched(orchestrator, media, caplog):
    """A normal response must pass through unchanged and unremarked."""
    caplog.set_level(logging.WARNING)
    data = episode_data(CAP - 1)

    await orchestrator.generate_all_media(data)

    assert len(media.image_prompts) == CAP - 1
    assert media.mp4_sentences == data["plot_points"]
    assert not [r for r in caplog.records if "Scene cap applied" in r.getMessage()]


@pytest.mark.parametrize(
    ("produced", "expected_images", "truncated"),
    [
        (CAP - 1, CAP - 1, False),
        (CAP, CAP, False),  # exactly at the cap is not a truncation
        (CAP + 1, CAP, True),  # one over is
    ],
)
async def test_the_boundary(orchestrator, media, caplog, produced, expected_images, truncated):
    caplog.set_level(logging.WARNING)

    await orchestrator.generate_all_media(episode_data(produced))

    assert len(media.image_prompts) == expected_images
    logged = any("Scene cap applied" in r.getMessage() for r in caplog.records)
    assert logged is truncated


async def test_images_durations_and_sentences_stay_the_same_length(orchestrator, media):
    """The encoder looks images up by index; a partial cap is a missing file.

    ``mp4_file_enhanced`` zips sentences against durations with ``strict=False``
    and builds ``..._{index}.png`` for each pair, so if the sentence list were
    left uncapped while the images were capped, encoding would raise on the
    first image that was never rendered.
    """
    await orchestrator.generate_all_media(episode_data(CAP * 3))

    assert len(media.image_prompts) == CAP
    assert len(media.mp4_sentences) == CAP
    assert len(media.mp4_durations) == CAP


async def test_the_stored_summary_keeps_every_plot_point(orchestrator, media):
    """Only the images are capped. The summary is not edited to match."""
    data = episode_data(CAP * 3)

    await orchestrator.generate_all_media(data)

    assert len(data["plot_points"]) == CAP * 3


# ---------------------------------------------------------------------------
# The season path: summary prose -> visual concepts -> create_images
# ---------------------------------------------------------------------------


class FakeVectorSearchManager:
    """Stand-in for the optional vector search backend."""


class FakeCharacterAgent:
    """Stand-in for the ChromaDB/sentence-transformers character analysis agent."""


@pytest.fixture
def generator(tmp_path, fake_chat_model):
    """A real ``AnimeVideoGenerator`` with a cap of ``CAP`` and no downloads."""
    import main

    settings = _settings_with_cap(CAP).model_copy(
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


def test_a_long_season_summary_is_capped_into_concepts(generator, caplog):
    """Concept count follows prose length, so it needs the same ceiling."""
    caplog.set_level(logging.WARNING)
    # 3 sentences per concept, so this is well past the cap.
    summary = " ".join(f"Sentence number {i} of the season." for i in range(CAP * 9))

    concepts = generator._parse_summary_to_concepts(summary, target_minutes=5)

    assert len(concepts) == CAP
    assert any("Scene cap applied" in r.getMessage() for r in caplog.records)


def test_a_short_season_summary_is_untouched(generator, caplog):
    """Two sentences' worth of prose, padded to the existing 5-concept floor.

    Nothing is truncated: the cap is a ceiling, and the floor is what decides
    the count here.
    """
    caplog.set_level(logging.WARNING)
    summary = "One. Two. Three. Four. Five. Six."

    concepts = generator._parse_summary_to_concepts(summary, target_minutes=5)

    assert len(concepts) == 5
    assert not [r for r in caplog.records if "Scene cap applied" in r.getMessage()]


def test_a_cap_that_cannot_fill_the_target_says_so(generator, caplog):
    """A cap that shortens the video is reported, not discovered in the output.

    With 4 concepts clamped to 15s each the visuals run 60s, against the 240s of
    visual time a 5-minute target asks for. The encoder concatenates the image
    clips and cuts the narration to fit, so this is a materially shorter video.
    """
    caplog.set_level(logging.WARNING)

    timing = generator._calculate_visual_timing(target_minutes=5, concept_count=4)

    assert timing["concept_duration"] == generator.settings.video_config.max_concept_duration
    under_fill = [r for r in caplog.records if "under-fills the target" in r.getMessage()]
    assert len(under_fill) == 1
    assert "16 concepts would be needed" in under_fill[0].getMessage()


def test_enough_concepts_to_fill_the_target_are_not_reported(generator, caplog):
    caplog.set_level(logging.WARNING)

    generator._calculate_visual_timing(target_minutes=5, concept_count=16)

    assert not [r for r in caplog.records if "under-fills the target" in r.getMessage()]


# ---------------------------------------------------------------------------
# The configured bound itself
# ---------------------------------------------------------------------------


def test_the_default_cap_cannot_shorten_any_supported_video():
    """The default is derived, so it must stay equal to its derivation.

    ``max_scenes`` defaults to the number of scenes needed to fill the longest
    supported video at the longest permitted per-scene duration. Set that way it
    bounds worst-case spend without being able to make any video the current
    timing rules could have filled any shorter. If someone edits the duration
    bounds and not the cap, this fails.
    """
    config = VideoConfig()

    assert config.max_scenes == config.scenes_to_fill(config.max_duration_minutes)
    assert config.max_scenes == 48


def test_the_cap_is_validated():
    with pytest.raises(ValueError):
        VideoConfig(max_scenes=0)
    with pytest.raises(ValueError):
        VideoConfig(max_scenes=201)


def test_the_cap_is_configurable():
    assert VideoConfig(max_scenes=12).max_scenes == 12


def test_enforce_scene_cap_refuses_a_meaningless_limit():
    with pytest.raises(ValueError, match="at least 1"):
        enforce_scene_cap(["a", "b"], 0, context="test")


def test_enforce_scene_cap_preserves_order():
    kept = enforce_scene_cap(["a", "b", "c", "d"], 2, context="test")

    assert kept == ["a", "b"]
