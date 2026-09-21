"""
Shared pytest fixtures for the test suite.

Everything here exists because at least two places in the suite needed the same
thing, or because a test needs a stand-in for an external dependency (Gemini,
ChromaDB, the network, the filesystem) that must never be touched during a test
run. Nothing here is speculative: every fixture below is used by a real test.
"""

import builtins
import io
import json
import os
import sqlite3
import subprocess
from functools import lru_cache
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
    Stand-in for a real image generator, injected through the seam that
    ``core/visual_coherence_manager.py`` exposes (an async callable taking the
    enhanced prompt and returning a path).

    That callable is ``core.protocols.ImageFileGenerator.generate_image`` with
    the destination already bound - the manager only needs a file OpenCV can
    read, so it lets the generator pick the name. ``FakeImageGenerator`` below
    implements both views; this one stays a bare callable because the visual
    coherence tests inject plain lambdas alongside it.

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
    A ``core.protocols.ImageFileGenerator`` that writes a real PNG with PIL.

    This is the second implementation that earned the protocol its place; the
    first is ``media.media_utils.ImagenImageGenerator``. It renders rather than
    pretending to, so ``create_image`` -> ``mp4_file_enhanced`` can be exercised
    end to end without a key, a client library or a socket.

    It also answers the ``VisualCoherenceManager`` seam: ``__call__(prompt)`` is
    ``generate_image`` with a destination this object picks, which is exactly
    the relationship between the two shapes.
    """

    def __init__(
        self,
        directory: Path | str | None = None,
        color: tuple[int, int, int] = (32, 64, 128),
        size: tuple[int, int] = (1024, 768),
        fail_with: Exception | None = None,
    ):
        self.directory = Path(directory) if directory is not None else None
        self.color = color
        self.size = size
        self.fail_with = fail_with
        self.prompts: list[str] = []
        self.destinations: list[str] = []

    def generate_image(self, prompt: str, destination: str) -> str:
        from PIL import Image

        self.prompts.append(prompt)
        if self.fail_with is not None:
            raise self.fail_with
        self.destinations.append(destination)
        Image.new("RGB", self.size, color=self.color).save(destination)
        return destination

    def __call__(self, prompt: str) -> str:
        """The visual-coherence view: same render, generator-chosen path."""
        directory = self.directory or Path.cwd()
        directory.mkdir(parents=True, exist_ok=True)
        return self.generate_image(prompt, str(directory / f"fake_{len(self.prompts)}.png"))

    @property
    def call_count(self) -> int:
        return len(self.prompts)


@pytest.fixture
def image_generator(tmp_path) -> FakeImageGenerator:
    """A protocol-conforming image generator that writes real PNGs, offline."""
    return FakeImageGenerator(directory=tmp_path)


class FakeImagePayloadSource:
    """
    The callback ``ContentCache.get_or_generate_image`` takes - *not* an image
    generator, despite the method name it is duck-typed against.

    ``core/content_cache.py`` asks for ``generate_image(prompt) -> dict`` and
    then caches the dict. It never renders anything and never learns where a
    file went; a dict literal would satisfy it. Keeping it separate from
    ``FakeImageGenerator`` is the point: the two shapes were being called the
    same thing, and only one of them puts a PNG on disk.

    Its signature is pinned by ``docs/CONTENT_CACHING_GUIDE.md``, so it stays
    as it is until the cache grows a second implementation of its own.
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
def fake_image_generator() -> FakeImagePayloadSource:
    """The ``ContentCache`` payload callback (see ``FakeImagePayloadSource``)."""
    return FakeImagePayloadSource()


# ---------------------------------------------------------------------------
# CI parity: make a local run behave like a clean runner
# ---------------------------------------------------------------------------
#
# Twenty tests and six errors once passed here and failed in CI, all for the
# same two reasons: they reached for `data/databases/character_db`, which is
# gitignored and therefore exists only on a machine that has already run the
# pipeline, and they constructed `SentenceTransformer("all-MiniLM-L6-v2")`,
# which is a HuggingFace download that a developer's cache silently satisfies.
#
# Fixing those tests one at a time does not stop the next one. The two fixtures
# below remove the local advantage instead: the repository's real `data/`
# directory becomes an error to touch, and the model caches point at an empty
# temporary directory with the hub in offline mode, so a download raises
# instead of succeeding from a warm cache.

REPO_ROOT = Path(__file__).resolve().parent.parent
REAL_DATA_DIR = REPO_ROOT / "data"

# Environment that decides where model weights are looked for and whether they
# may be fetched. Redirected for the whole session, and restored for the
# `network` tests, which are allowed to reach both the network and a real cache.
_MODEL_CACHE_VARS = (
    "HF_HOME",
    "HUGGINGFACE_HUB_CACHE",
    "SENTENCE_TRANSFORMERS_HOME",
    "TORCH_HOME",
)
_OFFLINE_VARS = {
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "HF_DATASETS_OFFLINE": "1",
    "HF_HUB_DISABLE_TELEMETRY": "1",
}


class RepoDataAccess(BaseException):
    """A test touched the repository's real ``data/`` directory.

    Deliberately a ``BaseException``. The production code this guard fires
    inside is full of defensive ``except Exception`` blocks - the character
    agent's constructor is one - and a guard that those swallow would turn a
    loud local failure back into a silent one that only CI sees.
    """


@lru_cache(maxsize=1)
def _data_files_in_git() -> frozenset[str]:
    """Absolute paths under ``data/`` that a clean checkout actually has.

    Two small fixtures under ``data/`` are committed; everything else there is
    gitignored build-up. Reading a committed file is fine because CI has it.
    If git cannot answer, the set is empty and every read is refused, which is
    the safe direction: it matches the runner that has the least.
    """
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", "data"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return frozenset()
    return frozenset(str(REPO_ROOT / name) for name in result.stdout.split("\0") if name)


def _offending_path(target: object) -> str | None:
    """The absolute path under the real ``data/`` tree, or ``None``.

    The ``"data"`` substring test in front is not the decision - the prefix
    comparison below it is. It is there so that the overwhelming majority of
    calls, which name a path with no ``data`` in it at all, cost one string
    scan and nothing else.
    """
    if isinstance(target, int):  # already-open file descriptor
        return None
    try:
        name = os.fspath(target)
    except TypeError:
        return None
    if isinstance(name, bytes):
        name = name.decode("utf-8", "replace")
    if "data" not in name:
        return None
    resolved = os.path.abspath(name)
    if resolved == str(REAL_DATA_DIR) or resolved.startswith(str(REAL_DATA_DIR) + os.sep):
        return resolved
    return None


def _refuse(path: str, verb: str, api: str, node_id: str) -> RepoDataAccess:
    return RepoDataAccess(
        f"\nCI-parity guard: this test tried to {verb} the repository's real data/ "
        f"directory.\n\n"
        f"    path: {path}\n"
        f"    via:  {api}\n"
        f"    test: {node_id}\n\n"
        f"Everything under data/ except two committed fixtures is gitignored, so it "
        f"exists on this machine and never on a clean runner. This is the exact "
        f"failure mode that turned a green local run into 20 failures and 6 errors "
        f"in CI.\n\n"
        f"Use `tmp_path` for scratch files, or the `database_manager` fixture for a "
        f"throwaway SQLite database. Anything whose default lands under data/ - "
        f"`CharacterAnalysisAgent()`, `VectorSearchManager()` - takes an explicit "
        f'`persist_directory=str(tmp_path / "...")`.\n\n'
        f"If the test genuinely needs the real tree, mark it `@pytest.mark.network`: "
        f"that marker means 'needs things a clean runner does not have' and is "
        f"deselected by default. Prefer fixing the default."
    )


@pytest.fixture(scope="session", autouse=True)
def _clean_runner_model_cache(tmp_path_factory):
    """Point every model cache at an empty directory and forbid downloads.

    Session-scoped and set before the first test imports anything, because
    transformers and huggingface_hub read several of these at import time.
    ``HF_HUB_OFFLINE`` turns a download into an immediate, legible error rather
    than a multi-hundred-megabyte fetch that only the developer's machine is
    fast at, and the empty cache means nothing can be served from a warm one.
    """
    cache = tmp_path_factory.mktemp("clean-runner-model-cache")
    original = {name: os.environ.get(name) for name in (*_MODEL_CACHE_VARS, *_OFFLINE_VARS)}
    with pytest.MonkeyPatch.context() as mp:
        for name in _MODEL_CACHE_VARS:
            mp.setenv(name, str(cache))
        for name, value in _OFFLINE_VARS.items():
            mp.setenv(name, value)
        yield original


@pytest.fixture(autouse=True)
def _ci_parity_guard(request, monkeypatch, _clean_runner_model_cache):
    """Refuse filesystem access to the repository's real ``data/`` directory.

    Wraps the handful of entry points that every higher-level filesystem call
    in this tree funnels through - ``open``, the ``os`` mutators, directory
    listing and ``sqlite3.connect``. ``pathlib`` is covered for free: ``Path.
    mkdir`` is ``os.mkdir``, ``Path.read_text`` is ``io.open``, and so on.

    Writes are refused everywhere under ``data/``. Reads are refused unless the
    file is committed, because a committed file is one a clean runner also has.

    ``network``-marked tests get neither guard nor offline environment: that
    marker already means "needs things a clean runner does not have".
    """
    if request.node.get_closest_marker("network"):
        for name, value in _clean_runner_model_cache.items():
            if value is None:
                monkeypatch.delenv(name, raising=False)
            else:
                monkeypatch.setenv(name, value)
        yield
        return

    node_id = request.node.nodeid
    real_open, real_io_open = builtins.open, io.open
    real_connect = sqlite3.connect

    def _guard_read(path, api):
        offender = _offending_path(path)
        if offender is not None and offender not in _data_files_in_git():
            raise _refuse(offender, "read from", api, node_id)

    def _guard_write(path, api):
        offender = _offending_path(path)
        if offender is not None:
            raise _refuse(offender, "write to", api, node_id)

    def _open(file, mode="r", *args, **kwargs):
        if any(character in mode for character in "wax+"):
            _guard_write(file, f"open(..., mode={mode!r})")
        else:
            _guard_read(file, "open()")
        return real_open(file, mode, *args, **kwargs)

    def _io_open(file, mode="r", *args, **kwargs):
        if any(character in mode for character in "wax+"):
            _guard_write(file, f"io.open(..., mode={mode!r})")
        else:
            _guard_read(file, "io.open()")
        return real_io_open(file, mode, *args, **kwargs)

    def _connect(database, *args, **kwargs):
        _guard_write(database, "sqlite3.connect()")
        return real_connect(database, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", _open)
    monkeypatch.setattr(io, "open", _io_open)
    monkeypatch.setattr(sqlite3, "connect", _connect)

    for name in ("mkdir", "makedirs", "remove", "unlink", "rmdir", "truncate"):
        real = getattr(os, name)

        def _mutator(path, *args, _real=real, _api=f"os.{name}()", **kwargs):
            _guard_write(path, _api)
            return _real(path, *args, **kwargs)

        monkeypatch.setattr(os, name, _mutator)

    for name in ("rename", "replace"):
        real = getattr(os, name)

        def _mover(src, dst, *args, _real=real, _api=f"os.{name}()", **kwargs):
            _guard_write(src, _api)
            _guard_write(dst, _api)
            return _real(src, dst, *args, **kwargs)

        monkeypatch.setattr(os, name, _mover)

    for name in ("listdir", "scandir"):
        real = getattr(os, name)

        def _lister(path=".", *args, _real=real, _api=f"os.{name}()", **kwargs):
            _guard_read(path, _api)
            return _real(path, *args, **kwargs)

        monkeypatch.setattr(os, name, _lister)

    yield
