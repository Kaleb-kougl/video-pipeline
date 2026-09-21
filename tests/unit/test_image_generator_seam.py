"""
The image-generation seam: one protocol, two implementations, one fallback.

``media/media_utils.py`` used to build a ``genai.Client`` inline inside
``create_image``, which meant the only way to render a frame without Google was
to monkeypatch the module. Meanwhile three places in the repository described an
"injectable image generator" and no two of them agreed on its shape - one
returned a path, one returned a dict, and the only implementation was a test
fake. ``core.protocols.ImageFileGenerator`` settles it: render this prompt into
this path, return the path.

What these tests pin:

* both implementations really satisfy the protocol, by signature and not just
  by attribute name;
* an injected generator renders through ``create_image`` with no client library
  call and no socket, at the exact path ``mp4_file_enhanced`` will reopen;
* every reason the production generator can fail to exist - no key, no client
  library, a client that refuses to construct - degrades to the same placeholder
  title card, with the reason logged (the ``b6fde06`` lesson);
* a caller that injects nothing still writes one real PNG per sentence.

What these tests do *not* pin is that production actually injects anything:
they all enter at ``create_image``/``create_images``, which is the half of the
seam nothing in production called. That is
``tests/unit/test_image_generator_wiring.py``, which enters through the
``WorkflowOrchestrator`` and ``main.AnimeVideoGenerator`` instead.
"""

import inspect
import logging
import os
import socket
import subprocess
import sys
import unittest.mock as mock
from pathlib import Path

import pytest
from PIL import Image

from core.protocols import ImageFileGenerator
from media.media_utils import (
    ImageGeneratorUnavailable,
    ImagenImageGenerator,
    build_image_generator,
    create_image,
    create_images,
)
from tests.conftest import FakeImageGenerator

SHOW = "Seam Test Show"
SEASON = "1"
EPISODE = "3"
PLACEHOLDER_SIZE = (1024, 768)


def expected_path(index: int, episode: str = EPISODE) -> Path:
    """The filename both ``create_image`` and ``mp4_file_enhanced`` compute."""
    return Path(SHOW) / f"Season{SEASON}" / f"Episode{episode}" / f"{SHOW}_{episode}_{index}.png"


@pytest.fixture
def in_tmp_cwd(tmp_path, monkeypatch):
    """Media paths are relative to the process cwd; keep them in a sandbox."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def without_api_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    return monkeypatch


@pytest.fixture
def unused_genai():
    """Patch the client library so any use of it is an assertable mistake."""
    with mock.patch("media.media_utils.genai") as genai:
        yield genai


# ---------------------------------------------------------------------------
# 1. The protocol has two real implementations
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "implementation",
    [ImagenImageGenerator, FakeImageGenerator],
    ids=["imagen-adapter", "test-fake"],
)
def test_both_implementations_satisfy_the_protocol(implementation):
    """A protocol earns its place at two implementations. Here are both."""
    assert isinstance(implementation.__new__(implementation), ImageFileGenerator)

    expected = inspect.signature(ImageFileGenerator.generate_image)
    actual = inspect.signature(implementation.generate_image)
    assert list(actual.parameters) == list(expected.parameters), (
        f"{implementation.__name__}.generate_image does not take (self, prompt, destination)"
    )


def test_the_adapter_returns_the_destination_it_was_given(tmp_path):
    """The caller owns the path: the generator writes there and says so."""
    destination = str(tmp_path / "frame.png")
    saved = []

    client = mock.Mock()
    generated = mock.Mock()
    generated.image.save.side_effect = lambda path: (
        saved.append(path),
        Image.new("RGB", (8, 8)).save(path),
    )
    client.models.generate_images.return_value = mock.Mock(generated_images=[generated])

    generator = ImagenImageGenerator.__new__(ImagenImageGenerator)
    generator._client = client

    with mock.patch("media.media_utils.types"):
        assert generator.generate_image("a prompt", destination) == destination

    assert saved == [destination]
    assert Path(destination).is_file()


def test_the_adapter_refuses_to_report_success_for_an_empty_response(tmp_path):
    """No images back is a failure, not a silently missing file."""
    client = mock.Mock()
    client.models.generate_images.return_value = mock.Mock(generated_images=[])

    generator = ImagenImageGenerator.__new__(ImagenImageGenerator)
    generator._client = client

    with mock.patch("media.media_utils.types"), pytest.raises(RuntimeError, match="no images"):
        generator.generate_image("a prompt", str(tmp_path / "frame.png"))


# ---------------------------------------------------------------------------
# 2. Injection renders, offline
# ---------------------------------------------------------------------------


def test_an_injected_generator_writes_the_path_the_video_step_opens(
    in_tmp_cwd, without_api_key, unused_genai
):
    """The whole point of the seam: a real PNG, no key, no client, no socket."""
    generator = FakeImageGenerator(color=(11, 22, 33), size=(64, 48))

    def no_sockets(*_args, **_kwargs):
        raise AssertionError("the image seam opened a socket")

    with mock.patch.object(socket.socket, "connect", no_sockets):
        create_image("a scene", EPISODE, SEASON, SHOW, 0, image_generator=generator)

    written = in_tmp_cwd / expected_path(0)
    assert written.is_file(), f"the generator did not write {written}"
    with Image.open(written) as image:
        assert image.size == (64, 48), "the placeholder ran instead of the generator"

    assert generator.prompts == ["a scene"]
    assert generator.destinations == [str(expected_path(0))]
    unused_genai.Client.assert_not_called()


def test_an_injected_generator_is_preferred_over_a_configured_key(in_tmp_cwd, monkeypatch):
    """Injection wins: a key in the environment must not smuggle Imagen back in."""
    monkeypatch.setenv("GOOGLE_API_KEY", "a-real-looking-key")
    generator = FakeImageGenerator(size=(32, 32))

    with mock.patch("media.media_utils.genai") as genai:
        create_image("a scene", EPISODE, SEASON, SHOW, 1, image_generator=generator)

    genai.Client.assert_not_called()
    assert generator.call_count == 1
    assert (in_tmp_cwd / expected_path(1)).is_file()


def test_the_fake_also_answers_the_visual_coherence_callable_seam(tmp_path):
    """``__call__(prompt)`` is ``generate_image`` with the destination bound."""
    generator = FakeImageGenerator(directory=tmp_path, size=(16, 16))

    path = generator("an enhanced prompt")

    assert isinstance(path, str) and path, "the coherence seam requires a non-empty path"
    assert Path(path).is_file()
    assert generator.prompts == ["an enhanced prompt"]


# ---------------------------------------------------------------------------
# 3. Degradation, for every reason the generator can fail to exist
# ---------------------------------------------------------------------------


def test_a_failing_generator_still_leaves_a_usable_slide(in_tmp_cwd, without_api_key, caplog):
    """Generation blew up mid-call: the video step must still find a frame."""
    generator = FakeImageGenerator(fail_with=RuntimeError("upstream 503"))

    with caplog.at_level(logging.WARNING, logger="media.media_utils"):
        create_image("a scene", EPISODE, SEASON, SHOW, 0, image_generator=generator)

    written = in_tmp_cwd / expected_path(0)
    assert written.is_file()
    with Image.open(written) as image:
        assert image.size == PLACEHOLDER_SIZE, "this is not the placeholder title card"
    assert "upstream 503" in caplog.text, "the failure was swallowed without a reason"


def test_no_api_key_means_no_generator_and_a_logged_reason(in_tmp_cwd, without_api_key, caplog):
    """Reason one: nothing to authenticate with."""
    with pytest.raises(ImageGeneratorUnavailable, match="No Google API key found"):
        build_image_generator()

    with caplog.at_level(logging.WARNING, logger="media.media_utils"):
        create_image("a scene", EPISODE, SEASON, SHOW, 0)

    assert (in_tmp_cwd / expected_path(0)).is_file()
    assert "No Google API key found" in caplog.text


def test_a_missing_client_library_degrades_instead_of_exploding(in_tmp_cwd, monkeypatch, caplog):
    """Reason two: ``google-genai`` is not installed at all.

    This is the ``b6fde06`` lesson applied to images. An optional path has to be
    optional for every reason it can fail - not only for the one (a missing key)
    that was thought of first. Before this, the import sat at module scope, so a
    machine without the package could not import ``media.media_utils`` at all.
    """
    monkeypatch.setenv("GOOGLE_API_KEY", "a-real-looking-key")
    monkeypatch.setattr("media.media_utils.genai", None)
    monkeypatch.setattr("media.media_utils.types", None)

    with pytest.raises(ImageGeneratorUnavailable, match="google-genai is not installed"):
        build_image_generator()

    with caplog.at_level(logging.WARNING, logger="media.media_utils"):
        create_image("a scene", EPISODE, SEASON, SHOW, 0)

    assert (in_tmp_cwd / expected_path(0)).is_file()
    assert "google-genai is not installed" in caplog.text


def test_a_client_that_refuses_to_construct_degrades_too(in_tmp_cwd, monkeypatch, caplog):
    """Reason three: the library is there, the key is there, the SDK says no."""
    monkeypatch.setenv("GOOGLE_API_KEY", "a-real-looking-key")

    with mock.patch("media.media_utils.genai") as genai:
        genai.Client.side_effect = OSError("could not read credentials")
        with caplog.at_level(logging.WARNING, logger="media.media_utils"):
            create_image("a scene", EPISODE, SEASON, SHOW, 0)

    written = in_tmp_cwd / expected_path(0)
    assert written.is_file()
    with Image.open(written) as image:
        assert image.size == PLACEHOLDER_SIZE
    assert "could not read credentials" in caplog.text


# ---------------------------------------------------------------------------
# 4. A caller that injects nothing
# ---------------------------------------------------------------------------


def test_the_uninjected_path_renders_every_slide_with_no_key(
    in_tmp_cwd, without_api_key, unused_genai
):
    """No generator and no key still means real PNGs, one per sentence.

    The offline demo reaches the same degradation by a shorter route now: it
    builds a ``WorkflowOrchestrator``, which resolves one generator for the run
    (a stand-in, with no key) and forwards it. This is the shape left for
    callers that pass nothing at all.
    """
    sentences = ["first slide", "second slide", "third slide"]

    create_images(sentences, EPISODE, SEASON, SHOW)

    for index in range(len(sentences)):
        written = in_tmp_cwd / expected_path(index)
        assert written.is_file(), f"the video step will look for {written}"
        with Image.open(written) as image:
            assert image.size == PLACEHOLDER_SIZE
    unused_genai.Client.assert_not_called()


def test_the_demo_clears_credentials_that_moviepy_puts_back(tmp_path):
    """The offline demo's image guarantee survives a machine that has a key.

    ``scripts/demo.py`` pops the credential variables at import, but importing
    ``moviepy.config`` runs ``dotenv.load_dotenv()``, which reads the
    repository's ``.env`` and restores ``GOOGLE_API_KEY``. The demo therefore
    re-clears them after the heavy imports and then *checks* that no generator
    can be built. Run in a subprocess because that check is a process-wide
    environment assertion.
    """
    script = (
        "import scripts.demo as demo\n"
        "demo.enforce_offline_image_generation()\n"
        "from media.media_utils import build_image_generator, ImageGeneratorUnavailable\n"
        "try:\n"
        "    build_image_generator()\n"
        "except ImageGeneratorUnavailable:\n"
        "    print('STILL OFFLINE')\n"
    )
    environment = {**os.environ, "GOOGLE_API_KEY": "a-key-that-leaked-in"}

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parent.parent.parent,
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "no image generator can be built" in result.stdout
    assert "STILL OFFLINE" in result.stdout
