#!/usr/bin/env python3
"""
Regression tests for Google AI client initialization in ``media/media_utils.py``.

The original bugs were: constructing ``genai.Client()`` with no API key, calling
``generate_content`` for image generation instead of ``generate_images``, and
passing deprecated model names and config parameters. These tests pin the
current, correct usage and the fallbacks that run when the API is unavailable.

This module used to be a single ``test_google_ai_client_fixes()`` that wrapped
six checks in ``try/except``, printed a tick or a cross, and *returned* a bool -
which pytest ignores, so the module reported as one passing test while four of
its six checks failed unseen. Two of those failures were artifacts of the mocks
rather than product faults:

* Patching ``media.media_utils.Image`` left ``create_placeholder_image``'s real
  ``PIL.ImageDraw`` drawing on a ``Mock``, so ``draw.textbbox(...)[2]`` raised
  ``'Mock' object is not subscriptable`` / ``'>' not supported between
  MagicMock and int``. Nothing like that can happen with the real PIL, so the
  tests below let PIL run for real inside ``tmp_path`` and assert on the file
  that lands on disk.
* Patching ``media.media_utils.wave`` *and* ``os.makedirs`` meant the silent
  audio fallback (which had its own ``import wave``) wrote to a directory that
  the patched ``makedirs`` never created. The ``FileNotFoundError`` surfaced as
  ``'Wave_write' object has no attribute '_file'`` from ``Wave_write.__del__``.
  The redundant local import has been removed; these tests write real WAV files.

One check was simply stale: it asserted ``genai.Client(api_key=None)`` when the
key is missing. ``create_image`` now refuses to build a client without a key,
which is the better behaviour, so the test asserts that instead.
"""

import sys
import unittest.mock as mock
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

SHOW = "Test Show"
SEASON = "1"
EPISODE = "1"
EXPECTED_IMAGE = Path(SHOW) / f"Season{SEASON}" / f"Episode{EPISODE}" / f"{SHOW}_{EPISODE}_0.png"
EXPECTED_AUDIO = Path(SHOW) / f"Season{SEASON}" / f"Episode{EPISODE}" / f"{SHOW}_{EPISODE}.wav"


@pytest.fixture
def in_tmp_cwd(tmp_path, monkeypatch):
    """Run in a throwaway working directory: media paths are relative to cwd."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def with_api_key(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")


@pytest.fixture
def without_api_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)


@pytest.fixture
def fake_genai():
    """Patch the ``genai``/``types`` module objects ``media_utils`` imported."""
    with (
        mock.patch("media.media_utils.genai") as genai,
        mock.patch("media.media_utils.types") as types,
    ):
        yield genai, types


def _image_response(genai, image_path: Path):
    """Wire ``generate_images`` to return one image that really saves itself."""
    generated = mock.Mock()
    generated.image.save.side_effect = lambda path: Image.new("RGB", (8, 8)).save(path)
    response = mock.Mock()
    response.generated_images = [generated]
    genai.Client.return_value.models.generate_images.return_value = response
    return response


def test_image_generation_uses_an_api_keyed_client(in_tmp_cwd, with_api_key, fake_genai):
    """The client is built with the key from the environment, per call."""
    from media.media_utils import create_image

    genai, _types = fake_genai
    _image_response(genai, in_tmp_cwd / EXPECTED_IMAGE)

    create_image("test prompt", EPISODE, SEASON, SHOW, 0)

    genai.Client.assert_called_with(api_key="test-key")
    genai.Client.return_value.models.generate_images.assert_called_once()
    assert (in_tmp_cwd / EXPECTED_IMAGE).is_file(), "the generated image was not saved"


def test_image_generation_calls_generate_images_with_the_imagen_model(
    in_tmp_cwd, with_api_key, fake_genai
):
    """``generate_images``, not ``generate_content``, and the current model id."""
    from media.media_utils import create_image

    genai, types = fake_genai
    _image_response(genai, in_tmp_cwd / EXPECTED_IMAGE)

    create_image("test prompt", EPISODE, SEASON, SHOW, 0)

    models = genai.Client.return_value.models
    models.generate_content.assert_not_called()
    kwargs = models.generate_images.call_args.kwargs
    assert kwargs["model"] == "imagen-3.0-generate-002"
    assert kwargs["prompt"] == "test prompt"
    types.GenerateImagesConfig.assert_called_once_with(
        number_of_images=1, output_mime_type="image/png"
    )


def test_missing_api_key_skips_the_client_and_writes_a_placeholder(
    in_tmp_cwd, without_api_key, fake_genai
):
    """No key means no client at all - and a real placeholder image instead."""
    from media.media_utils import create_image

    genai, _types = fake_genai

    create_image("test prompt", EPISODE, SEASON, SHOW, 0)

    genai.Client.assert_not_called()
    placeholder = in_tmp_cwd / EXPECTED_IMAGE
    assert placeholder.is_file(), "no placeholder image was written"
    with Image.open(placeholder) as written:
        assert written.size == (1024, 768)


def test_an_empty_response_falls_back_to_a_placeholder(in_tmp_cwd, with_api_key, fake_genai):
    """A call that returns no images must still leave a usable slide behind."""
    from media.media_utils import create_image

    genai, _types = fake_genai
    response = mock.Mock()
    response.generated_images = []
    genai.Client.return_value.models.generate_images.return_value = response

    create_image("test prompt", EPISODE, SEASON, SHOW, 0)

    placeholder = in_tmp_cwd / EXPECTED_IMAGE
    assert placeholder.is_file(), "no placeholder image was written"
    with Image.open(placeholder) as written:
        assert written.size == (1024, 768)


def test_audio_generation_uses_an_api_keyed_client_and_the_tts_model(
    in_tmp_cwd, with_api_key, fake_genai
):
    """The TTS path writes the returned PCM and reports the real duration."""
    from media.media_utils import wave_file

    genai, _types = fake_genai
    one_second_of_pcm = b"\x00\x00" * 24000
    # Built out of plain objects rather than Mocks: the production code indexes
    # into `candidates` and `parts`, which a Mock does not support.
    part = SimpleNamespace(inline_data=SimpleNamespace(data=one_second_of_pcm))
    response = SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=[part]))])
    genai.Client.return_value.models.generate_content.return_value = response

    duration = wave_file(SHOW, SEASON, EPISODE, "test content")

    genai.Client.assert_called_with(api_key="test-key")
    assert (
        genai.Client.return_value.models.generate_content.call_args.kwargs["model"]
        == "gemini-2.5-flash-preview-tts"
    )
    audio = in_tmp_cwd / EXPECTED_AUDIO
    assert audio.is_file(), "no audio file was written"
    with wave.open(str(audio)) as written:
        assert written.getnchannels() == 1
        assert written.getsampwidth() == 2
        assert written.getframerate() == 24000
    assert duration == pytest.approx(1.0)


def test_failed_tts_falls_back_to_a_real_silent_track(in_tmp_cwd, with_api_key, fake_genai):
    """``create_silent_audio_fallback`` is wired into the live TTS-failure path.

    It must leave a WAV that MoviePy can actually open, whose real duration
    matches the duration handed back for video timing.
    """
    from media.media_utils import get_wav_duration, wave_file

    genai, _types = fake_genai
    genai.Client.return_value.models.generate_content.side_effect = RuntimeError(
        "429 RESOURCE_EXHAUSTED"
    )

    duration = wave_file(SHOW, SEASON, EPISODE, "a short line of narration")

    audio = in_tmp_cwd / EXPECTED_AUDIO
    assert audio.is_file(), "the TTS fallback left no audio file behind"
    assert duration >= 60.0, "the fallback floor of one minute is gone"
    assert get_wav_duration(str(audio)) == pytest.approx(duration, abs=0.01), (
        "the reported duration does not match the file, so video timing will drift"
    )


def test_the_silent_fallback_honours_the_requested_sample_rate(in_tmp_cwd):
    """A non-default rate must reach the fallback, or the duration is wrong."""
    from media.media_utils import create_silent_audio_fallback, get_wav_duration

    path = in_tmp_cwd / "silence.wav"
    duration = create_silent_audio_fallback(str(path), "one two three", sample_rate=8000)

    with wave.open(str(path)) as written:
        assert written.getframerate() == 8000
    assert get_wav_duration(str(path)) == pytest.approx(duration, abs=0.01)


if __name__ == "__main__":
    # `scripts/run_regression_suite.py` runs this module as a script. Delegating
    # to pytest keeps a direct run and a collected run executing the same checks
    # and reporting the same exit status.
    raise SystemExit(pytest.main([__file__, *sys.argv[1:]]))
