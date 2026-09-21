"""
The image seam, exercised through the *production* entry points.

``f2597bf`` gave ``create_image`` an ``image_generator`` parameter and
``tests/unit/test_image_generator_seam.py`` proved the parameter works. Nothing
proved the wiring reached it: ``create_images`` had no such parameter, every
production caller went through ``create_images``, and so the seam existed
without ever being used - a boundary you can inject into only by calling the
private half of the media layer is a boundary that is routed around.

These tests enter where production enters - ``WorkflowOrchestrator`` and
``main.AnimeVideoGenerator`` - and assert three things:

* the injected generator is what actually rendered the frames, at the exact
  deterministic paths ``mp4_file_enhanced`` reopens;
* ``build_image_generator`` is never called on that path, so no Google client
  is constructed anywhere in the run. Because ``create_image`` still builds one
  for a caller that passes none, a broken forwarding chain would otherwise keep
  *working* - it would just quietly pay Imagen per frame again. That is the
  failure this file is here to make loud;
* the generator is run-scoped: one construction per orchestrator, shared by
  every frame and by ``main.py``, not one per image.
"""

import logging
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from PIL import Image

project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from agents.workflow_orchestrator import WorkflowOrchestrator  # noqa: E402
from config.settings import get_settings  # noqa: E402
from core.protocols import ImageFileGenerator  # noqa: E402
from media.media_utils import (  # noqa: E402
    ImageGeneratorUnavailable,
    UnavailableImageGenerator,
    resolve_image_generator,
)
from tests.conftest import FakeImageGenerator  # noqa: E402

SHOW = "Naruto"
SEASON = "1"
EPISODE = "5"
FAKE_SIZE = (64, 48)
PLACEHOLDER_SIZE = (1024, 768)


# ---------------------------------------------------------------------------
# Stubs for the collaborators that would otherwise need a model or a network
# ---------------------------------------------------------------------------


class StubCharacterEnhancer:
    async def enhance_episode_with_character_data(
        self, episode_content: dict[str, Any], profiles: dict[str, Any]
    ) -> dict[str, Any]:
        scenes = [dict(scene, duration=1.0) for scene in episode_content["scenes"]]
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


def episode_data(plot_point_count: int = 3) -> dict[str, Any]:
    return {
        "show": SHOW,
        "season": SEASON,
        "episode": EPISODE,
        "youtube_transcript": "Team 7 retrieves the scroll.",
        "transcript": "NARUTO: believe it.",
        "plot_points": [f"Plot point {i} happens." for i in range(plot_point_count)],
    }


def expected_path(index: int) -> Path:
    """The filename ``create_image`` writes and ``mp4_file_enhanced`` reopens."""
    return Path(SHOW) / f"Season{SEASON}" / f"Episode{EPISODE}" / f"{SHOW}_{EPISODE}_{index}.png"


@pytest.fixture
def unbuildable_generator(monkeypatch) -> list[str]:
    """
    Record - and refuse - every attempt to construct a real generator.

    Both halves matter. Raising catches a caller that would have gone to Imagen;
    recording catches it even so, because ``create_image`` catches broadly by
    design, so an ``AssertionError`` raised inside it would be turned into a
    placeholder and swallowed. Tests assert the returned list is empty.
    """
    attempts: list[str] = []

    def explode() -> ImageFileGenerator:
        attempts.append("build_image_generator")
        raise AssertionError(
            "build_image_generator() was called: the injected generator did not "
            "reach create_image, and the run silently fell back to Imagen"
        )

    monkeypatch.setattr("media.media_utils.build_image_generator", explode)
    return attempts


@pytest.fixture
def orchestrator_with(database_manager, fake_chat_model, monkeypatch):
    """A real orchestrator whose only fakes are the ones that cost money."""

    def _build(generator: ImageFileGenerator | None) -> WorkflowOrchestrator:
        # Audio and video encoding are stubbed; images deliberately are NOT,
        # because the real create_images -> create_image path is the subject.
        monkeypatch.setattr("agents.workflow_orchestrator.wave_file", lambda **k: 3.0)
        monkeypatch.setattr("agents.workflow_orchestrator.mp4_file_enhanced", lambda **k: None)
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
            image_generator=generator,
        )

    return _build


# ---------------------------------------------------------------------------
# 1. The orchestrator: the seam reaches the renderer
# ---------------------------------------------------------------------------


async def test_the_orchestrator_renders_every_frame_with_the_injected_generator(
    orchestrator_with, unbuildable_generator, tmp_path, monkeypatch
):
    """The deliverable: injection at the production entry point, end to end.

    Nothing here patches ``create_images`` or ``create_image``. The generator
    handed to ``WorkflowOrchestrator`` is the object that writes the PNGs, and
    the production factory raises if anything reaches for Imagen instead.
    """
    monkeypatch.chdir(tmp_path)
    generator = FakeImageGenerator(color=(11, 22, 33), size=FAKE_SIZE)
    orchestrator = orchestrator_with(generator)

    data = episode_data(3)
    await orchestrator.generate_all_media(data)

    # The fake was called, once per scene, with the prompts the pipeline built.
    assert generator.call_count == 3, "the injected generator did not render the frames"
    assert all(prompt.endswith("[coherent]") for prompt in generator.prompts), generator.prompts

    # ...at exactly the paths the encoder will reopen.
    assert generator.destinations == [str(expected_path(i)) for i in range(3)]

    # ...and nothing anywhere in the run reached for a Google client.
    assert unbuildable_generator == [], "a frame constructed its own generator"

    for index in range(3):
        written = tmp_path / expected_path(index)
        assert written.is_file(), f"the video step will look for {written}"
        with Image.open(written) as image:
            assert image.size == FAKE_SIZE, "a placeholder was drawn instead of the injection"


async def test_the_orchestrator_builds_one_generator_for_the_whole_run(
    orchestrator_with, tmp_path, monkeypatch
):
    """One construction per run, not one per frame.

    ``create_image`` used to call ``build_image_generator()`` for every image,
    so an N-scene episode built N clients. The orchestrator now owns one, like
    the eleven collaborators beside it, and every frame shares it.
    """
    monkeypatch.chdir(tmp_path)
    constructions: list[str] = []

    class CountingGenerator:
        def __init__(self) -> None:
            constructions.append("built")

        def generate_image(self, prompt: str, destination: str) -> str:
            Image.new("RGB", FAKE_SIZE).save(destination)
            return destination

    monkeypatch.setattr("media.media_utils.build_image_generator", CountingGenerator)

    orchestrator = orchestrator_with(None)  # nothing injected: resolve it once
    assert constructions == ["built"], "the run did not build exactly one generator"

    await orchestrator.generate_all_media(episode_data(4))

    assert constructions == ["built"], "a generator was built per frame again"


async def test_an_unavailable_generator_still_degrades_with_its_reason(
    orchestrator_with, unbuildable_generator, tmp_path, monkeypatch, caplog
):
    """Offline is an ordinary state, and it has to stay one.

    ``make demo`` runs exactly this shape: no key, so the run holds a stand-in
    rather than a client, and every scene becomes a placeholder title card whose
    reason is printed and logged - once per frame, as before.
    """
    monkeypatch.chdir(tmp_path)
    orchestrator = orchestrator_with(UnavailableImageGenerator("No Google API key found"))

    with caplog.at_level(logging.WARNING, logger="media.media_utils"):
        await orchestrator.generate_all_media(episode_data(2))

    for index in range(2):
        written = tmp_path / expected_path(index)
        assert written.is_file()
        with Image.open(written) as image:
            assert image.size == PLACEHOLDER_SIZE
    assert caplog.text.count("No Google API key found - creating placeholder") == 2
    assert unbuildable_generator == [], "the offline run tried to build a client per frame"


def test_resolving_without_a_key_yields_a_stand_in_that_names_the_reason(monkeypatch):
    """``resolve_image_generator`` never raises; it explains instead."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    generator = resolve_image_generator()

    assert isinstance(generator, UnavailableImageGenerator)
    assert isinstance(generator, ImageFileGenerator)
    with pytest.raises(ImageGeneratorUnavailable, match="No Google API key found"):
        generator.generate_image("a scene", "unused.png")


# ---------------------------------------------------------------------------
# 2. main.py: the other production entry point, and the same object
# ---------------------------------------------------------------------------


class FakeVectorSearchManager:
    """Stand-in for the optional vector search backend."""


@pytest.fixture
def application(tmp_path, fake_chat_model, monkeypatch):
    """A real ``AnimeVideoGenerator`` with an injected image generator."""
    import main

    settings = get_settings().model_copy(
        update={
            "database_path": str(tmp_path / "video_generator.db"),
            "output_directory": str(tmp_path / "output"),
        }
    )
    generator = FakeImageGenerator(color=(9, 9, 9), size=FAKE_SIZE)

    with (
        patch("main.get_settings", return_value=settings),
        patch("langchain.chat_models.init_chat_model", return_value=fake_chat_model),
        patch("main.CharacterAnalysisAgent", return_value=StubCharacterAnalyzer()),
        patch("main.VectorSearchManager", return_value=FakeVectorSearchManager()),
        patch("main.resolve_image_generator", return_value=generator),
    ):
        instance = main.AnimeVideoGenerator()

    return instance, generator


def test_one_image_generator_per_process(application):
    """The orchestrator renders through the application's generator, not its own."""
    instance, generator = application

    assert instance.image_generator is generator
    assert instance.orchestrator.image_generator is generator


def test_the_season_path_renders_through_the_injected_generator(
    application, unbuildable_generator, tmp_path, monkeypatch
):
    """``_generate_season_images`` is the second production caller of ``create_images``."""
    monkeypatch.chdir(tmp_path)
    instance, generator = application
    concepts = [
        {"index": 0, "enhanced_prompt": "first concept"},
        {"index": 1, "enhanced_prompt": "second concept"},
    ]

    instance._generate_season_images(concepts, SHOW, 2)

    assert generator.prompts == ["first concept", "second concept"]
    assert generator.destinations == [
        str(Path(SHOW) / "Season2" / "EpisodeSeason_2" / f"{SHOW}_Season_2_{index}.png")
        for index in range(2)
    ]
    for destination in generator.destinations:
        assert (tmp_path / destination).is_file()
    assert unbuildable_generator == [], "the season path built its own generator"
