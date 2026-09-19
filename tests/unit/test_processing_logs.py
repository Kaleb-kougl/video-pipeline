"""
``processing_logs`` gets written, so ``stats`` can stop lying.

The table, its writer ``DatabaseManager.log_processing_task`` and the "Recent
activity" section of ``main.py stats`` all shipped together, and nothing ever
called the writer - not ``main.py``, not ``agents/``, not a test. The section
was therefore structurally always empty, which reads as "nothing happened in
the last 24 hours" rather than "this was never wired up".

The orchestrator's stage boundaries are where the facts are, so that is where
the writer now lives. What each table is for:

``run_telemetry``
    Per *job*: stage timings plus tokens and cost, for "what did this run cost".
``processing_logs``
    Per *episode*: which stage did what, for "what has happened to episode 7".
    ``run_telemetry`` has no episode column, so it cannot answer that.
"""

import sqlite3
import sys
from pathlib import Path
from typing import Any

import pytest

project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from agents.workflow_orchestrator import WorkflowOrchestrator  # noqa: E402
from core.telemetry import RunTelemetry  # noqa: E402
from tests.unit.test_orchestrator_telemetry import (  # noqa: E402
    EXPECTED_STAGES,
    StubCharacterAnalyzer,
    StubCharacterEnhancer,
    StubContentAgent,
    StubQualityManager,
    StubVisualCoherence,
)

# `sample_episode_summary`, which `fake_chat_model` returns, is Naruto S1E5.
EPISODE = ("Naruto", "1", "5")


def _build(database_manager, fake_chat_model, monkeypatch, telemetry=None):
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
        **({} if telemetry is None else {"telemetry": telemetry}),
    )


@pytest.fixture
def logging_orchestrator(database_manager, fake_chat_model, monkeypatch):
    return _build(database_manager, fake_chat_model, monkeypatch)


def _logs(db) -> list[sqlite3.Row]:
    with sqlite3.connect(db.db_path) as conn:
        conn.row_factory = sqlite3.Row
        return list(conn.execute("SELECT * FROM processing_logs ORDER BY id"))


class TestTheTableIsWritten:
    async def test_a_run_logs_every_stage_against_its_episode(
        self, logging_orchestrator, database_manager
    ):
        result = await logging_orchestrator.process_episode("https://example.invalid/ep", "Naruto")
        assert result["success"] is True, result.get("error")

        rows = _logs(database_manager)
        assert [row["task_type"] for row in rows] == EXPECTED_STAGES
        assert {row["status"] for row in rows} == {"completed"}

        episode_id = database_manager.get_episode_id(*EPISODE)
        assert episode_id is not None
        assert {row["episode_id"] for row in rows} == {episode_id}
        assert all(row["processing_time"] >= 0 for row in rows)

    async def test_stats_recent_activity_is_no_longer_empty(
        self, logging_orchestrator, database_manager
    ):
        """The section `main.py stats` prints. It could not report anything before."""
        await logging_orchestrator.process_episode("https://example.invalid/ep", "Naruto")

        activity = database_manager.get_processing_stats()["recent_activity"]
        assert activity
        assert {row["task_type"] for row in activity} == set(EXPECTED_STAGES)
        assert {row["status"] for row in activity} == {"completed"}

    async def test_a_failed_stage_is_recorded_with_its_reason(
        self, logging_orchestrator, database_manager, monkeypatch
    ):
        def explode(*args: Any, **kwargs: Any) -> None:
            raise RuntimeError("encoder unavailable")

        monkeypatch.setattr("agents.workflow_orchestrator.mp4_file_enhanced", explode)

        result = await logging_orchestrator.process_episode("https://example.invalid/ep", "Naruto")
        assert result["success"] is False

        failed = [row for row in _logs(database_manager) if row["status"] == "failed"]
        assert [row["task_type"] for row in failed] == ["video_encode"]
        assert "encoder unavailable" in failed[0]["error_message"]

    async def test_a_retry_appends_rather_than_replacing_the_failed_attempt(
        self, logging_orchestrator, database_manager
    ):
        await logging_orchestrator.process_episode("https://example.invalid/ep", "Naruto")
        await logging_orchestrator.process_episode("https://example.invalid/ep", "Naruto")

        assert len(_logs(database_manager)) == 2 * len(EXPECTED_STAGES)

    async def test_stage_outcomes_do_not_leak_between_runs(
        self, logging_orchestrator, database_manager
    ):
        """Each attempt files its own stages, not the previous attempt's as well."""
        await logging_orchestrator.process_episode("https://example.invalid/ep", "Naruto")
        first = len(_logs(database_manager))

        await logging_orchestrator.process_episode("https://example.invalid/ep", "Naruto")

        assert len(_logs(database_manager)) - first == len(EXPECTED_STAGES)

    async def test_turning_telemetry_off_does_not_turn_the_audit_trail_off(
        self, database_manager, fake_chat_model, monkeypatch
    ):
        """
        ``ANIME_TELEMETRY=0`` suppresses the *report*, not the record.

        This is why the stage outcomes are collected by the orchestrator's own
        wrapper rather than read back off the telemetry payload: an inert
        collector records no stages at all, and an operator who turned off
        timing did not ask the database to forget that a render failed.
        """
        orchestrator = _build(
            database_manager,
            fake_chat_model,
            monkeypatch,
            telemetry=RunTelemetry("off", enabled=False),
        )

        result = await orchestrator.process_episode("https://example.invalid/ep", "Naruto")

        assert result["success"] is True, result.get("error")
        assert orchestrator.telemetry.stages == []
        assert [row["task_type"] for row in _logs(database_manager)] == EXPECTED_STAGES


class TestNothingIsInvented:
    async def test_an_unpersisted_episode_logs_nothing_rather_than_a_dangling_row(
        self, database_manager, fake_chat_model, monkeypatch
    ):
        """
        ``episode_id`` is an enforced foreign key, so a log with no episode is
        not written at all. Silence is the honest answer: an attempt that died
        before the episode existed has nothing to hang a record off.
        """

        class FailingContentAgent:
            def extract_and_analyze(self, url: str) -> dict[str, Any]:
                return {"success": False, "error": "404"}

        orchestrator = _build(database_manager, fake_chat_model, monkeypatch)
        orchestrator.content_agent = FailingContentAgent()

        result = await orchestrator.process_episode("https://example.invalid/ep", "Naruto")

        assert result["success"] is False
        assert _logs(database_manager) == []

    def test_recording_against_an_unknown_episode_writes_nothing(self, logging_orchestrator):
        logging_orchestrator._pending_stage_logs = [("video_encode", True, None, 1.0)]

        assert logging_orchestrator._record_processing_logs("Nobody", 9, 9) == 0
