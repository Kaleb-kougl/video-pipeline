#!/usr/bin/env python3
"""
Offline end-to-end demo: transcript in, playable MP4 out, no API key, no network.

Why this exists
---------------
The production pipeline needs a Google AI Studio key (Gemini for summarisation,
Imagen for frames, Gemini TTS for narration) and a ~1.1 GB ML install for the
ChromaDB character store. A reviewer should not have to supply either to find
out whether the project works. This script drives the *real*
``WorkflowOrchestrator`` with only those paid/network boundaries replaced, and
renders a genuine MP4 through the real MoviePy/ffmpeg path.

What is REAL (production code, actually executed)
-------------------------------------------------
* ``utils/web_utils.py``  - BeautifulSoup parsing of the episode page
* ``agents/content_agent.py`` - content extraction and validation
* ``agents/quality_agent.py`` - content quality validation
* ``core/database.py``    - SQLite persistence (a real .db file is written)
* ``core/character_episode_enhancer.py`` - character-weighted scene timing
* ``core/adaptive_quality_manager.py``   - resource-aware quality profile
* ``core/visual_coherence_manager.py``   - ``build_coherent_prompt`` (no API)
* ``media/media_utils.py::create_images`` - real PIL frame rendering via the
  production ``create_placeholder_image`` fallback
* ``media/media_utils.py::mp4_file_enhanced`` - real MoviePy + ffmpeg encode

What is STUBBED (external paid / network services only)
-------------------------------------------------------
* HTTP           - ``requests.get`` returns a canned page built from the
                   committed ``demo/sample_transcript.txt``. Nothing is scraped.
* Gemini chat    - ``init_chat_model`` returns a fake model that replays
                   ``demo/canned_llm_response.json``. No key, no call.
* Imagen         - not stubbed by this script: ``create_image`` sees no
                   ``GOOGLE_API_KEY`` and takes its own placeholder branch.
* Gemini TTS     - ``wave_file`` is replaced with a local synthesiser that
                   writes a real WAV. (The production no-key fallback writes
                   *silence*; a tone is used here so the reviewer can confirm
                   the MP4 really carries an audio stream.)
* ChromaDB +
  sentence-transformers - ``CharacterAnalysisAgent`` is replaced with a
                   stand-in replaying ``demo/canned_character_profiles.json``.

Run it with ``make demo``.
"""

import asyncio
import json
import math
import os
import shutil
import socket
import struct
import sys
import wave
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DEMO_DIR = PROJECT_ROOT / "demo"
# Overridable so the container can render straight into a bind-mounted volume.
OUTPUT_DIR = Path(os.environ.get("DEMO_OUTPUT_DIR") or (PROJECT_ROOT / "demo_output")).resolve()
EPISODE_URL = "https://example.invalid/neon-lantern-brigade/season-1/episode-3"

# The demo must never reach a paid service, even on a machine that has a key
# configured. Clear the credentials the pipeline looks for *before* importing
# anything that reads them, so create_image/wave_file take their offline paths.
for _var in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS"):
    os.environ.pop(_var, None)


# ---------------------------------------------------------------------------
# Network guard - makes "no network" a checked claim, not a promise
# ---------------------------------------------------------------------------


class DemoMadeANetworkCall(RuntimeError):
    """Raised if any code path tries to open an off-box socket."""


def block_outbound_network() -> None:
    """Let loopback through (nothing needs it, but ffmpeg pipes are noisy) and
    fail loudly on anything else."""
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def _is_local(address: object) -> bool:
        if not isinstance(address, tuple) or not address:
            return True  # AF_UNIX and friends are on-box by definition
        host = str(address[0])
        return host in {"127.0.0.1", "::1", "localhost", "0.0.0.0"}

    def guarded_connect(self, address, *args, **kwargs):  # type: ignore[no-untyped-def]
        if not _is_local(address):
            raise DemoMadeANetworkCall(
                f"The offline demo tried to connect to {address!r}. "
                "That is a bug in the demo's stubs, not a missing API key."
            )
        return real_connect(self, address, *args, **kwargs)

    def guarded_connect_ex(self, address, *args, **kwargs):  # type: ignore[no-untyped-def]
        if not _is_local(address):
            raise DemoMadeANetworkCall(f"The offline demo tried to connect to {address!r}.")
        return real_connect_ex(self, address, *args, **kwargs)

    socket.socket.connect = guarded_connect  # type: ignore[method-assign]
    socket.socket.connect_ex = guarded_connect_ex  # type: ignore[method-assign]


# ---------------------------------------------------------------------------
# Stand-ins for the external services
# ---------------------------------------------------------------------------


class CannedHTTPResponse:
    """Just enough of ``requests.Response`` for ``utils.web_utils.get_html_content``."""

    def __init__(self, text: str):
        self.text = text
        self.status_code = 200

    def raise_for_status(self) -> None:
        return None


class CannedStructuredModel:
    """What ``model.with_structured_output(schema)`` returns."""

    def __init__(self, response: object):
        self.response = response
        self.prompts: list[object] = []

    def invoke(self, prompt: object) -> object:
        self.prompts.append(prompt)
        return self.response


class CannedChatModel:
    """Replays a recorded Gemini response. No key, no provider package, no call."""

    def __init__(self, structured_response: object):
        self.structured_response = structured_response
        self.prompts: list[object] = []
        self.structured_model: CannedStructuredModel | None = None

    def invoke(self, prompt: object) -> str:
        self.prompts.append(prompt)
        return "Canned offline analysis."

    def with_structured_output(self, schema: object) -> CannedStructuredModel:
        self.structured_model = CannedStructuredModel(self.structured_response)
        return self.structured_model


class CannedCharacterAnalysisAgent:
    """Stand-in for the ChromaDB + sentence-transformers backed agent."""

    def __init__(self, *args, profiles: dict | None = None, **kwargs):
        self.profiles = profiles or {}
        self.calls: list[tuple] = []

    def analyze_episode_characters(self, show_name, season, episode, transcript):  # noqa: ANN001
        self.calls.append((show_name, season, episode, transcript))
        return self.profiles


def synthesise_narration(
    show: str,
    season: str,
    episode: str,
    contents: str,
    target_seconds: float,
    sample_rate: int = 24000,
    **_ignored,
) -> float:
    """
    Stand-in for Gemini TTS that writes a *real* WAV to the path the production
    encoder will later read.

    The production no-key fallback (``create_silent_audio_fallback``) writes
    pure silence, which makes it impossible to tell a working audio pipeline
    from a broken one by watching the output. This writes a quiet arpeggio of
    the same length instead, so the rendered MP4 demonstrably carries an audio
    stream. It is a stub, and the banner says so.
    """
    episode_dir = Path(f"{show}/Season{season}/Episode{episode}")
    episode_dir.mkdir(parents=True, exist_ok=True)
    file_name = episode_dir / f"{show}_{episode}.wav"

    notes = [220.0, 277.18, 329.63, 277.18]  # A3 / C#4 / E4 / C#4
    seconds_per_note = 1.25
    amplitude = 3500  # ~10% of full scale: present, not shrill
    total_frames = int(target_seconds * sample_rate)

    frames = bytearray()
    for frame in range(total_frames):
        t = frame / sample_rate
        freq = notes[int(t / seconds_per_note) % len(notes)]
        # Short attack/release envelope per note, so it reads as narration-ish
        # pacing rather than one continuous drone.
        phase_in_note = (t % seconds_per_note) / seconds_per_note
        envelope = math.sin(math.pi * phase_in_note) ** 2
        value = int(amplitude * envelope * math.sin(2 * math.pi * freq * t))
        frames += struct.pack("<h", value)

    with wave.open(str(file_name), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(bytes(frames))

    print(f"   [stub] synthesised {target_seconds:.1f}s narration track -> {file_name}")
    return target_seconds


def render_branding_intro(show: str, width: int = 1024, height: int = 768) -> Path:
    """
    Render the channel intro clip ``mp4_file_enhanced`` expects at
    ``{show}/tldr_mha_intro.mp4``.

    In production this is a hand-made branding asset. Generating it here keeps
    the repo free of committed binaries, and it is a real MoviePy encode, so it
    also proves ffmpeg is wired up before the main render starts.
    """
    from moviepy import ImageClip
    from PIL import Image, ImageDraw

    show_dir = Path(show)
    show_dir.mkdir(parents=True, exist_ok=True)
    frame_path = show_dir / "_intro_frame.png"
    intro_path = show_dir / "tldr_mha_intro.mp4"

    image = Image.new("RGB", (width, height), "#101024")
    draw = ImageDraw.Draw(image)
    for y in range(height):
        shade = int(16 + (y / height) * 60)
        draw.line([(0, y), (width, y)], fill=(shade, shade, min(shade + 30, 255)))

    font = _load_font(64)
    small = _load_font(28)
    for text, y, fill, chosen in (
        ("TLDR Media", 280, "white", font),
        (show, 380, "#9ad7ff", small),
        ("offline demo render - no API key, no network", 440, "#8a8aa8", small),
    ):
        bbox = draw.textbbox((0, 0), text, font=chosen)
        draw.text(((width - (bbox[2] - bbox[0])) // 2, y), text, fill=fill, font=chosen)

    image.save(frame_path)
    clip = ImageClip(str(frame_path)).with_duration(2.0)
    clip.write_videofile(str(intro_path), fps=24, logger=None)
    clip.close()
    frame_path.unlink(missing_ok=True)
    return intro_path


def _load_font(size: int):  # noqa: ANN202
    """Best-effort truetype lookup; PIL's bitmap default is the last resort."""
    from PIL import ImageFont

    candidates = (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    )
    for candidate in candidates:
        if Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

REAL = [
    "HTML parsing (BeautifulSoup, utils/web_utils.py)",
    "Content extraction + quality validation (agents/)",
    "SQLite persistence (core/database.py) - a real .db is written",
    "Character-weighted scene timing (core/character_episode_enhancer.py)",
    "Adaptive quality profile selection (core/adaptive_quality_manager.py)",
    "Visual-coherence prompt construction (core/visual_coherence_manager.py)",
    "Frame rendering (media/media_utils.py placeholder path, PIL)",
    "Video encode (media/media_utils.py -> MoviePy -> ffmpeg)",
]

STUBBED = [
    "HTTP scrape          -> demo/sample_transcript.txt wrapped in a canned page",
    "Gemini summarisation -> demo/canned_llm_response.json",
    "Imagen frames        -> production no-key fallback (captioned title cards)",
    "Gemini TTS narration -> locally synthesised tone track (real WAV)",
    "ChromaDB characters  -> demo/canned_character_profiles.json",
]


def banner() -> None:
    print("=" * 78)
    print("  Anime Video Generator - OFFLINE DEMO")
    print("  No API key is used. No network call is permitted (enforced, not promised).")
    print("=" * 78)
    print("\n  REAL - production code, actually executed:")
    for item in REAL:
        print(f"    + {item}")
    print("\n  STUBBED - external paid / network services only:")
    for item in STUBBED:
        print(f"    ~ {item}")
    print(
        "\n  This is NOT a full run: the frames are captioned title cards, not\n"
        "  generated artwork, and the audio is a synthesised tone, not narration.\n"
        "  Everything between those boundaries is the shipping pipeline.\n"
    )
    print("-" * 78)


def describe_artifact(video_path: Path) -> None:
    from moviepy import VideoFileClip

    size_mb = video_path.stat().st_size / (1024 * 1024)
    with VideoFileClip(str(video_path)) as clip:
        duration = clip.duration
        width, height = clip.size
        fps = clip.fps
        has_audio = clip.audio is not None
    print("-" * 78)
    print("  DONE. Playable MP4 written:\n")
    print(f"    {video_path}")
    print(f"      duration : {duration:.2f}s")
    print(f"      size     : {size_mb:.2f} MB")
    print(f"      video    : {width}x{height} @ {fps:g} fps")
    print(f"      audio    : {'present (AAC)' if has_audio else 'MISSING'}")
    print("\n  Open it with any player, e.g.:")
    print(f"    open '{video_path}'        # macOS")
    print(f"    xdg-open '{video_path}'    # Linux")
    print("-" * 78)


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


async def run_demo() -> Path:
    from agents.workflow_orchestrator import WorkflowOrchestrator
    from core.schemas import Episode_Summary_Schema

    canned = json.loads((DEMO_DIR / "canned_llm_response.json").read_text())
    canned.pop("_comment", None)
    summary = Episode_Summary_Schema(**canned)

    profiles = json.loads((DEMO_DIR / "canned_character_profiles.json").read_text())
    profiles.pop("_comment", None)

    transcript = (DEMO_DIR / "sample_transcript.txt").read_text()
    page = (
        "<html><body>"
        f"<h1>{summary.show} - Season {summary.season}, Episode {summary.episode}</h1>"
        f'<div class="full-script">{transcript}</div>'
        "</body></html>"
    )

    # The orchestrator gives every scene a 3.0s base duration before the
    # character enhancer adjusts it, so this is the right ballpark for the
    # narration length. Any drift is absorbed by the encoder.
    target_audio_seconds = 3.0 * len(summary.plot_points)

    def wave_file_stub(show, season, episode, contents, **kwargs):  # noqa: ANN001
        return synthesise_narration(
            show, season, episode, contents, target_seconds=target_audio_seconds
        )

    print("  [1/4] Rendering the branding intro clip (real MoviePy encode)...")
    render_branding_intro(summary.show)

    print("  [2/4] Driving WorkflowOrchestrator.process_episode with stubbed boundaries...")
    with (
        patch(
            "agents.workflow_orchestrator.init_chat_model",
            return_value=CannedChatModel(summary),
        ),
        patch(
            "agents.workflow_orchestrator.CharacterAnalysisAgent",
            return_value=CannedCharacterAnalysisAgent(profiles=profiles["profiles"]),
        ),
        patch("utils.web_utils.requests.get", return_value=CannedHTTPResponse(page)),
        patch("agents.workflow_orchestrator.wave_file", side_effect=wave_file_stub),
    ):
        orchestrator = WorkflowOrchestrator(db_path="demo.db")
        result = await orchestrator.process_episode(EPISODE_URL, summary.show)

    if not result["success"]:
        raise SystemExit(f"\n  DEMO FAILED: {result['error']}\n")

    print("  [3/4] Pipeline reported success; verifying persisted state...")
    stored = orchestrator.db.get_episode(summary.show, summary.season, summary.episode)
    if stored is None:
        raise SystemExit("\n  DEMO FAILED: nothing was persisted to SQLite.\n")
    print(f"        SQLite row stored, transcript {len(stored['transcript']):,} chars")

    print("  [4/4] Locating the rendered MP4...")
    video_path = (
        Path(summary.show)
        / f"Season{summary.season}"
        / f"Episode{summary.episode}"
        / f"{summary.show}_{summary.season}_{summary.episode}.mp4"
    )
    if not video_path.exists():
        raise SystemExit(f"\n  DEMO FAILED: expected {video_path} to exist.\n")
    return video_path.resolve()


def main() -> int:
    banner()
    block_outbound_network()

    # Empty the directory's *contents* rather than the directory itself: in the
    # container it is a bind-mounted volume, which cannot be unlinked.
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for entry in OUTPUT_DIR.iterdir():
        shutil.rmtree(entry) if entry.is_dir() else entry.unlink()

    previous_cwd = Path.cwd()
    # create_image / wave_file / mp4_file_enhanced all build relative paths from
    # the process cwd, so the whole run is confined to demo_output/ this way
    # without touching media/media_utils.py.
    os.chdir(OUTPUT_DIR)
    try:
        video_path = asyncio.run(run_demo())
    finally:
        os.chdir(previous_cwd)

    describe_artifact(video_path)
    print(f"  Everything the demo wrote lives under: {OUTPUT_DIR}")
    print("  That directory is gitignored and safe to delete.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
