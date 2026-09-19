# Run telemetry

The evals answer "did a change make the output worse?". This answers the other
question a reviewer asks about an LLM pipeline: **what does a run cost, and how
long does it take?**

Before this, nothing in the repo measured either. The README used to claim
"~70-140 seconds end-to-end"; that number came from nowhere and was deleted.
This is the replacement, and its one rule is:

> **Every number is an observation. A value that could not be observed is
> reported as unavailable, with the reason, never as a plausible default.**

That rule is why the demo run below prints `Tokens: unavailable` instead of a
token estimate from a character count, and why `cost` is `null`.

```bash
make demo                                    # prints the table below
python main.py process-episode "Show" 1 4    # same table, real run
python main.py --telemetry-json runs/ ...    # also write a JSON artifact
python main.py --no-telemetry ...            # collect nothing
ANIME_TELEMETRY=0 make demo                  # same, via the environment
```

## What is measured

**Wall-clock per stage**, from `time.perf_counter()` deltas taken around the
real call sites in `agents/workflow_orchestrator.py`. The stage names map onto
the six stages in [architecture.md](architecture.md); two of them
(`persistence`, `quality_profile`) are work the orchestrator does that the
architecture document does not number, and they are reported with `-` rather
than being folded into a neighbouring stage to make the table look tidier.

| Stage | Doc stage | Wraps |
|---|---|---|
| `transcript_discovery` | 1 | `discovery_agent.search_episode_enhanced()` |
| `transcript_parse` | 1 | `transcript_agent.parse_discovered_url()` |
| `content_extraction` | 1-2 | `content_agent.extract_and_analyze()` - fetch + BeautifulSoup parse |
| `summarization` | 2 | `generate_structured_summary()` - the Gemini call |
| `persistence` | - | `db.save_episode()` |
| `character_enrichment` | 3 | ChromaDB character analysis + character-weighted timing |
| `quality_profile` | - | `AdaptiveQualityManager.select_quality_profile()` |
| `prompt_construction` | 4 | the `build_coherent_prompt()` loop over every scene |
| `image_generation` | 4 | `create_images()` - Imagen, or the placeholder fallback |
| `audio_synthesis` | 5 | `wave_file()` - Gemini TTS, or the silent fallback |
| `video_encode` | 5 | `mp4_file_enhanced()` - MoviePy/ffmpeg |

Which stages appear depends on the entry point: `process_episode` and
`process_episode_from_url` start at `content_extraction`; `process_episode_complete`
starts at `transcript_discovery`. A stage that raises is still recorded, with
`ok: false` and the exception, and the exception propagates unchanged - a failed
run's timings are the interesting ones.

**Tokens per LLM call**, taken from the provider's own
`AIMessage.usage_metadata` on the response. Nothing is derived from text length.

**The residual.** The summary prints the run's total wall-clock alongside the
sum of the stages, so the part of a run that is *not* inside an instrumented
stage is visible instead of implied. It is currently ~0.2 ms.

<!-- verified: c262fff sources: core/telemetry.py, scripts/demo.py -->

## How tokens are captured, and why it is done the awkward way

`generate_structured_summary()` calls `model_with_structure.invoke(prompt)`,
where `model_with_structure` came from `with_structured_output()`. That returns a
parsed Pydantic model - the usage metadata of the underlying response is not on
it. Three ways out, and the two rejected ones matter:

- **Switch to `with_structured_output(..., include_raw=True)`** and read the
  usage off the raw message. This changes the return shape of a production
  method that the demo, the e2e suite and the eval harness all drive. Rejected:
  a measurement should not rewrite the thing it measures.
- **Pass `config={"callbacks": [...]}` to `invoke`.** Rejected because the
  offline demo and the e2e fixtures substitute doubles whose signature is
  literally `invoke(self, prompt)`; adding a keyword argument would break every
  offline path in the repo.
- **A context-local callback** (what this does). `core/telemetry.py` registers
  one LangChain configure hook at import and sets a `ContextVar` for the
  duration of the call, so the handler is picked up by the callback manager with
  no change to the call site at all.

Two deliberate differences from langchain-core's own
`get_usage_metadata_callback()`:

1. It registers a *new* global hook on every entry. Per-LLM-call use would grow
   a process-global list by one entry per call across a batch run.
2. It **discards the usage entirely** when the response carries no `model_name`
   in `response_metadata`. Throwing away a measured token count because the
   provider omitted a label is exactly the failure this module exists to
   prevent, so the count is kept with `model: null` instead.

LangChain is imported lazily and defensively. If it is missing, timing still
works and the token fields say so.

## Cost: measured tokens, no shipped prices

**No price table ships with this repo.** Cost appears as `not computed` unless
an operator configures one.

This is a judgement call, so here is the reasoning. A cost figure is
`tokens x price`. The tokens are measured; the price is an assumption, and an
assumption that decays. Checking on 2026-09-18, the model this pipeline pins -
`gemini-2.0-flash`, hardcoded in `WorkflowOrchestrator.__init__` - **is no
longer listed on <https://ai.google.dev/gemini-api/docs/pricing> at all**. A
constant committed here would have been a number no reader could verify against
its own cited source, in a repo whose last cleanup was deleting exactly that
kind of number.

So the prices are configuration:

```bash
ANIME_TELEMETRY_PRICES=prices.json python main.py process-episode "Show" 1 4
```

```json
{
  "currency": "USD",
  "source": "REPLACE ME: where you read these rates",
  "retrieved": "REPLACE ME: the date you read them",
  "models": {
    "gemini-2.0-flash": {"input_per_1m": 0.0, "output_per_1m": 0.0}
  }
}
```

The rates above are zeros on purpose. Fill them in from your own billing console
or a provider price list you have actually opened, and put that reference in
`source`. This document will not hand you a number it cannot stand behind.

The `source` and `retrieved` fields are echoed verbatim into the JSON artifact
and the printed summary, so a cost number is never separable from the claim it
rests on, and the artifact labels its basis as
*"configured price table - an assumption supplied by the operator, not
measured"*. Cost is refused - `null`, with the reason - when tokens were not
measured, when no table is configured, or when the table has no rate for the
model that actually answered.

## What a run prints

Verbatim from `make demo` on 2026-09-18 (macOS, Apple silicon, Python 3.12).
These are measurements, not a computed artifact, so no test can recompute them;
the tag below names the commit they were measured at and the sources they rest
on, and `tests/test_docs_contract.py` fails the build if either source moves
without the numbers being taken again.

<!-- verified: c262fff sources: core/telemetry.py, scripts/demo.py -->

```
------------------------------------------------------------------------------
  RUN TELEMETRY  Neon Lantern Brigade_2026-09-18T21:56:15.875216
------------------------------------------------------------------------------
  stage                     doc      wall_s    share  status
  content_extraction        1-2      0.0006     0.0%  ok
  summarization               2      0.0345     0.3%  ok
  persistence                 -      0.0009     0.0%  ok
  character_enrichment        3      0.0000     0.0%  ok
  quality_profile             -      0.1101     0.9%  ok
  prompt_construction         4      0.0000     0.0%  ok
  image_generation            4      0.3316     2.8%  ok
  audio_synthesis             5      0.1241     1.1%  ok
  video_encode                5     11.1431    94.9%  ok
  measured total                    11.7449   100.0%
  run wall-clock 11.745s (0.0002s outside instrumented stages)

  LLM calls: 1
    episode_summary       tokens unavailable (0.000s)
      reason: no usage metadata was reported (offline replay, a test double, or a provider that omits it)
  Tokens: unavailable (measured only; never estimated)
  Cost:   not computed - no token counts were reported, so cost cannot be derived
------------------------------------------------------------------------------
```

### What you may not conclude from those numbers

**This is not what a real run costs or how long one takes.** The demo replaces
every paid boundary (see the banner `make demo` prints), so:

- `summarization` at 34 ms is the cost of replaying a JSON file. A real Gemini
  call over a full transcript is seconds, and it is the stage whose latency
  varies most.
- `image_generation` at 0.33 s is PIL drawing five captioned title cards. Real
  Imagen generation is network-bound and orders of magnitude slower.
- `audio_synthesis` at 0.12 s is a locally synthesised tone. Real Gemini TTS is
  a network call.
- `character_enrichment` at ~0 is a canned dictionary. The real path embeds
  dialogue into ChromaDB with sentence-transformers.
- `Tokens: unavailable` is correct and expected here: no model was called.
- The `94.9%` share for `video_encode` is an artifact of everything else being
  faked. **Do not read it as "the pipeline is encode-bound."**

What the demo numbers *are* good for: the encode and the HTML parse are real
production code doing real work, the instrumentation demonstrably records the
stages in order, and the shape of the report is what a real run produces.
Getting real numbers for the other stages needs a key and a network, and this
document will not pretend otherwise until someone runs it and pastes them here.

## Retrieving the data

Three ways, in increasing order of durability:

1. **Printed** at the end of every run, unless `ANIME_TELEMETRY=0`.
2. **In the result payload.** `process_episode()` returns a `telemetry` key
   holding the full record. The collector also stays on the orchestrator as
   `orchestrator.telemetry` after any entry point returns.
3. **As a JSON artifact**, when `ANIME_TELEMETRY_JSON` (or `--telemetry-json`)
   names a file or a directory. The artifact carries `schema_version: 1`, every
   stage, every LLM call, the token totals and the cost block with its basis.

### Why JSON and not SQLite

The natural home for run history is `core/database.py`, next to the episodes
table - that is what makes "has stage 5 got slower over the last month?"
answerable with a query rather than with a directory of files. **That schema
change was deliberately not made here**, because `core/database.py` is outside
this change's scope. The shape it wants is a `run_telemetry` table keyed by
`job_id` with a row per stage (`stage`, `doc_stage`, `wall_seconds`, `ok`) and a
run-level row for tokens and cost; `to_dict()` is already in exactly that shape.
Until then the JSON artifact is the durable record, and it is deliberately
versioned so a later importer can backfill.

## What is not measured

Stated plainly, because an incomplete instrument that implies completeness is
the thing this repo is trying to stop doing:

- **Memory and CPU.** Nothing samples RSS or CPU time. `record_quality_metrics`
  now receives a *measured* `processing_time_ms` (it used to receive a literal
  `0` with a comment admitting it was fake), and `memory_usage_mb` /
  `output_quality_score` are passed as `null` rather than as invented numbers -
  a consumer can tell "not measured" from "measured zero".
- **Sub-stage granularity.** `image_generation` is one number for all scenes,
  not one per image; `prompt_construction` is the whole loop. Per-scene timing
  is where a real Imagen run's variance lives and it is not captured yet.
- **Retries, rate limits and cache hits.** `core/content_cache.py` is not
  instrumented, so a cached run is indistinguishable from an uncached one in the
  report.
- **The quality agents.** `agents/quality_agents/` runs post-hoc validation that
  no stage timer covers.
- **Bytes over the wire, and output size.** No network accounting; the MP4's
  size and duration are printed by the demo, not by telemetry.
- **Anything about a real paid run.** No live run has been recorded. Every
  number in this document is from offline mode.
- **Cross-run aggregation.** There is no p50/p95, because there is no run store
  (see the schema note above). One run, one report.

## LangSmith

`LANGSMITH_API_KEY` sits unused in `.env`, and LangChain would pick up
`LANGCHAIN_TRACING_V2=true` on its own to give per-call traces, latencies and
token counts in a hosted UI - considerably more than this module does.

It is deliberately not wired up. It sends prompts and completions to a
third-party service, which is a decision about data handling and an external
dependency, not a logging tweak; it does nothing offline, which is where this
repo's demo and CI live; and it would make the answer to "what does a run cost?"
require an account. The two are complementary: this module is the always-on,
offline, no-account floor. If LangSmith is switched on later, it should be an
explicit opt-in with its own note here.
