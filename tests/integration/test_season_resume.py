"""
A season batch survives being killed halfway through.

This is the test the resumability work exists for. A season run makes a paid
model call and renders a video per episode, so a crash at episode 7 of 12 used
to lose the whole run: SQLite was an append-only log, nothing recorded what had
finished, and the only way forward was to pay for all twelve again.

The run here is killed mid-episode with ``KeyboardInterrupt`` - a ``BaseException``,
so it is not swallowed by ``process_episode_by_numbers``'s ``except Exception``
and it models a real Ctrl-C or supervisor kill: the process stops *between*
starting an episode and recording its outcome, which is the state the whole
design has to cope with.

The orchestrator is replaced with a recorder. That is the point, not a
shortcut: the orchestrator call *is* the expensive work (model call plus
render), so counting calls to it is a direct measurement of what a resumed run
paid for. The real orchestrator's own behaviour is covered by
``tests/unit/test_orchestrator_telemetry.py`` and the offline ``make demo``.
"""

from typing import Any
from unittest.mock import patch

import pytest

from config.settings import get_settings
from core.schemas import EpisodeStatus, ProcessingResult, RunStatus

SHOW = "My Hero Academia"  # a real entry in EpisodeConfigs, so the season length is known
SEASON = 1


class FakeVectorSearchManager:
    """Stand-in for the optional vector search backend."""


class FakeCharacterAgent:
    """Stand-in for the ChromaDB-backed character analysis agent."""

    def analyze_episode_characters(
        self, show_name: str, season: Any, episode: Any, transcript: str
    ) -> dict[str, Any]:
        return {}


class RecordingOrchestrator:
    """
    Stands in for the expensive half of the pipeline and counts what it cost.

    Every call represents one episode's paid model call plus one video render.
    ``crash_on`` kills the process partway through that episode, *after* the
    run has recorded that the episode was started and before any outcome is
    written - exactly where a real crash lands.
    """

    def __init__(self, crash_on: int | None = None):
        self.crash_on = crash_on
        self.calls: list[tuple[int, str | None]] = []

    @property
    def episodes_processed(self) -> list[int]:
        return [episode for episode, _ in self.calls]

    async def process_episode_complete(
        self,
        show_name: str,
        season: int,
        episode: int,
        episode_title: str = None,
        db: Any = None,
        run_id: str | None = None,
    ) -> ProcessingResult:
        self.calls.append((episode, run_id))

        if episode == self.crash_on:
            raise KeyboardInterrupt(f"killed while processing S{season}E{episode}")

        # The real orchestrator persists the episode before generating media;
        # do the same so the resumed run is working against a realistic row.
        db.save_episode(
            show_name,
            str(season),
            str(episode),
            f"https://example.invalid/{show_name}/s{season}e{episode}",
            transcript=f"transcript for episode {episode}",
            summary=f"summary for episode {episode}",
            plot_points=[f"plot point {episode}"],
        )
        return ProcessingResult(
            success=True,
            job_id=f"{run_id}/S{season}E{episode}",
            data={"show": show_name, "season": str(season), "episode": str(episode)},
        )


class FailingOrchestrator(RecordingOrchestrator):
    """Fails one episode the ordinary way: a result, not an exception."""

    def __init__(self, fail_on: int):
        super().__init__()
        self.fail_on = fail_on

    async def process_episode_complete(self, show_name, season, episode, *args, **kwargs):  # noqa: ANN001,ANN201
        if episode == self.fail_on:
            self.calls.append((episode, kwargs.get("run_id")))
            return ProcessingResult(success=False, error="no transcript source responded")
        return await super().process_episode_complete(show_name, season, episode, *args, **kwargs)


@pytest.fixture
def generator(tmp_path, fake_chat_model, monkeypatch):
    """A real ``AnimeVideoGenerator`` confined to ``tmp_path``, with no delays."""
    import main

    settings = get_settings().model_copy(
        update={
            "database_path": str(tmp_path / "video_generator.db"),
            "output_directory": str(tmp_path / "output"),
        }
    )

    # The batch sleeps 2-5s between episodes to be polite to transcript
    # servers. No server is contacted here, and a 5-episode run would
    # otherwise spend half a minute asleep.
    monkeypatch.setattr("main.time.sleep", lambda _seconds: None)

    with (
        patch("main.get_settings", return_value=settings),
        patch("langchain.chat_models.init_chat_model", return_value=fake_chat_model),
        patch("main.CharacterAnalysisAgent", return_value=FakeCharacterAgent()),
        patch("main.VectorSearchManager", return_value=FakeVectorSearchManager()),
    ):
        return main.AnimeVideoGenerator()


async def test_a_killed_batch_resumes_without_redoing_completed_episodes(generator):
    """
    The deliverable: kill the run at episode 3 of 5, resume, and pay only for
    what was left.
    """
    first_pass = RecordingOrchestrator(crash_on=3)
    generator.orchestrator = first_pass

    with pytest.raises(KeyboardInterrupt):
        await generator.process_season_batch(SHOW, SEASON, 1, 5, full_processing=True)

    # --- what the crash left behind -------------------------------------
    assert first_pass.episodes_processed == [1, 2, 3]

    assert generator.db.is_episode_complete(SHOW, SEASON, 1) is True
    assert generator.db.is_episode_complete(SHOW, SEASON, 2) is True
    # Episode 3 was in flight. Nothing is known about how far it got, so it is
    # neither succeeded nor failed - and it is certainly not complete.
    assert generator.db.get_episode_status(SHOW, SEASON, 3) is EpisodeStatus.IN_PROGRESS
    assert generator.db.is_episode_complete(SHOW, SEASON, 3) is False
    assert generator.db.get_episode_status(SHOW, SEASON, 4) is None

    # The run never wrote its own epitaph, which is precisely how --resume
    # finds it.
    crashed_run = generator.db.find_resumable_run(SHOW, SEASON)
    assert crashed_run is not None
    assert crashed_run["status"] == RunStatus.RUNNING.value
    run_id = crashed_run["run_id"]

    # --- resume ----------------------------------------------------------
    second_pass = RecordingOrchestrator()
    generator.orchestrator = second_pass

    report = await generator.process_season_batch(
        SHOW, SEASON, 1, 5, full_processing=True, resume=True
    )

    # The work already paid for was NOT paid for again.
    assert second_pass.episodes_processed == [3, 4, 5]
    assert 1 not in second_pass.episodes_processed
    assert 2 not in second_pass.episodes_processed

    # Across both passes each episode cost exactly one orchestrator call,
    # except the one that was interrupted.
    all_calls = first_pass.episodes_processed + second_pass.episodes_processed
    assert sorted(all_calls) == [1, 2, 3, 3, 4, 5]

    # --- and the run finished --------------------------------------------
    assert report is not None
    assert report.run_id == run_id, "a resumed run keeps its identity"
    assert report.resumed is True
    assert report.status is RunStatus.SUCCEEDED
    assert report.skipped == 2
    assert report.succeeded == 3
    assert report.failed == 0
    assert report.requested == 5

    assert all(generator.db.is_episode_complete(SHOW, SEASON, ep) for ep in range(1, 6))
    assert generator.db.get_run(run_id)["status"] == RunStatus.SUCCEEDED.value
    assert generator.db.get_run(run_id)["resumed_count"] == 1


async def test_the_skipped_episodes_are_reported_as_skipped_not_reprocessed(generator):
    """A resumed run says which episodes it charged for and which it did not."""
    generator.orchestrator = RecordingOrchestrator(crash_on=3)
    with pytest.raises(KeyboardInterrupt):
        await generator.process_season_batch(SHOW, SEASON, 1, 4, full_processing=True)

    generator.orchestrator = RecordingOrchestrator()
    report = await generator.process_season_batch(
        SHOW, SEASON, 1, 4, full_processing=True, resume=True
    )

    by_episode = {outcome.episode: outcome for outcome in report.episodes}
    assert [by_episode[ep].skipped for ep in (1, 2, 3, 4)] == [True, True, False, False]
    assert all(outcome.status is EpisodeStatus.SUCCEEDED for outcome in report.episodes)


async def test_without_resume_the_batch_redoes_everything(generator):
    """
    The control. Skipping must be caused by ``--resume``, not by the episode
    happening to have a row - otherwise a deliberate reprocess would silently
    do nothing.
    """
    generator.orchestrator = RecordingOrchestrator(crash_on=3)
    with pytest.raises(KeyboardInterrupt):
        await generator.process_season_batch(SHOW, SEASON, 1, 4, full_processing=True)
    crashed_run_id = generator.db.find_resumable_run(SHOW, SEASON)["run_id"]

    fresh = RecordingOrchestrator()
    generator.orchestrator = fresh
    report = await generator.process_season_batch(SHOW, SEASON, 1, 4, full_processing=True)

    assert fresh.episodes_processed == [1, 2, 3, 4]
    assert report.skipped == 0
    assert report.resumed is False
    assert report.run_id != crashed_run_id, "a fresh run is a new run, not a continuation"


async def test_a_resumed_run_retries_episodes_that_failed_for_a_reason(generator):
    """
    An ordinary failure is recorded with its reason and retried on resume.

    A failed episode is not "done": the transcript source may have been down,
    and the next attempt may well succeed. Only a recorded success is skipped.
    """
    generator.orchestrator = FailingOrchestrator(fail_on=2)
    report = await generator.process_season_batch(SHOW, SEASON, 1, 3, full_processing=True)

    assert report.status is RunStatus.PARTIAL
    assert report.failed == 1
    assert generator.db.get_episode_status(SHOW, SEASON, 2) is EpisodeStatus.FAILED
    assert (
        generator.db.get_episode(SHOW, "1", "2")["last_error"] == "no transcript source responded"
    )

    # A partial run is still resumable: the cause may have been transient.
    retry = RecordingOrchestrator()
    generator.orchestrator = retry
    resumed = await generator.process_season_batch(
        SHOW, SEASON, 1, 3, full_processing=True, resume=True
    )

    assert retry.episodes_processed == [2], "only the failed episode is retried"
    assert resumed.run_id == report.run_id
    assert resumed.status is RunStatus.SUCCEEDED
    assert resumed.skipped == 2
    assert generator.db.get_episode(SHOW, "1", "2")["last_error"] is None


async def test_attempts_are_counted_so_a_repeatedly_failing_episode_is_visible(generator):
    """A run's history survives the resume, rather than being overwritten by it."""
    generator.orchestrator = FailingOrchestrator(fail_on=2)
    await generator.process_season_batch(SHOW, SEASON, 1, 2, full_processing=True)

    generator.orchestrator = FailingOrchestrator(fail_on=2)
    await generator.process_season_batch(SHOW, SEASON, 1, 2, full_processing=True, resume=True)

    assert generator.db.get_episode(SHOW, "1", "1")["attempts"] == 1, "skipped, so not re-attempted"
    assert generator.db.get_episode(SHOW, "1", "2")["attempts"] == 2


async def test_a_partial_run_can_be_inspected_afterwards(generator):
    """The user can ask what a killed run actually accomplished."""
    generator.orchestrator = RecordingOrchestrator(crash_on=3)
    with pytest.raises(KeyboardInterrupt):
        await generator.process_season_batch(SHOW, SEASON, 1, 5, full_processing=True)

    run_id = generator.db.find_resumable_run(SHOW, SEASON)["run_id"]
    progress = generator.db.get_run_progress(run_id)

    assert progress["found"] is True
    assert progress["run"]["status"] == RunStatus.RUNNING.value
    assert progress["run"]["command"] == "process-season"
    assert progress["status_counts"] == {"succeeded": 2, "in_progress": 1}
    assert [row["episode"] for row in progress["episodes"]] == ["1", "2", "3"]


async def test_resuming_with_nothing_to_resume_starts_a_new_run(generator):
    """``--resume`` on a clean slate is not an error; it is just a first run."""
    generator.orchestrator = RecordingOrchestrator()

    report = await generator.process_season_batch(
        SHOW, SEASON, 1, 2, full_processing=True, resume=True
    )

    assert report.resumed is False
    assert report.skipped == 0
    assert report.status is RunStatus.SUCCEEDED
    assert generator.orchestrator.episodes_processed == [1, 2]


async def test_the_run_id_is_threaded_into_the_work_it_paid_for(generator):
    """Every episode is attributable to the run that processed it."""
    orchestrator = RecordingOrchestrator()
    generator.orchestrator = orchestrator

    report = await generator.process_season_batch(SHOW, SEASON, 1, 2, full_processing=True)

    assert {run_id for _, run_id in orchestrator.calls} == {report.run_id}
    assert generator.db.get_episode(SHOW, "1", "1")["run_id"] == report.run_id


async def test_an_unknown_season_starts_no_run_at_all(generator):
    """Nothing is recorded for a season whose length cannot be established."""
    generator.orchestrator = RecordingOrchestrator()

    report = await generator.process_season_batch("Nonexistent Show", 99, full_processing=True)

    assert report is None
    assert generator.orchestrator.calls == []
    assert generator.db.find_resumable_run("Nonexistent Show", 99) is None
