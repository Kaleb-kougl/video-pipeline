"""
Run telemetry: what a pipeline run actually cost, in wall-clock and in tokens.

Design rules, in order of importance
------------------------------------
1. **Every number is an observation.** Wall-clock comes from
   :func:`time.perf_counter`. Token counts come from the provider's own
   ``usage_metadata`` on the response. Nothing here estimates, extrapolates or
   back-fills. A value that could not be observed is recorded as ``None`` with
   a machine-readable reason next to it, never as a plausible-looking number.
2. **Cost is never measured, so it is never presented as measured.** A token
   count times a price is arithmetic over a *configured assumption*. No price
   table ships with this repo (see ``docs/telemetry.md`` for why), so cost is
   reported as "not computed" unless an operator supplies one, and when they
   do, the output carries that table's own ``source``/``retrieved`` fields so
   the reader can see exactly what the number rests on.
3. **Inert unless asked.** ``RunTelemetry(enabled=False)`` - which is what
   ``ANIME_TELEMETRY=0`` produces - keeps no state and does no formatting; the
   context managers become pass-throughs. Nothing in this module imports
   anything outside the standard library at module scope, and the one optional
   LangChain import is guarded, so instrumentation cannot break an offline run.
4. **Instrumentation never changes behaviour.** Stage timers re-raise whatever
   the body raised (recording the stage as failed on the way out), and the
   token collector is a LangChain *callback*, so the call signature and return
   value of the instrumented ``invoke`` are untouched. That matters: the
   structured-output path returns a Pydantic model, and several test doubles
   implement ``invoke(self, prompt)`` with no ``config`` parameter.
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

#: Environment switch. Any of these values (case-insensitive) disables
#: collection entirely; anything else, including unset, leaves it on.
_DISABLED_VALUES = {"0", "false", "no", "off"}

ENV_ENABLED = "ANIME_TELEMETRY"
ENV_JSON = "ANIME_TELEMETRY_JSON"
ENV_PRICES = "ANIME_TELEMETRY_PRICES"

#: Stage names, in pipeline order, mapped to the stage numbers in
#: ``docs/architecture.md``. Stages the orchestrator drives but the
#: architecture document does not number (persistence, quality-profile
#: selection) map to ``None`` rather than being forced into a bucket.
STAGE_DOC_REFERENCE: dict[str, str | None] = {
    "transcript_discovery": "1",
    "transcript_parse": "1",
    "content_extraction": "1-2",
    "summarization": "2",
    "persistence": None,
    "character_enrichment": "3",
    "quality_profile": None,
    "prompt_construction": "4",
    "image_generation": "4",
    "audio_synthesis": "5",
    "video_encode": "5",
}


@dataclass(frozen=True)
class StageTiming:
    """One measured stage. ``wall_seconds`` is a :func:`time.perf_counter` delta."""

    name: str
    wall_seconds: float
    started_at: str
    ok: bool
    doc_stage: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.name,
            "architecture_doc_stage": self.doc_stage,
            "wall_seconds": round(self.wall_seconds, 4),
            "started_at": self.started_at,
            "ok": self.ok,
            "error": self.error,
        }


@dataclass(frozen=True)
class LLMCallRecord:
    """
    One instrumented model invocation.

    ``input_tokens``/``output_tokens`` are ``None`` when the provider returned
    no usage metadata - which is the normal case for every offline run in this
    repo, because the test doubles and the demo replay recorded objects rather
    than calling a model. ``tokens_unavailable_reason`` says which it was.
    """

    label: str
    wall_seconds: float
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    tokens_unavailable_reason: str | None = None

    @property
    def has_tokens(self) -> bool:
        return self.input_tokens is not None or self.output_tokens is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "wall_seconds": round(self.wall_seconds, 4),
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "tokens_unavailable_reason": self.tokens_unavailable_reason,
        }


@dataclass(frozen=True)
class PriceTable:
    """
    Operator-supplied token prices. **Configuration, not measurement.**

    Loaded from a JSON file named by ``ANIME_TELEMETRY_PRICES``::

        {
          "currency": "USD",
          "source": "<where you read these rates>",
          "retrieved": "<the date you read them>",
          "models": {
            "gemini-2.0-flash": {"input_per_1m": 0.0, "output_per_1m": 0.0}
          }
        }

    ``source`` and ``retrieved`` are echoed verbatim into the telemetry
    artifact so a cost figure is never separable from the claim it rests on.
    Nothing validates that they are true - that is the operator's assertion,
    and the report labels it as such.
    """

    models: dict[str, dict[str, float]] = field(default_factory=dict)
    currency: str = "USD"
    source: str | None = None
    retrieved: str | None = None

    @classmethod
    def load(cls, path: str | Path) -> PriceTable:
        raw = json.loads(Path(path).read_text())
        models = {
            str(name): {str(k): float(v) for k, v in rates.items()}
            for name, rates in (raw.get("models") or {}).items()
        }
        return cls(
            models=models,
            currency=str(raw.get("currency", "USD")),
            source=raw.get("source"),
            retrieved=raw.get("retrieved"),
        )

    def cost_for(self, model: str | None, input_tokens: int, output_tokens: int) -> float | None:
        """Price the call, or ``None`` when this table says nothing about the model."""
        rates = self.models.get(model or "")
        if rates is None:
            return None
        return (
            input_tokens * rates.get("input_per_1m", 0.0)
            + output_tokens * rates.get("output_per_1m", 0.0)
        ) / 1_000_000

    def to_dict(self) -> dict[str, Any]:
        return {
            "basis": "configured price table - an assumption supplied by the operator, not measured",
            "currency": self.currency,
            "source": self.source,
            "retrieved": self.retrieved,
            "models_priced": sorted(self.models),
        }


class RunTelemetry:
    """
    Collects per-stage wall-clock and per-call token usage for one pipeline run.

    Typical use inside the orchestrator::

        with self.telemetry.stage("content_extraction"):
            content_result = self.content_agent.extract_and_analyze(url)

        with self.telemetry.llm_call("episode_summary"):
            response = self.model_with_structure.invoke(prompt)

    Both are safe on a disabled collector and both re-raise.
    """

    def __init__(
        self,
        run_id: str = "unattributed",
        *,
        enabled: bool = True,
        prices: PriceTable | None = None,
    ) -> None:
        self.run_id = run_id
        self.enabled = enabled
        self.prices = prices
        self.started_at: str | None = None
        self.stages: list[StageTiming] = []
        self.llm_calls: list[LLMCallRecord] = []
        self._run_started: float | None = None
        self._run_wall: float | None = None

    # -- construction -------------------------------------------------------

    @classmethod
    def from_env(cls, run_id: str, env: dict[str, str] | None = None) -> RunTelemetry:
        """
        Build a collector honouring ``ANIME_TELEMETRY`` and ``ANIME_TELEMETRY_PRICES``.

        A price file that is missing or malformed is a configuration problem,
        not a run-stopping one: it is logged and cost simply stays uncomputed.
        """
        environ = os.environ if env is None else env
        enabled = environ.get(ENV_ENABLED, "1").strip().lower() not in _DISABLED_VALUES
        prices: PriceTable | None = None
        price_path = environ.get(ENV_PRICES)
        if enabled and price_path:
            try:
                prices = PriceTable.load(price_path)
            except Exception as exc:  # noqa: BLE001 - never fail a run over telemetry config
                logger.warning(f"Ignoring unreadable telemetry price table {price_path}: {exc}")
        return cls(run_id, enabled=enabled, prices=prices)

    # -- measurement --------------------------------------------------------

    def start_run(self, run_id: str | None = None) -> None:
        """Reset for a new run. Called by each orchestrator entry point."""
        if run_id is not None:
            self.run_id = run_id
        self.stages = []
        self.llm_calls = []
        self._run_wall = None
        if not self.enabled:
            return
        self.started_at = datetime.now().isoformat(timespec="seconds")
        self._run_started = time.perf_counter()

    def end_run(self) -> None:
        """
        Stop the run clock. Idempotent: entry points call this on the way out of
        both the success and the failure branch *and* from ``finally``, and the
        first call is the one that counts, so the number in the returned payload
        and the number in the printed summary are the same number.
        """
        if self.enabled and self._run_started is not None and self._run_wall is None:
            self._run_wall = time.perf_counter() - self._run_started

    @contextmanager
    def stage(self, name: str, doc_stage: str | None = None) -> Iterator[None]:
        """
        Time a pipeline stage. A stage that raises is still recorded, with
        ``ok=False`` and the exception's repr, and the exception propagates
        unchanged - a partial run's timings are exactly the interesting ones.
        """
        if not self.enabled:
            yield
            return
        started_at = datetime.now().isoformat(timespec="seconds")
        start = time.perf_counter()
        ok = True
        error: str | None = None
        try:
            yield
        except BaseException as exc:
            ok = False
            error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            self.stages.append(
                StageTiming(
                    name=name,
                    wall_seconds=time.perf_counter() - start,
                    started_at=started_at,
                    ok=ok,
                    doc_stage=doc_stage if doc_stage is not None else STAGE_DOC_REFERENCE.get(name),
                    error=error,
                )
            )

    @contextmanager
    def llm_call(self, label: str) -> Iterator[None]:
        """
        Time a model invocation and capture its token usage *if the provider
        reported any*.

        Usage is collected through LangChain's ``get_usage_metadata_callback``
        rather than by reading the return value, for two reasons. The
        structured-output path returns a parsed Pydantic model that carries no
        usage at all, and a callback rides the existing callback manager, so
        the instrumented call keeps its exact signature - important because the
        demo and the e2e tests substitute ``invoke(self, prompt)`` doubles that
        would reject a ``config=`` argument.

        When LangChain is absent, or the model is a double that never notifies
        callbacks, the call is still timed and the token fields are recorded as
        unavailable with the reason.
        """
        if not self.enabled:
            yield
            return

        collector = _UsageCollector()
        start = time.perf_counter()
        try:
            with collector:
                yield
        finally:
            elapsed = time.perf_counter() - start
            self.llm_calls.extend(
                _records_from_usage(label, elapsed, collector.records, collector.reason)
            )

    # -- reporting ----------------------------------------------------------

    @property
    def measured_seconds(self) -> float:
        return sum(s.wall_seconds for s in self.stages)

    @property
    def run_wall_seconds(self) -> float | None:
        return self._run_wall

    def token_totals(self) -> tuple[int | None, int | None]:
        """Summed input/output tokens, or ``(None, None)`` if nothing reported any."""
        calls = [c for c in self.llm_calls if c.has_tokens]
        if not calls:
            return (None, None)
        return (
            sum(c.input_tokens or 0 for c in calls),
            sum(c.output_tokens or 0 for c in calls),
        )

    def cost(self) -> tuple[float | None, str]:
        """
        ``(amount, explanation)``. The amount is ``None`` whenever it would have
        to be invented; the explanation always says which reason applied.
        """
        inp, out = self.token_totals()
        if inp is None or out is None:
            return (None, "no token counts were reported, so cost cannot be derived")
        if self.prices is None:
            return (None, "no price table configured (set ANIME_TELEMETRY_PRICES)")
        total = 0.0
        priced_any = False
        for call in self.llm_calls:
            if not call.has_tokens:
                continue
            amount = self.prices.cost_for(
                call.model, call.input_tokens or 0, call.output_tokens or 0
            )
            if amount is None:
                continue
            priced_any = True
            total += amount
        if not priced_any:
            return (None, "the configured price table lists no rate for the models used")
        return (total, "configured rates x measured tokens - the rates are an assumption")

    def to_dict(self) -> dict[str, Any]:
        inp, out = self.token_totals()
        amount, cost_note = self.cost()
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "enabled": self.enabled,
            "wall_seconds": None if self._run_wall is None else round(self._run_wall, 4),
            "measured_stage_seconds": round(self.measured_seconds, 4),
            "stages": [s.to_dict() for s in self.stages],
            "llm_calls": [c.to_dict() for c in self.llm_calls],
            "tokens": {
                "input": inp,
                "output": out,
                "note": (
                    "measured from provider usage metadata"
                    if inp is not None
                    else "unavailable - no LLM response in this run carried usage metadata"
                ),
            },
            "cost": {
                "amount": amount,
                "currency": None if self.prices is None else self.prices.currency,
                "note": cost_note,
                "price_table": None if self.prices is None else self.prices.to_dict(),
            },
            "schema_version": 1,
        }

    def format_summary(self, width: int = 78) -> str:
        """A fixed-width stage table suitable for a terminal."""
        if not self.enabled:
            return "telemetry disabled"
        rule = "-" * width
        total = self.measured_seconds
        lines = [
            rule,
            f"  RUN TELEMETRY  {self.run_id}",
            rule,
            f"  {'stage':<24}{'doc':>5}{'wall_s':>12}{'share':>9}  status",
        ]
        for item in self.stages:
            share = (item.wall_seconds / total * 100) if total else 0.0
            doc = item.doc_stage or "-"
            status = "ok" if item.ok else f"FAILED ({item.error})"
            lines.append(
                f"  {item.name:<24}{doc:>5}{item.wall_seconds:>12.4f}{share:>8.1f}%  {status}"
            )
        lines.append(
            f"  {'measured total':<24}{'':>5}{total:>12.4f}{100.0 if total else 0.0:>8.1f}%"
        )
        if self._run_wall is not None:
            outside = self._run_wall - total
            # Four decimals on the uninstrumented remainder on purpose: the gap
            # between the stages and the run is normally sub-millisecond, and
            # printing it as "0.000s" reads like a hardcoded zero rather than a
            # measurement that happens to be small.
            lines.append(
                f"  run wall-clock {self._run_wall:.3f}s "
                f"({outside:.4f}s outside instrumented stages)"
            )

        inp, out = self.token_totals()
        lines.append("")
        if not self.llm_calls:
            lines.append("  LLM calls: none instrumented in this run")
        else:
            lines.append(f"  LLM calls: {len(self.llm_calls)}")
            for call in self.llm_calls:
                if call.has_tokens:
                    lines.append(
                        f"    {call.label:<22}{call.model or 'unknown model':<24}"
                        f"in={call.input_tokens} out={call.output_tokens} "
                        f"({call.wall_seconds:.3f}s)"
                    )
                else:
                    lines.append(
                        f"    {call.label:<22}tokens unavailable ({call.wall_seconds:.3f}s)"
                    )
                    lines.append(f"      reason: {call.tokens_unavailable_reason}")
        if inp is None:
            lines.append("  Tokens: unavailable (measured only; never estimated)")
        else:
            lines.append(f"  Tokens: input={inp} output={out} (from provider usage metadata)")
        amount, note = self.cost()
        if amount is None:
            lines.append(f"  Cost:   not computed - {note}")
        else:
            currency = self.prices.currency if self.prices else ""
            source = (self.prices.source or "unspecified source") if self.prices else ""
            retrieved = (self.prices.retrieved or "undated") if self.prices else ""
            lines.append(f"  Cost:   {amount:.6f} {currency} - {note}")
            lines.append(f"          rates from {source} (retrieved {retrieved})")
        lines.append(rule)
        return "\n".join(lines)

    def write_json(self, destination: str | Path) -> Path:
        """
        Write the artifact. A directory (or a path ending in ``/``) gets a
        ``telemetry-<run id>.json`` inside it; anything else is used as the file
        name. Returns the path written.
        """
        path = Path(destination)
        if path.is_dir() or str(destination).endswith(os.sep):
            path.mkdir(parents=True, exist_ok=True)
            path = path / f"telemetry-{_slug(self.run_id)}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n")
        return path

    def emit(self, *, stream_summary: bool = True, env: dict[str, str] | None = None) -> None:
        """
        Publish the run: a one-line INFO log, the stage table on stdout, and a
        JSON artifact when ``ANIME_TELEMETRY_JSON`` names one.

        Failures here are swallowed deliberately. Telemetry that can break a
        render is worse than no telemetry.
        """
        if not self.enabled:
            return
        environ = os.environ if env is None else env
        try:
            wall = self._run_wall
            logger.info(
                f"Run telemetry {self.run_id}: "
                f"{'unknown' if wall is None else f'{wall:.2f}'}s wall, "
                f"{len(self.stages)} stages, {len(self.llm_calls)} LLM calls"
            )
            if stream_summary:
                print(self.format_summary())
            target = environ.get(ENV_JSON)
            if target:
                written = self.write_json(target)
                logger.info(f"Run telemetry written to {written}")
                if stream_summary:
                    print(f"  telemetry JSON: {written}")
        except Exception as exc:  # noqa: BLE001 - reporting must never fail a run
            logger.warning(f"Telemetry reporting failed (run is unaffected): {exc}")


# ---------------------------------------------------------------------------
# Token capture helpers
# ---------------------------------------------------------------------------


#: Set while an ``llm_call`` block is open. LangChain's callback manager reads
#: it through a configure hook, which is why an instrumented ``invoke`` needs no
#: ``config=`` argument. Declared once at module scope and registered once
#: (see ``_ensure_hook``): ``get_usage_metadata_callback`` from langchain-core
#: registers a *fresh* hook on every entry, which would grow a global list by
#: one entry per LLM call over a long batch run.
_USAGE_VAR: ContextVar[Any] = ContextVar("anime_telemetry_usage", default=None)
_hook_state: dict[str, Any] = {"registered": False, "handler_class": None}


def _ensure_hook() -> bool:
    """Register the configure hook once. False means LangChain is unavailable."""
    if _hook_state["registered"]:
        return _hook_state["handler_class"] is not None
    _hook_state["registered"] = True
    try:
        from langchain_core.callbacks import BaseCallbackHandler
        from langchain_core.tracers.context import register_configure_hook
    except Exception:  # noqa: BLE001 - LangChain is optional at runtime, by design
        return False

    class _TelemetryUsageHandler(BaseCallbackHandler):  # type: ignore[misc]
        """
        Records ``AIMessage.usage_metadata`` for every chat completion.

        Deliberately *not* langchain-core's own ``UsageMetadataCallbackHandler``:
        that one drops the usage entirely unless the response also carries a
        ``model_name`` in ``response_metadata``. Losing a measured token count
        because a provider omitted a label is exactly the failure this module
        exists to avoid, so tokens are kept with ``model=None`` instead.
        """

        def __init__(self) -> None:
            super().__init__()
            self.records: list[tuple[str | None, dict[str, Any]]] = []

        def on_llm_end(self, response: Any, **kwargs: Any) -> None:
            for generation in _flatten_generations(response):
                message = getattr(generation, "message", None)
                usage = getattr(message, "usage_metadata", None)
                metadata = getattr(message, "response_metadata", None) or {}
                if not isinstance(usage, dict) or not usage:
                    # Providers that only fill the legacy LLMResult.llm_output.
                    legacy = (getattr(response, "llm_output", None) or {}).get("token_usage")
                    usage = legacy if isinstance(legacy, dict) else None
                if isinstance(usage, dict) and usage:
                    model = metadata.get("model_name") or metadata.get("model")
                    self.records.append((str(model) if model else None, dict(usage)))

    register_configure_hook(_USAGE_VAR, inheritable=True)
    _hook_state["handler_class"] = _TelemetryUsageHandler
    return True


def _flatten_generations(response: Any) -> list[Any]:
    generations = getattr(response, "generations", None)
    if not isinstance(generations, list):
        return []
    flat: list[Any] = []
    for group in generations:
        flat.extend(group if isinstance(group, list) else [group])
    return flat


class _UsageCollector:
    """
    Context manager that makes the usage handler active for the duration of a
    model call and exposes whatever it saw.

    Degrades to collecting nothing (and saying so) when LangChain is missing, so
    ``core.telemetry`` imports nothing it cannot live without.
    """

    NO_LANGCHAIN = "langchain_core callbacks are not available in this process"
    NO_USAGE = (
        "no usage metadata was reported (offline replay, a test double, "
        "or a provider that omits it)"
    )

    def __init__(self) -> None:
        self.records: list[tuple[str | None, dict[str, Any]]] = []
        self.reason: str = self.NO_USAGE
        self._token: Any = None

    def __enter__(self) -> _UsageCollector:
        if not _ensure_hook():
            self.reason = self.NO_LANGCHAIN
            return self
        self._token = _USAGE_VAR.set(_hook_state["handler_class"]())
        return self

    def __exit__(self, *exc_info: Any) -> None:
        if self._token is None:
            return
        handler = _USAGE_VAR.get()
        if handler is not None:
            self.records = list(handler.records)
        _USAGE_VAR.reset(self._token)
        self._token = None


def _records_from_usage(
    label: str,
    elapsed: float,
    usage: list[tuple[str | None, dict[str, Any]]],
    reason: str,
) -> list[LLMCallRecord]:
    """
    Turn observed ``(model, usage_metadata)`` pairs into records. An empty list
    yields one record with the tokens marked unavailable, because the call still
    happened and its latency is real even when its token count is unknowable.
    """
    records: list[LLMCallRecord] = []
    for model, counts in usage:
        records.append(
            LLMCallRecord(
                label=label,
                wall_seconds=elapsed,
                model=model,
                input_tokens=_as_int(counts.get("input_tokens", counts.get("prompt_tokens"))),
                output_tokens=_as_int(counts.get("output_tokens", counts.get("completion_tokens"))),
                total_tokens=_as_int(counts.get("total_tokens")),
            )
        )
    if not records:
        records.append(
            LLMCallRecord(
                label=label,
                wall_seconds=elapsed,
                tokens_unavailable_reason=reason,
            )
        )
    return records


def _as_int(value: Any) -> int | None:
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _slug(text: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in text)[:120]
