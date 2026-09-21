"""
``google-genai`` is optional for ``VideoGenerationAgent`` - in fact, not used.

``f2597bf`` made the package an optional import in ``media/media_utils.py`` and
said so in its commit message. The claim was false in practice: this module did
a bare ``from google import genai`` at module scope, and
``agents/workflow_orchestrator.py`` imports ``VideoGenerationAgent`` at module
scope, so importing the orchestrator - and therefore starting the pipeline or
the offline demo - still hard-required the package. ``requirements-demo.txt``
had to pin it for that reason alone.

Nothing this agent computes needs it. ``generate_optimized_images`` builds
prompt strings and ``adaptive_duration_calculation`` divides word counts; the
only reference was a Gemini client that no caller reads. So the import is now
guarded the way ``media/media_utils.py`` and ``agents/character_analysis_agent``
guard theirs, and the failure moved to the one place that genuinely needs the
package: ``VideoGenerationAgent.build_client``.

What these tests pin:

* the orchestrator - the whole import chain, not just this module - imports in
  a process where ``google.genai`` cannot be imported at all;
* the agent constructs there, and both of its methods work;
* the client request fails with a message naming the package and the install
  command, rather than an ``AttributeError`` from inside the SDK;
* a missing package is logged at construction, never raised.

The absence is simulated with a real ``sys.meta_path`` blocker in a subprocess
rather than by patching a module attribute, because the claim under test is
about *import time*: patching ``agents.video_agent.genai`` to ``None`` presumes
the import already succeeded, which is the exact thing that used to fail.
"""

import logging
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from agents.video_agent import (
    GENAI_AVAILABLE,
    GeminiClientUnavailable,
    VideoGenerationAgent,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Runs in a child interpreter with `google.genai` made unimportable. Anything
# that still reaches for the package raises ImportError, so a clean exit is the
# assertion. Printed markers let the failure message say how far it got.
_WITHOUT_GENAI = textwrap.dedent(
    """
    import sys


    class Blocker:
        def find_spec(self, fullname, path=None, target=None):
            if fullname == "google.genai" or fullname.startswith("google.genai."):
                raise ImportError(f"No module named {fullname!r} (blocked by the test)")
            return None


    for name in [n for n in sys.modules if n.split(".")[0:2] == ["google", "genai"]]:
        del sys.modules[name]
    sys.meta_path.insert(0, Blocker())

    try:
        from google import genai
    except ImportError:
        pass
    else:
        raise AssertionError("the blocker did not block google.genai")
    print("BLOCKED")

    import agents.workflow_orchestrator  # noqa: F401
    print("ORCHESTRATOR-IMPORTED")

    from agents.video_agent import GENAI_AVAILABLE, GeminiClientUnavailable
    from agents.video_agent import VideoGenerationAgent

    assert GENAI_AVAILABLE is False, "the availability flag should report the truth"

    agent = VideoGenerationAgent()
    assert agent.client is None, "no client is buildable without the package"
    print("AGENT-CONSTRUCTED")

    prompts = agent.generate_optimized_images(["a rooftop chase"], {"show": "Demo Show"})
    assert len(prompts) == 1 and "a rooftop chase" in prompts[0]
    assert agent.adaptive_duration_calculation(["one two", "three"], 12.0) == [8.0, 4.0]
    print("METHODS-WORK")

    try:
        agent.build_client()
    except GeminiClientUnavailable as exc:
        assert "google-genai" in str(exc) and "pip install google-genai" in str(exc)
    else:
        raise AssertionError("build_client must refuse without the package")
    print("CLIENT-REFUSED")
    """
)


@pytest.fixture
def without_genai(monkeypatch):
    """In-process stand-in for an uninstalled package, post-import."""
    monkeypatch.setattr("agents.video_agent.genai", None)
    monkeypatch.setattr("agents.video_agent._GENAI_IMPORT_ERROR", "No module named 'google.genai'")


def test_the_orchestrator_imports_with_google_genai_uninstallable():
    """The claim ``f2597bf`` made, finally true: no package, no ImportError.

    Before the guard this subprocess died on ``from google import genai`` at
    ``agents/video_agent.py`` line 9, reached through the orchestrator's
    module-scope ``from agents.video_agent import VideoGenerationAgent``.
    """
    result = subprocess.run(
        [sys.executable, "-c", _WITHOUT_GENAI],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=90,
    )

    assert result.returncode == 0, (
        f"a process without google-genai could not get through the import chain:\n"
        f"{result.stdout}\n{result.stderr}"
    )
    for marker in (
        "BLOCKED",
        "ORCHESTRATOR-IMPORTED",
        "AGENT-CONSTRUCTED",
        "METHODS-WORK",
        "CLIENT-REFUSED",
    ):
        assert marker in result.stdout, f"{marker} missing from:\n{result.stdout}"


def test_build_client_names_the_package_and_how_to_install_it(without_genai):
    """At the point of use, with a message that tells the caller what to do.

    The failure is deliberately not an ``AttributeError`` raised deep inside a
    call on ``None``, which is what a bare ``genai = None`` fallback would have
    produced.
    """
    agent = VideoGenerationAgent()

    with pytest.raises(GeminiClientUnavailable) as excinfo:
        agent.build_client()

    message = str(excinfo.value)
    assert "google-genai is not installed" in message
    assert "pip install google-genai" in message


def test_a_missing_package_is_logged_at_construction_not_raised(without_genai, caplog):
    """Constructing the agent is not the point of use, so it must not fail."""
    with caplog.at_level(logging.WARNING, logger="agents.video_agent"):
        agent = VideoGenerationAgent()

    assert agent.client is None
    assert "google-genai is not installed" in caplog.text


def test_both_methods_work_without_the_package(without_genai):
    """The two things the orchestrator actually calls need nothing from Google.

    ``agents/workflow_orchestrator.py`` uses exactly these two methods on the
    agent (the fallback prompt at the coherence step, and the fallback timing at
    step 6). Both are pure: style text plus the scene, and word counts divided
    into the audio length with a 2 second floor.
    """
    agent = VideoGenerationAgent()

    prompts = agent.generate_optimized_images(["Naruto storms the outpost"], {"show": "Naruto"})
    assert len(prompts) == 1
    assert "Naruto storms the outpost" in prompts[0]
    assert "consistent anime art style for Naruto" in prompts[0]

    # 2 words and 1 word out of 3, over 12 seconds.
    assert agent.adaptive_duration_calculation(["one two", "three"], 12.0) == [8.0, 4.0]
    # The 2 second floor still applies.
    assert agent.adaptive_duration_calculation(["one", "two"], 1.0) == [2.0, 2.0]


def test_the_availability_flag_matches_this_environment():
    """The flag is derived from the import, never asserted to a fixed value.

    Pinned so that the flag cannot drift into a hand-maintained constant; the
    subprocess above covers the uninstalled direction.
    """
    try:
        from google import genai  # noqa: F401

        importable = True
    except ImportError:
        importable = False

    assert GENAI_AVAILABLE is importable
