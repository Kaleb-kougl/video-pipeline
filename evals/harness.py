"""
The eval harness: load the golden set, obtain a summary per case, score it,
print a scorecard, write JSON, and set the exit code.

Two modes, deliberately distinct in the output banner:

``offline`` (default, and what CI runs)
    Replays committed fixtures from ``evals/fixtures/recorded/``. No API key, no
    network - a socket guard makes that a checked claim rather than a promise.
    The real ``WorkflowOrchestrator.generate_structured_summary`` code path is
    still executed, with only the model swapped, so the prompt is genuinely
    rendered by production code and the prompt-contract check has something real
    to inspect.

``live`` (requires ``GOOGLE_API_KEY``)
    Calls Gemini through the same production path. This is the mode that
    actually evaluates a prompt change. ``--record`` overwrites the fixtures
    with what came back, so the committed baseline moves in a reviewable diff.

The offline/live split is the honest one: offline mode locks the rubric, the
golden set and the prompt contract, and gives CI something to gate on; it cannot
tell you that a prompt edit made the model worse, because the recorded outputs
do not react to the prompt. Live mode is where that question gets answered, and
then the answer gets committed.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evals.metrics import CaseScore, check_prompt_contract, score_case

EVALS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EVALS_DIR.parent
CASES_DIR = EVALS_DIR / "cases"
DEFAULT_FIXTURES_DIR = EVALS_DIR / "fixtures" / "recorded"
BASELINE_PATH = EVALS_DIR / "baseline.json"
DEFAULT_JSON_OUT = EVALS_DIR / "results" / "scorecard.json"

SCHEMA_FIELDS = ("show", "season", "episode", "youtube_transcript", "plot_points")


class EvalMadeANetworkCall(RuntimeError):
    """Raised if offline mode tries to open an off-box socket."""


def block_outbound_network() -> None:
    """Same guard ``scripts/demo.py`` uses. 'Runs offline' should be enforced,
    not asserted in a README."""
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def is_local(address: object) -> bool:
        if not isinstance(address, tuple) or not address:
            return True
        return str(address[0]) in {"127.0.0.1", "::1", "localhost", "0.0.0.0"}

    def guarded_connect(self, address, *args, **kwargs):  # type: ignore[no-untyped-def]
        if not is_local(address):
            raise EvalMadeANetworkCall(
                f"Offline eval tried to connect to {address!r}. That is a bug in the "
                "harness's stubs, not a missing API key."
            )
        return real_connect(self, address, *args, **kwargs)

    def guarded_connect_ex(self, address, *args, **kwargs):  # type: ignore[no-untyped-def]
        if not is_local(address):
            raise EvalMadeANetworkCall(f"Offline eval tried to connect to {address!r}.")
        return real_connect_ex(self, address, *args, **kwargs)

    socket.socket.connect = guarded_connect  # type: ignore[method-assign]
    socket.socket.connect_ex = guarded_connect_ex  # type: ignore[method-assign]


# ---------------------------------------------------------------------------
# Golden set
# ---------------------------------------------------------------------------


def load_cases(only: list[str] | None = None) -> list[dict[str, Any]]:
    manifest = json.loads((CASES_DIR / "cases.json").read_text())
    cases = manifest["cases"]
    for case in cases:
        case["transcript_text"] = (CASES_DIR / case["transcript"]).read_text()
    if only:
        wanted = set(only)
        unknown = wanted - {c["id"] for c in cases}
        if unknown:
            raise SystemExit(f"Unknown case id(s): {', '.join(sorted(unknown))}")
        cases = [c for c in cases if c["id"] in wanted]
    return cases


def load_fixture(fixtures_dir: Path, case_id: str) -> dict[str, Any]:
    path = fixtures_dir / f"{case_id}.json"
    if not path.exists():
        raise SystemExit(
            f"Missing recorded fixture {path}. Record one with:\n"
            f"  python evals/run_eval.py --mode live --record --case {case_id}"
        )
    return json.loads(path.read_text())


# ---------------------------------------------------------------------------
# Model access - the only thing that differs between the two modes
# ---------------------------------------------------------------------------


class ReplayModel:
    """
    Stands in for a LangChain chat model and replays a recorded response.

    Mirrors ``tests/conftest.py::FakeChatModel`` and the demo's
    ``CannedChatModel`` so there is one shape of fake in the repo. Every prompt
    is captured, which is what feeds the prompt-contract check.
    """

    def __init__(self) -> None:
        self.response: Any = None
        self.prompts: list[Any] = []
        self._structured: ReplayModel | None = None

    def with_structured_output(self, _schema: Any) -> ReplayModel:
        self._structured = self
        return self

    def invoke(self, prompt: Any) -> Any:
        self.prompts.append(prompt)
        return self.response


@dataclass
class Generation:
    """One model output plus how it was obtained."""

    raw: dict[str, Any] | None
    parse_error: str | None
    rendered_prompt: str
    source: str


def build_orchestrator(mode: str, db_path: Path):  # noqa: ANN201 - lazy import type
    """
    Construct the real ``WorkflowOrchestrator`` with only the boundaries the
    eval has no business touching replaced.

    In offline mode the chat model is a ``ReplayModel`` and the ChromaDB-backed
    character agent is stubbed (it downloads an embedding model on first use).
    In live mode the real ``init_chat_model`` runs; the character agent is still
    stubbed because this eval scores summarisation, not character retrieval.
    """
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from unittest.mock import patch

    from agents.workflow_orchestrator import WorkflowOrchestrator

    db_path.parent.mkdir(parents=True, exist_ok=True)
    replay = ReplayModel() if mode == "offline" else None

    stack = [patch("agents.workflow_orchestrator.CharacterAnalysisAgent")]
    if replay is not None:
        stack.append(patch("agents.workflow_orchestrator.init_chat_model", return_value=replay))

    for patcher in stack:
        patcher.start()
    try:
        orchestrator = WorkflowOrchestrator(db_path=str(db_path))
    finally:
        for patcher in stack:
            patcher.stop()

    if mode == "live" and orchestrator.model_with_structure is None:
        raise SystemExit(
            "Live mode requested but the chat model failed to initialise. Check "
            "GOOGLE_API_KEY and that langchain-google-genai is installed."
        )
    return orchestrator, replay


def render_prompt_text(prompt: Any) -> str:
    """Flatten whatever ``ChatPromptTemplate.invoke`` returned into plain text."""
    messages = getattr(prompt, "messages", None)
    if messages is not None:
        return "\n".join(str(getattr(m, "content", m)) for m in messages)
    return str(prompt)


def generate(orchestrator: Any, replay: ReplayModel | None, case: dict, mode: str) -> Generation:
    """
    Drive the production summarisation path for one case.

    Both modes call the same method, ``generate_structured_summary``, so the
    prompt template, the show-name interpolation and the structured-output
    contract are exercised identically. Only the model behind it differs.
    """
    if mode == "offline":
        fixture = load_fixture(case["_fixtures_dir"], case["id"])
        assert replay is not None
        replay.response = _fixture_to_schema(fixture)
        orchestrator.model_with_structure = replay

    content_result = {"transcript": case["transcript_text"], "analysis": ""}
    parse_error: str | None = None
    raw: dict[str, Any] | None = None
    try:
        raw = orchestrator.generate_structured_summary(content_result, case["show"])
    except Exception as exc:  # noqa: BLE001 - a failed generation is a data point
        parse_error = f"{type(exc).__name__}: {exc}"

    prompts = replay.prompts if replay is not None else getattr(orchestrator, "_eval_prompts", [])
    rendered = render_prompt_text(prompts[-1]) if prompts else ""
    return Generation(
        raw=raw,
        parse_error=parse_error,
        rendered_prompt=rendered,
        source="fixture" if mode == "offline" else "gemini",
    )


def _fixture_to_schema(fixture: dict[str, Any]) -> Any:
    """
    Turn a recorded fixture into the schema object the production code expects
    back from ``with_structured_output``.

    A fixture that does not satisfy the schema is replayed as a plain object
    that raises on ``model_dump`` - that is how the harness represents "the
    model returned something unparseable", which is a real failure mode and one
    the rubric has to be able to score.
    """
    from core.schemas import Episode_Summary_Schema

    payload = {k: v for k, v in fixture.items() if k in SCHEMA_FIELDS}
    try:
        return Episode_Summary_Schema(**payload)
    except Exception as exc:  # noqa: BLE001
        # Bind the message now: `exc` is unbound once the except block exits, so
        # closing over it directly raises NameError instead of reporting the
        # schema violation.
        reason = f"{type(exc).__name__}: {exc}".replace("\n", " ")[:300]

    class UnparseableResponse:
        def model_dump(self) -> dict:
            raise ValueError(f"recorded output violates Episode_Summary_Schema - {reason}")

    return UnparseableResponse()


# ---------------------------------------------------------------------------
# Optional LLM judge (live mode only, never gated)
# ---------------------------------------------------------------------------

JUDGE_PROMPT = """You are grading a YouTube narration script written from an episode
transcript. Reply with ONLY a single integer from 1 to 5.

5 = accurate, well paced, no invented events
1 = inaccurate or largely invented

TRANSCRIPT:
{transcript}

SCRIPT:
{script}

Integer score:"""


def judge_case(orchestrator: Any, case: dict, summary: dict | None) -> float | None:
    """
    One extra signal in live mode. Reported, never gated.

    A judge shares the failure modes of the system under test (same family, same
    prompt-sensitivity, same drift across model versions), so gating CI on it
    would mean a green build depends on a number nobody can reproduce. It is
    here because it catches fluency and coherence problems the deterministic
    rubric is blind to, and for nothing else.
    """
    if summary is None or orchestrator.model is None:
        return None
    prompt = JUDGE_PROMPT.format(
        transcript=case["transcript_text"][:4000],
        script=str(summary.get("youtube_transcript") or "")[:4000],
    )
    try:
        response = orchestrator.model.invoke(prompt)
        text = getattr(response, "content", response)
        digits = "".join(ch for ch in str(text) if ch.isdigit())
        if not digits:
            return None
        return min(5, max(1, int(digits[0]))) / 5.0
    except Exception:  # noqa: BLE001 - an unavailable judge must not fail the run
        return None


# ---------------------------------------------------------------------------
# Scorecard
# ---------------------------------------------------------------------------


def aggregate(scores: list[CaseScore]) -> float:
    return statistics.fmean([s.score for s in scores]) if scores else 0.0


def metric_averages(scores: list[CaseScore]) -> dict[str, float]:
    totals: dict[str, list[float]] = {}
    for case_score in scores:
        for metric in case_score.metrics:
            if metric.applicable:
                totals.setdefault(metric.name, []).append(metric.score or 0.0)
    return {name: statistics.fmean(values) for name, values in sorted(totals.items())}


def bar(value: float, width: int = 10) -> str:
    filled = int(round(value * width))
    return "#" * filled + "." * (width - filled)


def print_scorecard(
    mode: str,
    scores: list[CaseScore],
    judges: dict[str, float | None],
    contract_ok: bool,
    contract_missing: list[str],
    baseline: dict[str, Any] | None,
    gate: dict[str, Any],
    full_set: bool = True,
) -> None:
    header = {
        "offline": (
            "OFFLINE MODE - replaying committed fixtures. No API key, no network "
            "(enforced).\n  A prompt change will NOT move these numbers: re-record "
            "with --mode live --record."
        ),
        "live": (
            "LIVE MODE - calling Gemini through the production path. Results are "
            "nondeterministic.\n  Add --record to overwrite the committed fixtures "
            "and baseline inputs."
        ),
    }[mode]

    print("=" * 78)
    print("  LLM GENERATION EVAL - Episode_Summary_Schema rubric")
    print(f"  {header}")
    print("=" * 78)

    print("\n  PROMPT CONTRACT (does the shipped prompt still issue what we score?)")
    if contract_ok:
        print("    PASS  all scored instructions are present in the rendered prompt")
    else:
        print("    FAIL  rendered prompt no longer contains:")
        for directive in contract_missing:
            print(f"            - {directive!r}")

    print("\n  PER-CASE")
    base_cases = (baseline or {}).get("cases", {})
    for case_score in scores:
        prior = base_cases.get(case_score.case_id, {}).get("score")
        delta = (
            "" if prior is None else f"  (baseline {prior:.3f}, {case_score.score - prior:+.3f})"
        )
        print(
            f"\n    {case_score.case_id}: {case_score.score:.3f} [{bar(case_score.score)}]{delta}"
        )
        for metric in case_score.metrics:
            shown = "  n/a" if metric.score is None else f"{metric.score:5.2f}"
            print(f"        {metric.name:<22} {shown}  w={metric.weight:.2f}  {metric.detail}")
        judge = judges.get(case_score.case_id)
        if judge is not None:
            print(f"        {'llm_judge (ungated)':<22} {judge:5.2f}  w=0.00  advisory signal only")
        for error in case_score.errors:
            print(f"        ERROR: {error}")

    print("\n  METRIC AVERAGES (across applicable cases)")
    for name, value in metric_averages(scores).items():
        print(f"    {name:<24} {value:5.3f} [{bar(value)}]")

    total = aggregate(scores)
    print("\n  AGGREGATE")
    prior_total = (baseline or {}).get("aggregate_score") if full_set else None
    line = f"    mean case score: {total:.3f} [{bar(total)}]"
    if prior_total is not None:
        line += f"   baseline {prior_total:.3f} ({total - prior_total:+.3f})"
    print(line)
    threshold_note = "" if full_set else "  (not enforced: --case selected a subset)"
    print(f"    gate threshold : {gate['min_aggregate_score']:.3f}{threshold_note}")
    print(f"    max per-case regression allowed: {gate['max_case_regression']:.3f}")
    print("-" * 78)


def evaluate_gate(
    scores: list[CaseScore],
    contract_ok: bool,
    baseline: dict[str, Any] | None,
    gate: dict[str, Any],
    full_set: bool = True,
) -> list[str]:
    """
    Return the list of gate failures. Empty list means exit 0.

    ``full_set`` is False when ``--case`` selected a subset: the committed
    aggregate threshold describes the whole golden set, so comparing a subset
    against it would fail or pass for the wrong reason. Per-case regressions and
    the prompt contract are still enforced.
    """
    failures: list[str] = []
    if not contract_ok:
        failures.append(
            "prompt contract broken: the shipped prompt no longer issues an instruction "
            "the rubric scores"
        )

    total = aggregate(scores)
    if full_set and total < gate["min_aggregate_score"]:
        failures.append(
            f"aggregate {total:.3f} is below the committed threshold "
            f"{gate['min_aggregate_score']:.3f}"
        )

    base_cases = (baseline or {}).get("cases", {})
    for case_score in scores:
        prior = base_cases.get(case_score.case_id, {}).get("score")
        if prior is None:
            continue
        drop = prior - case_score.score
        if drop > gate["max_case_regression"]:
            failures.append(
                f"case '{case_score.case_id}' regressed {drop:.3f} "
                f"({prior:.3f} -> {case_score.score:.3f}), limit {gate['max_case_regression']:.3f}"
            )
    return failures


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_eval.py",
        description="Score the episode-summarisation prompt against a committed golden set.",
    )
    parser.add_argument(
        "--mode",
        choices=("offline", "live"),
        default="offline",
        help="offline replays committed fixtures (default, CI); live calls Gemini.",
    )
    parser.add_argument("--case", action="append", dest="cases", help="Run only this case id.")
    parser.add_argument(
        "--record",
        action="store_true",
        help="Live mode only: overwrite the committed fixtures with what came back.",
    )
    parser.add_argument(
        "--judge",
        action="store_true",
        help="Live mode only: also collect an LLM-judge score (reported, never gated).",
    )
    parser.add_argument(
        "--fixtures-dir",
        type=Path,
        default=DEFAULT_FIXTURES_DIR,
        help="Where recorded fixtures live. Point at a copy to test the gate.",
    )
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument(
        "--fail-under",
        type=float,
        default=None,
        help="Override the committed aggregate threshold.",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Write this run's scores into evals/baseline.json (review the diff).",
    )
    parser.add_argument("--no-gate", action="store_true", help="Report only; always exit 0.")
    return parser


def run_cli(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)

    if args.mode == "live" and not os.environ.get("GOOGLE_API_KEY"):
        raise SystemExit("--mode live needs GOOGLE_API_KEY. Omit --mode to run offline.")
    if args.record and args.mode != "live":
        raise SystemExit("--record only makes sense with --mode live.")

    if args.mode == "offline":
        for var in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS"):
            os.environ.pop(var, None)
        block_outbound_network()

    baseline = json.loads(BASELINE_PATH.read_text()) if BASELINE_PATH.exists() else None
    gate = dict((baseline or {}).get("gate") or {})
    gate.setdefault("min_aggregate_score", 0.0)
    gate.setdefault("max_case_regression", 0.05)
    if args.fail_under is not None:
        gate["min_aggregate_score"] = args.fail_under

    cases = load_cases(args.cases)
    for case in cases:
        case["_fixtures_dir"] = args.fixtures_dir

    db_path = EVALS_DIR / "results" / "eval_scratch.db"
    orchestrator, replay = build_orchestrator(args.mode, db_path)

    scores: list[CaseScore] = []
    judges: dict[str, float | None] = {}
    contract_ok = True
    contract_missing: list[str] = []

    for case in cases:
        generation = generate(orchestrator, replay, case, args.mode)
        ok, missing = check_prompt_contract(generation.rendered_prompt)
        if not ok:
            contract_ok = False
            contract_missing = missing

        scores.append(
            score_case(generation.raw, case, case["transcript_text"], generation.parse_error)
        )
        if args.judge and args.mode == "live":
            judges[case["id"]] = judge_case(orchestrator, case, generation.raw)
        if args.record and generation.raw is not None:
            _write_fixture(args.fixtures_dir, case, generation.raw)

    full_set = not args.cases
    print_scorecard(
        args.mode, scores, judges, contract_ok, contract_missing, baseline, gate, full_set
    )

    failures = evaluate_gate(scores, contract_ok, baseline, gate, full_set=full_set)
    payload = {
        "mode": args.mode,
        "aggregate_score": round(aggregate(scores), 4),
        "gate": gate,
        "prompt_contract_ok": contract_ok,
        "prompt_contract_missing": contract_missing,
        "metric_averages": {k: round(v, 4) for k, v in metric_averages(scores).items()},
        "cases": {s.case_id: s.as_dict() for s in scores},
        "llm_judge": {k: v for k, v in judges.items() if v is not None},
        "gate_failures": failures,
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"  Machine-readable scorecard: {args.json_out}")

    if args.update_baseline:
        _write_baseline(payload, gate)
        print(f"  Baseline updated: {BASELINE_PATH} (commit the diff)")

    if failures and not args.no_gate:
        print("\n  GATE: FAIL")
        for failure in failures:
            print(f"    - {failure}")
        print("-" * 78)
        return 1
    print("\n  GATE: PASS" if not args.no_gate else "\n  GATE: skipped (--no-gate)")
    print("-" * 78)
    return 0


def _write_fixture(fixtures_dir: Path, case: dict, raw: dict[str, Any]) -> None:
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "_comment": (
            f"Recorded model output for case '{case['id']}'. Regenerate with: "
            f"python evals/run_eval.py --mode live --record --case {case['id']}"
        ),
        "_provenance": "recorded from gemini-2.0-flash via --mode live --record",
        **{k: raw.get(k) for k in SCHEMA_FIELDS},
    }
    path = fixtures_dir / f"{case['id']}.json"
    path.write_text(json.dumps(payload, indent=2) + "\n")


def _write_baseline(payload: dict[str, Any], gate: dict[str, Any]) -> None:
    existing = json.loads(BASELINE_PATH.read_text()) if BASELINE_PATH.exists() else {}
    existing["_comment"] = existing.get(
        "_comment",
        "Committed baseline scores. A prompt change that makes generation worse shows "
        "up as a diff here. Regenerate with --update-baseline and review before merging.",
    )
    existing["gate"] = gate
    existing["aggregate_score"] = payload["aggregate_score"]
    existing["metric_averages"] = payload["metric_averages"]
    existing["cases"] = {
        case_id: {"score": data["score"]} for case_id, data in payload["cases"].items()
    }
    BASELINE_PATH.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n")
