"""
The orchestrator's telemetry boundaries.

``core/telemetry.py`` is tested on its own; this file pins the *placement* of
the instrumentation, which is the part that silently rots. If someone adds a
stage to ``generate_all_media`` or moves a call out of a timed block, the run
report quietly stops describing the run - and a timing report nobody can trust
is worse than none, because it still looks authoritative.

It also checks the two things instrumentation must never do: change what a run
returns, and turn a working pipeline into a broken one when telemetry is off.
"""

import sys
from pathlib import Path
from typing import Any

import pytest

project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from agents.workflow_orchestrator import WorkflowOrchestrator  # noqa: E402
from core.telemetry import RunTelemetry  # noqa: E402

#: Every stage `process_episode` is expected to time, in order. Written out
#: rather than derived, so a change to the pipeline has to be a change here too.
EXPECTED_STAGES = [
    "content_extraction",
    "summarization",
    "persistence",
    "character_enrichment",
    "quality_profile",
    "prompt_construction",
    "image_generation",
    "audio_synthesis",
    "video_encode",
]


class StubContentAgent:
    def extract_and_analyze(self, url: str) -> dict[str, Any]:
        return {"success": True, "transcript": "NARUTO: believe it.", "analysis": ""}


class StubCharacterEnhancer:
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
    def __init__(self) -> None:
        self.recorded: list[dict[str, Any]] = []

    async def select_quality_profile(self, context: str, deadline: Any) -> StubQualityProfile:
        return StubQualityProfile()

    def record_quality_metrics(self, profile: Any, metrics: dict[str, Any]) -> None:
        self.recorded.append(metrics)


class StubCharacterAnalyzer:
    def analyze_episode_characters(
        self, show_name: str, season: Any, episode: Any, transcript: str
    ) -> dict[str, Any]:
        return {}


@pytest.fixture
def orchestrator(database_manager, fake_chat_model, monkeypatch):
    """A real orchestrator whose media calls are recorded rather than performed."""
    monkeypatch.setattr("agents.workflow_orchestrator.create_images", lambda *a, **k: None)
    monkeypatch.setattr("agents.workflow_orchestrator.wave_file", lambda **k: 12.0)
    monkeypatch.setattr("agents.workflow_orchestrator.mp4_file_enhanced", lambda **k: None)

    return WorkflowOrchestrator(
        db=database_manager,
        model=fake_chat_model,
        content_agent=StubContentAgent(),
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


async def test_a_run_times_every_pipeline_stage_in_order(orchestrator):
    result = await orchestrator.process_episode("https://example.invalid/ep", "Naruto")

    assert result["success"] is True, result.get("error")
    assert [s.name for s in orchestrator.telemetry.stages] == EXPECTED_STAGES
    assert all(s.ok for s in orchestrator.telemetry.stages)

    # The stage total cannot exceed the run it is a breakdown of.
    wall = orchestrator.telemetry.run_wall_seconds
    assert wall is not None
    assert orchestrator.telemetry.measured_seconds <= wall + 1e-6


async def test_the_result_payload_carries_the_telemetry(orchestrator):
    result = await orchestrator.process_episode("https://example.invalid/ep", "Naruto")

    payload = result["telemetry"]
    assert [s["stage"] for s in payload["stages"]] == EXPECTED_STAGES
    assert payload["wall_seconds"] is not None
    # Offline there is no provider response, so tokens must read as unavailable
    # rather than as zero.
    assert payload["tokens"]["input"] is None
    assert payload["cost"]["amount"] is None


async def test_a_failed_run_still_reports_the_stages_that_ran(orchestrator, monkeypatch):
    def explode(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("encoder unavailable")

    monkeypatch.setattr("agents.workflow_orchestrator.mp4_file_enhanced", explode)

    result = await orchestrator.process_episode("https://example.invalid/ep", "Naruto")

    assert result["success"] is False
    stages = orchestrator.telemetry.stages
    assert [s.name for s in stages] == EXPECTED_STAGES
    assert stages[-1].name == "video_encode" and stages[-1].ok is False
    assert "encoder unavailable" in (stages[-1].error or "")


async def test_the_pipeline_still_runs_with_telemetry_disabled(
    database_manager, fake_chat_model, monkeypatch
):
    """``ANIME_TELEMETRY=0`` must cost the run nothing but the report."""
    monkeypatch.setattr("agents.workflow_orchestrator.create_images", lambda *a, **k: None)
    monkeypatch.setattr("agents.workflow_orchestrator.wave_file", lambda **k: 12.0)
    monkeypatch.setattr("agents.workflow_orchestrator.mp4_file_enhanced", lambda **k: None)

    orchestrator = WorkflowOrchestrator(
        db=database_manager,
        model=fake_chat_model,
        content_agent=StubContentAgent(),
        character_analysis_agent=StubCharacterAnalyzer(),
        character_enhancer=StubCharacterEnhancer(),
        visual_coherence=StubVisualCoherence(),
        quality_manager=StubQualityManager(),
        video_agent=object(),
        qa_agent=object(),
        discovery_agent=object(),
        transcript_agent=object(),
        config_manager=object(),
        format_adapter=object(),
        telemetry=RunTelemetry("off", enabled=False),
    )

    result = await orchestrator.process_episode("https://example.invalid/ep", "Naruto")

    assert result["success"] is True, result.get("error")
    assert orchestrator.telemetry.stages == []


async def test_measured_processing_time_replaces_the_placeholder_metric(orchestrator):
    """
    ``record_quality_metrics`` used to receive ``processing_time_ms: 0`` and
    ``output_quality_score: 0.9`` with a comment admitting they were invented.
    The time is now measured; the two nobody samples are ``None``, so a consumer
    can tell "not measured" from "measured zero".
    """
    await orchestrator.process_episode("https://example.invalid/ep", "Naruto")

    (metrics,) = orchestrator.quality_manager.recorded
    assert metrics["processing_time_ms"] > 0
    assert metrics["memory_usage_mb"] is None
    assert metrics["output_quality_score"] is None
