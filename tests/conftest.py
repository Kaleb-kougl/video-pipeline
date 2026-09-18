"""
Shared pytest fixtures for the test suite.

Everything here exists because at least two places in the suite needed the same
thing, or because a test needs a stand-in for an external dependency (Gemini,
ChromaDB, the network, the filesystem) that must never be touched during a test
run. Nothing here is speculative: every fixture below is used by a real test.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from core.database import DatabaseManager
from core.schemas import Episode_Summary_Schema

FIXTURES_DIR = Path(__file__).parent / "fixtures"
CHARACTER_DATA_DIR = FIXTURES_DIR / "character_data"


# ---------------------------------------------------------------------------
# Canned episode / character data
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_episode_content() -> dict[str, Any]:
    """
    Scene-level episode content as the quality-enhancement pipeline consumes it.

    Loaded fresh per test: the enhancer and format adapter mutate the structure
    they are handed, so this must not be shared between tests.
    """
    with open(CHARACTER_DATA_DIR / "sample_episode_content.json") as handle:
        return json.load(handle)


@pytest.fixture
def sample_character_analysis() -> dict[str, Any]:
    """Canned character analysis (``{"profiles": {...}}``) for the same episode."""
    with open(CHARACTER_DATA_DIR / "sample_character_analysis.json") as handle:
        return json.load(handle)


@pytest.fixture
def sample_transcript() -> str:
    """A short but realistic episode transcript, used in place of a scraped one."""
    return (
        "Naruto: I'm going to become Hokage, believe it!\n"
        "Sasuke: You talk too much. Focus on the mission.\n"
        "Sakura: Both of you, stop arguing. Kakashi-sensei is waiting.\n"
        "Kakashi: Team 7, your task today is to retrieve the scroll from the "
        "forest outpost before sundown.\n"
        "Naruto: Shadow Clone Jutsu! Let's see them stop a hundred of me.\n"
        "Sasuke: Reckless. But it bought us the opening we needed.\n"
        "Sakura: I'll heal the wounded while you two hold the line.\n"
        "Kakashi: Well done. You fought as a team today, and that matters more "
        "than any single technique."
    )


@pytest.fixture
def sample_episode_summary() -> Episode_Summary_Schema:
    """
    The structured summary a real chat model would return for ``sample_transcript``.

    Returned as the actual pydantic schema so that anything consuming it sees the
    same object shape the production ``with_structured_output`` path produces.
    """
    return Episode_Summary_Schema(
        show="Naruto",
        season="1",
        episode="5",
        youtube_transcript=(
            "Team 7 takes on a scroll retrieval mission, and the squabbling finally "
            "gives way to real teamwork. Like, comment, and subscribe for more."
        ),
        plot_points=[
            "Naruto declares he will become Hokage before the mission briefing.",
            "Kakashi assigns Team 7 to retrieve a scroll from the forest outpost.",
            "Naruto uses Shadow Clone Jutsu to overwhelm the outpost guards.",
            "Sakura heals the wounded while Sasuke holds the line.",
            "Kakashi praises the squad for fighting as a team.",
        ],
    )


# ---------------------------------------------------------------------------
# Fake chat model (stand-in for init_chat_model / Gemini)
# ---------------------------------------------------------------------------


class FakeStructuredModel:
    """The object ``model.with_structured_output(schema)`` returns."""

    def __init__(self, response: Any):
        self.response = response
        self.prompts: list[Any] = []

    def invoke(self, prompt: Any) -> Any:
        self.prompts.append(prompt)
        return self.response


class FakeChatModel:
    """
    Minimal stand-in for a LangChain chat model.

    Implements only the surface the pipeline actually uses: ``invoke`` for free
    text and ``with_structured_output`` for schema-constrained responses. Every
    prompt is recorded so tests can assert what was asked, and no API key,
    network call or provider package is involved.
    """

    def __init__(self, structured_response: Any, text_response: str = "Fake analysis"):
        self.structured_response = structured_response
        self.text_response = text_response
        self.prompts: list[Any] = []
        self.structured_model: FakeStructuredModel | None = None

    def invoke(self, prompt: Any) -> str:
        self.prompts.append(prompt)
        return self.text_response

    def with_structured_output(self, schema: Any) -> FakeStructuredModel:
        self.requested_schema = schema
        self.structured_model = FakeStructuredModel(self.structured_response)
        return self.structured_model


@pytest.fixture
def fake_chat_model(sample_episode_summary) -> FakeChatModel:
    """A chat model that returns ``sample_episode_summary`` instead of calling Gemini."""
    return FakeChatModel(structured_response=sample_episode_summary)


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_db_path(tmp_path) -> str:
    """Path to a throwaway SQLite file inside pytest's per-test temp directory."""
    return str(tmp_path / "video_generator.db")


@pytest.fixture
def database_manager(temp_db_path) -> DatabaseManager:
    """A real, initialized ``DatabaseManager`` backed by a throwaway SQLite file."""
    return DatabaseManager(temp_db_path)


# ---------------------------------------------------------------------------
# Image generation stand-ins
# ---------------------------------------------------------------------------


@pytest.fixture
def image_factory(tmp_path):
    """
    Write real image files to disk so OpenCV-based scoring runs for real.

    ``seed`` produces noise (useful when a test needs two genuinely different
    images); otherwise a flat ``color`` fill is written.
    """
    import cv2
    import numpy as np

    counter = {"n": 0}

    def _make(color=None, size=(240, 320), seed=None):
        counter["n"] += 1
        if seed is not None:
            rng = np.random.default_rng(seed)
            image = rng.integers(0, 256, (*size, 3), dtype=np.uint8)
        else:
            image = np.zeros((*size, 3), dtype=np.uint8)
            image[:, :] = color if color is not None else (0, 0, 0)
        path = tmp_path / f"image_{counter['n']}.png"
        assert cv2.imwrite(str(path), image), "Test image should be written"
        return str(path)

    return _make


class RecordingImageGenerator:
    """
    Stand-in for a real image generator, injected through the public seam that
    ``core/visual_coherence_manager.py`` exposes (an async callable taking the
    enhanced prompt and returning a path).

    The manager itself is never patched: this writes actual image files to disk
    so the OpenCV scoring, retry and reference-update logic all run for real.
    """

    def __init__(self, image_factory, color=(200, 40, 40), seed=None, size=(240, 320)):
        self._image_factory = image_factory
        self.color = color
        self.seed = seed
        self.size = size
        self.prompts: list[str] = []
        self.paths: list[str] = []

    async def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        path = self._image_factory(color=self.color, size=self.size, seed=self.seed)
        self.paths.append(path)
        return path

    @property
    def call_count(self) -> int:
        return len(self.prompts)


@pytest.fixture
def make_generator(image_factory):
    """Factory for injectable recording image generators (visual coherence seam)."""

    def _make(color=(200, 40, 40), seed=None, size=(240, 320)):
        return RecordingImageGenerator(image_factory, color=color, seed=seed, size=size)

    return _make


class FakeImageGenerator:
    """
    Conforms to the ``generate_image(prompt)`` protocol that
    ``core/content_cache.py`` documents for ``get_or_generate_image``.
    """

    def __init__(self, payload: dict[str, Any] | None = None):
        self.payload = payload or {
            "url": "/generated/test_image.png",
            "prompt": "test prompt",
            "style": "anime",
        }
        self.prompts: list[str] = []

    def generate_image(self, prompt: str) -> dict[str, Any]:
        self.prompts.append(prompt)
        return dict(self.payload)

    @property
    def call_count(self) -> int:
        return len(self.prompts)


@pytest.fixture
def fake_image_generator() -> FakeImageGenerator:
    """An image generator implementing the ``generate_image(prompt)`` protocol."""
    return FakeImageGenerator()
