#!/usr/bin/env python3
"""
Regression tests for file path consistency in media generation.

``create_image`` writes a slide, ``wave_file`` writes the narration and
``mp4_file_enhanced`` reads both back to assemble the video. The three build
their paths independently, so a change to one naming scheme silently produces a
video that looks for images that were never written there. These tests pin the
shared layout:

    {show}/Season{season}/Episode{episode}/{show}_{episode}_{index}.png
    {show}/Season{season}/Episode{episode}/{show}_{episode}.wav

This module used to be a single ``test_file_path_consistency()`` that wrapped
five checks in ``try/except``, printed a tick or a cross, and *returned* a bool.
pytest ignores a return value, so the module reported as one passing test while
four of its five checks were failing. Those four failures were artifacts of the
mocks, not product faults: the module patched ``media.media_utils.Image`` while
``create_placeholder_image`` still used the real ``PIL.ImageDraw``, so
``draw.textbbox(...)[2]`` raised ``'Mock' object is not subscriptable`` (or
``'>' not supported between MagicMock and int``) before any path was recorded.

The checks below no longer mock PIL, ``wave`` or ``os.makedirs`` at all. They
run inside ``tmp_path`` and assert against the files that actually land on
disk, which is the only thing the video assembly step cares about. Only MoviePy
is stubbed, so the video does not have to be rendered to learn which paths it
asks for.
"""

import sys
import unittest.mock as mock
from pathlib import Path

import pytest

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

SHOW = "Test Show"
SEASON = "1"


def episode_dir(episode: str) -> Path:
    return Path(SHOW) / f"Season{SEASON}" / f"Episode{episode}"


@pytest.fixture
def in_tmp_cwd(tmp_path, monkeypatch):
    """Media paths are relative to the working directory, so move into tmp."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def no_api_key(monkeypatch):
    """Force the offline path: placeholder images and silent narration."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)


@pytest.fixture
def captured_video_paths():
    """Stub MoviePy and record every image path the assembly step opens."""
    paths: list[str] = []

    def record(path):
        paths.append(path)
        return mock.Mock()

    with (
        mock.patch("media.media_utils.ImageClip", side_effect=record),
        mock.patch("media.media_utils.VideoFileClip"),
        mock.patch("media.media_utils.AudioFileClip"),
        mock.patch("media.media_utils.concatenate_videoclips"),
    ):
        yield paths


@pytest.mark.parametrize(
    ("episode", "label"),
    [("1", "episode"), ("Season_1", "season summary")],
    ids=["episode-level", "season-level"],
)
def test_the_video_reads_the_images_that_were_written(
    in_tmp_cwd, no_api_key, captured_video_paths, episode, label
):
    """The path ``create_image`` writes is the path ``mp4_file_enhanced`` opens.

    Season summaries reuse the same functions with ``episode="Season_1"``, so
    both shapes are checked.
    """
    from media.media_utils import create_image, mp4_file_enhanced, wave_file

    create_image("a test prompt", episode, SEASON, SHOW, 0)
    wave_file(SHOW, SEASON, episode, "narration for the slide")

    written = in_tmp_cwd / episode_dir(episode) / f"{SHOW}_{episode}_0.png"
    assert written.is_file(), f"no {label} image was written to {written}"

    mp4_file_enhanced(SHOW, SEASON, episode, ["test sentence"], [1.0])

    assert captured_video_paths, "the video step opened no images at all"
    assert captured_video_paths[0] == str(episode_dir(episode) / f"{SHOW}_{episode}_0.png")
    assert (in_tmp_cwd / captured_video_paths[0]).is_file(), (
        f"the video looks for {captured_video_paths[0]}, which no step wrote"
    )


def test_the_video_reads_one_image_per_sentence_in_order(
    in_tmp_cwd, no_api_key, captured_video_paths
):
    """Index ``i`` of the slide list must map to ``..._{i}.png``."""
    from media.media_utils import create_images, mp4_file_enhanced, wave_file

    sentences = ["first slide", "second slide", "third slide"]
    create_images(sentences, "1", SEASON, SHOW)
    wave_file(SHOW, SEASON, "1", "narration")

    mp4_file_enhanced(SHOW, SEASON, "1", sentences, [1.0, 1.0, 1.0])

    assert captured_video_paths == [
        str(episode_dir("1") / f"{SHOW}_1_{index}.png") for index in range(len(sentences))
    ]
    for path in captured_video_paths:
        assert (in_tmp_cwd / path).is_file(), f"the video looks for {path}, which was never written"


def test_create_images_passes_its_arguments_through_in_order():
    """``create_images`` fans out to ``create_image``; the order is positional."""
    from media.media_utils import create_images

    with mock.patch("media.media_utils.create_image") as create_image:
        create_images(["sentence 1", "sentence 2"], "1", SEASON, SHOW)

    assert [call.args for call in create_image.call_args_list] == [
        ("sentence 1", "1", SEASON, SHOW, 0),
        ("sentence 2", "1", SEASON, SHOW, 1),
    ]


def test_image_and_audio_share_one_episode_directory(in_tmp_cwd, no_api_key):
    """Both media functions must build the same directory, not two near-misses."""
    from media.media_utils import create_image, wave_file

    create_image("a test prompt", "1", SEASON, SHOW, 5)
    wave_file(SHOW, SEASON, "1", "test content")

    expected = in_tmp_cwd / episode_dir("1")
    assert sorted(path.name for path in expected.iterdir()) == [
        f"{SHOW}_1.wav",
        f"{SHOW}_1_5.png",
    ]


if __name__ == "__main__":
    # `scripts/run_regression_suite.py` runs this module as a script. Delegating
    # to pytest keeps a direct run and a collected run executing the same checks
    # and reporting the same exit status.
    raise SystemExit(pytest.main([__file__, *sys.argv[1:]]))
