# ADR 0005 — Report measurements or `null`, never a plausible default

**Status:** Accepted · **Date:** 2026-09-18 · **Commit:** `c262fff`

## Context

The second question about an LLM pipeline, after "how do you know a change made
it worse", is "what does a run cost and how long does it take". There was no
answer. The README once claimed "~70-140 seconds end-to-end" with nothing
measuring it; it was deleted as unverifiable in `21f2eae`. Meanwhile
`record_quality_metrics` posted `processing_time_ms: 0` ("would be measured in
real implementation") and `output_quality_score: 0.9` ("based on quality
validation") — two numbers in the database that measured nothing.

## Decision

`core/telemetry.py` records per-stage wall clock via `perf_counter` and per-call
token usage, emits a stage table and an optional JSON artifact, and is fully
inert when `ANIME_TELEMETRY=0`. Eleven stage timers sit at real call boundaries
across all three entry points, mapped to the six stages in
[../architecture.md](../architecture.md).

The rule: **every number is an observation; a value that could not be observed is
reported as unavailable, with the reason, never as a plausible default.**

So **no price table ships.** The pricing page was fetched on 2026-09-18 and
`gemini-2.0-flash` — the model this orchestrator hardcodes — is no longer listed.
Any constant committed here would have been unverifiable against its own cited
source, and in *this* repo, of all repos, that is not a number to invent. Cost is
`null` with a stated reason unless the operator supplies
`ANIME_TELEMETRY_PRICES`, and any figure derived from it is labelled "a
configured assumption supplied by the operator, not measured", with its source
and retrieval date echoed alongside.

The two fabricated metrics became a real elapsed time and an explicit `None`
where no validator runs.

Token capture shaped the design more than the timing did. `with_structured_output()`
returns a parsed model carrying no usage metadata. `include_raw=True` was rejected
because it changes a production return shape the demo, e2e tests and evals all
drive. A per-call `callbacks` config was rejected because the offline doubles take
`invoke(self, prompt)`. A LangChain configure hook plus a `ContextVar` leaves call
sites unchanged.

## Consequences

Good: every figure the system prints can be traced to something that happened.
LangChain is imported lazily, so timing works without it and tokens simply read
as unavailable.

Accepted costs:

- **The repo cannot answer "what does a run cost in dollars" out of the box.**
  That is a real gap in a portfolio piece, and the honest `null` is less
  impressive than a number would have been. It is also the only defensible
  option once the cited source stopped listing the model.
- **The demo numbers are unrepresentative and say so** — summarisation replays a
  fixture, images are title cards, audio is a tone, so `video_encode` at 95% is
  an artifact of what is faked, not evidence the pipeline is encode-bound.
- No cross-run aggregation yet: there is no `run_telemetry` table, so p50/p95
  over history is not available. The artifact carries `schema_version: 1` for
  backfill.

See [../telemetry.md](../telemetry.md).
