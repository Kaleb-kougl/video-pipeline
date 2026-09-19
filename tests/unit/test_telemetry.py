"""
The run-telemetry contract.

These tests exist to keep two specific promises honest, because both are easy
to break in a way nothing else would notice:

1. **A number that was not observed is never reported.** Tokens with no usage
   metadata come back as ``None`` plus a reason, and cost is refused unless
   *both* real token counts and a configured price table exist.
2. **Instrumentation does not change behaviour.** Disabled collectors are
   pass-throughs, stage timers re-raise, and the LLM wrapper does not alter the
   signature or return value of the call it wraps - which is what lets the
   offline demo and the e2e fakes keep their ``invoke(self, prompt)`` doubles.
"""

import json
import sys
from pathlib import Path

import pytest
from langchain_core.language_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from core.telemetry import PriceTable, RunTelemetry  # noqa: E402

# ---------------------------------------------------------------------------
# Stage timing
# ---------------------------------------------------------------------------


def test_stages_are_recorded_in_order_with_measured_wall_clock():
    telemetry = RunTelemetry("run-1")
    telemetry.start_run()
    with telemetry.stage("content_extraction"):
        pass
    with telemetry.stage("video_encode"):
        pass
    telemetry.end_run()

    assert [s.name for s in telemetry.stages] == ["content_extraction", "video_encode"]
    assert all(s.wall_seconds >= 0 for s in telemetry.stages)
    assert all(s.ok for s in telemetry.stages)
    # Stage names carry their architecture.md stage number so the report can be
    # read against the documented pipeline rather than against this module.
    assert telemetry.stages[0].doc_stage == "1-2"
    assert telemetry.stages[1].doc_stage == "5"
    assert telemetry.run_wall_seconds is not None


def test_a_failing_stage_is_recorded_and_the_exception_still_propagates():
    telemetry = RunTelemetry("run-2")
    telemetry.start_run()

    with pytest.raises(ValueError, match="encoder died"):
        with telemetry.stage("video_encode"):
            raise ValueError("encoder died")

    assert len(telemetry.stages) == 1
    assert telemetry.stages[0].ok is False
    assert "encoder died" in (telemetry.stages[0].error or "")


def test_end_run_is_idempotent_so_the_payload_and_the_printout_agree():
    telemetry = RunTelemetry("run-3")
    telemetry.start_run()
    telemetry.end_run()
    first = telemetry.run_wall_seconds
    telemetry.end_run()
    assert telemetry.run_wall_seconds == first


def test_a_disabled_collector_is_completely_inert():
    telemetry = RunTelemetry("run-4", enabled=False)
    telemetry.start_run()
    with telemetry.stage("content_extraction"):
        pass
    with telemetry.llm_call("summary"):
        pass
    telemetry.end_run()

    assert telemetry.stages == []
    assert telemetry.llm_calls == []
    assert telemetry.run_wall_seconds is None
    assert telemetry.format_summary() == "telemetry disabled"


def test_env_switch_disables_collection():
    assert RunTelemetry.from_env("r", env={"ANIME_TELEMETRY": "0"}).enabled is False
    assert RunTelemetry.from_env("r", env={"ANIME_TELEMETRY": "false"}).enabled is False
    assert RunTelemetry.from_env("r", env={}).enabled is True


# ---------------------------------------------------------------------------
# Token accounting
# ---------------------------------------------------------------------------


def test_tokens_are_captured_from_a_real_langchain_response():
    """
    The capture path, end to end, through LangChain's callback machinery.

    The model here is a genuine ``BaseChatModel``; only its answer is canned.
    That is what makes this a test of the wiring rather than of a mock.
    """
    model = FakeMessagesListChatModel(
        responses=[
            AIMessage(
                content="summary",
                usage_metadata={"input_tokens": 1234, "output_tokens": 56, "total_tokens": 1290},
                response_metadata={"model_name": "gemini-2.0-flash"},
            )
        ]
    )

    telemetry = RunTelemetry("run-5")
    telemetry.start_run()
    with telemetry.llm_call("episode_summary"):
        model.invoke("transcript")
    telemetry.end_run()

    (call,) = telemetry.llm_calls
    assert (call.input_tokens, call.output_tokens) == (1234, 56)
    assert call.model == "gemini-2.0-flash"
    assert call.tokens_unavailable_reason is None
    assert telemetry.token_totals() == (1234, 56)


def test_tokens_survive_a_response_that_omits_the_model_name():
    """
    langchain-core's own usage callback discards usage when ``model_name`` is
    missing. Dropping a measured count over a missing label is the exact
    failure mode this module exists to avoid, so the count is kept.
    """
    model = FakeMessagesListChatModel(
        responses=[
            AIMessage(
                content="summary",
                usage_metadata={"input_tokens": 5, "output_tokens": 2, "total_tokens": 7},
            )
        ]
    )

    telemetry = RunTelemetry("run-6")
    telemetry.start_run()
    with telemetry.llm_call("episode_summary"):
        model.invoke("transcript")

    (call,) = telemetry.llm_calls
    assert (call.input_tokens, call.output_tokens) == (5, 2)
    assert call.model is None


def test_a_call_with_no_usage_metadata_is_unavailable_not_zero():
    """The offline case: latency is real, tokens are unknown, nothing is invented."""

    class StructuredDouble:
        """Mirrors the demo/e2e doubles: ``invoke(self, prompt)``, no ``config``."""

        def invoke(self, prompt):
            return {"parsed": prompt}

    telemetry = RunTelemetry("run-7")
    telemetry.start_run()
    with telemetry.llm_call("episode_summary"):
        returned = StructuredDouble().invoke("prompt")

    (call,) = telemetry.llm_calls
    assert returned == {"parsed": "prompt"}, "the wrapper must not touch the return value"
    assert call.input_tokens is None and call.output_tokens is None
    assert call.tokens_unavailable_reason
    assert telemetry.token_totals() == (None, None)
    assert "unavailable" in telemetry.format_summary()


# ---------------------------------------------------------------------------
# Cost: refused unless it can be derived from measured tokens and a stated table
# ---------------------------------------------------------------------------


def test_cost_is_refused_when_no_tokens_were_measured(tmp_path):
    prices = tmp_path / "prices.json"
    prices.write_text(
        json.dumps({"models": {"gemini-2.0-flash": {"input_per_1m": 1.0, "output_per_1m": 2.0}}})
    )
    telemetry = RunTelemetry("run-8", prices=PriceTable.load(prices))
    telemetry.start_run()
    with telemetry.llm_call("episode_summary"):
        pass

    amount, note = telemetry.cost()
    assert amount is None
    assert "token" in note


def test_cost_is_refused_when_no_price_table_is_configured():
    model = FakeMessagesListChatModel(
        responses=[
            AIMessage(
                content="s",
                usage_metadata={"input_tokens": 10, "output_tokens": 10, "total_tokens": 20},
                response_metadata={"model_name": "gemini-2.0-flash"},
            )
        ]
    )
    telemetry = RunTelemetry("run-9")
    telemetry.start_run()
    with telemetry.llm_call("episode_summary"):
        model.invoke("x")

    amount, note = telemetry.cost()
    assert amount is None
    assert "price table" in note


def test_cost_is_computed_from_measured_tokens_and_labelled_as_an_assumption(tmp_path):
    prices = tmp_path / "prices.json"
    prices.write_text(
        json.dumps(
            {
                "currency": "USD",
                "source": "an operator-supplied table",
                "retrieved": "2026-09-18",
                "models": {"gemini-2.0-flash": {"input_per_1m": 1.0, "output_per_1m": 10.0}},
            }
        )
    )
    model = FakeMessagesListChatModel(
        responses=[
            AIMessage(
                content="s",
                usage_metadata={
                    "input_tokens": 1_000_000,
                    "output_tokens": 100_000,
                    "total_tokens": 1_100_000,
                },
                response_metadata={"model_name": "gemini-2.0-flash"},
            )
        ]
    )

    telemetry = RunTelemetry("run-10", prices=PriceTable.load(prices))
    telemetry.start_run()
    with telemetry.llm_call("episode_summary"):
        model.invoke("x")
    telemetry.end_run()

    amount, note = telemetry.cost()
    assert amount == pytest.approx(1.0 + 1.0)  # 1M in at $1/M, 100k out at $10/M
    assert "assumption" in note

    payload = telemetry.to_dict()
    assert payload["cost"]["price_table"]["source"] == "an operator-supplied table"
    assert payload["cost"]["price_table"]["retrieved"] == "2026-09-18"
    assert "not measured" in payload["cost"]["price_table"]["basis"]


def test_an_unreadable_price_file_is_ignored_rather_than_fatal(tmp_path):
    bad = tmp_path / "nope.json"
    telemetry = RunTelemetry.from_env("run-11", env={"ANIME_TELEMETRY_PRICES": str(bad)})
    assert telemetry.enabled is True
    assert telemetry.prices is None


# ---------------------------------------------------------------------------
# The artifact
# ---------------------------------------------------------------------------


def test_json_artifact_round_trips_and_marks_unmeasured_values(tmp_path):
    telemetry = RunTelemetry("Show_2026-01-01T00:00:00")
    telemetry.start_run()
    with telemetry.stage("image_generation"):
        pass
    with telemetry.llm_call("episode_summary"):
        pass
    telemetry.end_run()

    written = telemetry.write_json(tmp_path)
    payload = json.loads(written.read_text())

    assert written.parent == tmp_path
    assert ":" not in written.name, "run ids become filesystem-safe names"
    assert payload["stages"][0]["stage"] == "image_generation"
    assert payload["tokens"] == {
        "input": None,
        "output": None,
        "note": "unavailable - no LLM response in this run carried usage metadata",
    }
    assert payload["cost"]["amount"] is None
    assert payload["wall_seconds"] is not None


def test_write_json_accepts_an_explicit_filename(tmp_path):
    telemetry = RunTelemetry("run-12")
    telemetry.start_run()
    telemetry.end_run()
    written = telemetry.write_json(tmp_path / "sub" / "run.json")
    assert written.name == "run.json"
    assert json.loads(written.read_text())["run_id"] == "run-12"


def test_emit_never_raises_even_when_the_destination_is_unwritable(tmp_path, capsys):
    blocked = tmp_path / "file"
    blocked.write_text("not a directory")
    telemetry = RunTelemetry("run-13")
    telemetry.start_run()
    telemetry.end_run()

    # Reporting must not be able to take down a run that already produced a video.
    telemetry.emit(env={"ANIME_TELEMETRY_JSON": str(blocked / "inside")})
    assert "RUN TELEMETRY" in capsys.readouterr().out
