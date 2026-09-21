# Operations: cost and latency

What a run costs before you start it, what the instrument measures, and what it
does not. Derived from `core/telemetry.py`, `agents/workflow_orchestrator.py`,
`config/settings.py`, `core/schemas.py`, `main.py` and `media/media_utils.py`,
re-read against the scene cap at `d58f1c7` and the image-generator seam at
`f2597bf`, then again at `59fd32d`, which moved generator construction to the
composition root.
[telemetry.md](telemetry.md) is the design rationale; this file is the operator
view. For procedures see [runbook.md](runbook.md).

<!-- verified: 59fd32d sources: core/telemetry.py, agents/workflow_orchestrator.py, media/media_utils.py, config/settings.py, core/schemas.py, main.py -->

## What a run costs in API calls

Counted from the call sites, not estimated. Per episode, with `--full`:

| Calls | Service | Model | Where | Metered? |
|---|---|---|---|---|
| 1 | Gemini text | `gemini-2.0-flash` | `generate_structured_summary` → `model_with_structure.invoke` | **yes** — the only token-instrumented call, labelled `episode_summary` |
| *N* ≤ 48 | Imagen | `imagen-3.0-generate-002` | `create_images` → one `create_image` per item, capped at `VideoConfig.max_scenes` | no |
| 1 | Gemini TTS | `gemini-2.5-flash-preview-tts` | `wave_file`, one call for the whole narration | no |
| 0 | — | — | character enrichment: ChromaDB + sentence-transformers, local | n/a |

***N* is bounded: at most `VideoConfig.max_scenes`, which defaults to 48.**
`create_images` is called once per element of `enhanced_episode["scenes"]`,
which is built one-per-`plot_point`, and the plot points still come back from a
model — but `core.schemas.enforce_scene_cap` truncates the list at the point of
use, so one Gemini response can no longer decide an unbounded image bill. Both
paid paths are capped: the episode path in
`WorkflowOrchestrator.generate_all_media`, and the season-summary path in
`AnimeVideoGenerator._parse_summary_to_concepts` (main and five-concept
fallback alike), which was independently unbounded.

**Where 48 comes from.** It is derived, not picked:
`ceil(max_duration_minutes × 60 × visual_time_ratio / max_concept_duration)` =
`ceil(15 × 60 × 0.80 / 15.0)` = 48 — the scenes needed to fill the longest
supported video at the longest permitted per-scene duration.
`visual_time_ratio` (0.80, the share of runtime given to visuals) is a named
field for exactly this reason; it used to be a bare `* 0.8` inside
`_calculate_visual_timing`. Set this way the cap bounds worst-case spend
without being able to shorten any video the current timing rules could
otherwise have filled.

```python
from config.settings import get_settings

video_config = get_settings().video_config
print(video_config.max_scenes)  # 48
print(video_config.scenes_to_fill(5), video_config.scenes_to_fill(15))  # 16 48
```

**Changing it.** There is no CLI flag and no environment variable: `Settings` is
a plain `BaseModel`, not a `BaseSettings`, so the `env_prefix` in its inner
`Config` is inert. `VideoConfig` is frozen, so replace it whole before anything
constructs an orchestrator — or edit the default in `config/settings.py`:

```python
from config.settings import VideoConfig, update_settings

update_settings(video_config=VideoConfig(max_scenes=12))
```

`max_scenes` is validated `1 ≤ n ≤ 200`. Lowering it is a real cost/quality
trade rather than a free win: below `scenes_to_fill(target_minutes)` the visuals
can no longer cover the narration, and `_calculate_visual_timing` logs a
WARNING naming the shortfall and the concept count that would be needed rather
than quietly rendering a short video. The default never trips that warning.

**Truncation is lossy and loud.** It keeps the first `max_scenes` entries, so
what gets dropped is the end of the episode — chosen over evenly-spaced
sampling because the cap is set to bind only on a runaway response. A
truncation logs at WARNING with the count the model produced, the count being
generated and the number dropped, naming `video_config.max_scenes` as the knob.
Nothing is discarded silently. Only the *images* are capped: the untruncated
plot-point list is still persisted to `episodes.plot_points`, so the summary
in the database can legitimately list more scenes than the video renders.

**What is still variable.** A ceiling is not a quota. A response *under* the cap
spends exactly what it asks for, so per-episode image spend still ranges freely
from one call to `max_scenes` and remains the largest single source of cost
variance in a run. The change made that variance bounded and knowable in
advance; it did not make it fixed. `max_scenes` is the number to take to a
worst-case billing estimate, not the number to expect from a typical run.

**One client per run is not a cost change.** Since `59fd32d` the Imagen client
is constructed once, at the composition root, and forwarded to every frame
(`media.media_utils.resolve_image_generator` → `create_images` →
`create_image`); before that `create_image` built one per image, so a
twelve-scene episode built twelve. Constructing a client is not a billed call,
so the table above is unchanged — the bill is still one `generate_images`
request per scene. What changed is that N clients became one, and that the
*reason* an unavailable generator gives is now decided once per run rather than
re-derived per frame. The per-frame messages are identical either way.

A season batch is this multiplied by the number of episodes not skipped. A
resumed run pays nothing for an episode recorded as `succeeded`: no discovery,
no model call, no render, not even the 2–5 s politeness sleep.

Transcript-only runs (`process-episode`/`process-season` without `--full`) make
no paid calls at all — discovery and persistence only.

## What telemetry measures

`core.telemetry.RunTelemetry` collects two things, both observations:

- **Wall-clock per stage**, from `time.perf_counter()` deltas around the real
  call sites. Eleven stage names are defined in `STAGE_DOC_REFERENCE`; which
  appear depends on the entry point (`process_episode_complete` starts at
  `transcript_discovery`, the other two at `content_extraction`). A stage that
  raises is recorded with `ok: false` and the exception, and the exception
  propagates unchanged.
- **Tokens per LLM call**, read from the provider's own `usage_metadata` via a
  LangChain callback. Nothing is derived from text length.

The printed summary adds the run wall-clock alongside the sum of the stages, so
the uninstrumented residual is visible rather than implied.

Reading the table: the `share` column is a share of the **measured** total, not
of the run. If the residual is large, the shares are describing a shrinking
fraction of what happened. Treat a `FAILED` row as the interesting one — a
partial run's timings are why the collector records failures at all.

Ad-hoc measurement of anything, without the CLI:

```python
from core.telemetry import RunTelemetry

telemetry = RunTelemetry.from_env("adhoc")
telemetry.start_run()
with telemetry.stage("video_encode"):
    ...  # the work
telemetry.end_run()
print(telemetry.format_summary())
```

## Switches

| Switch | Effect |
|---|---|
| `ANIME_TELEMETRY=0` (or `false`/`no`/`off`) | Inert collector: no state, no formatting, context managers become pass-throughs |
| `--no-telemetry` | Sets the above before any orchestrator is constructed |
| `ANIME_TELEMETRY_JSON=<path>` / `--telemetry-json <path>` | Also write the artifact. A directory gets `telemetry-<job id>.json`; anything else is the filename |
| `ANIME_TELEMETRY_PRICES=<file>` | Supply the price table — see below |

The global flags must precede the subcommand. `RunTelemetry.from_env` is read at
orchestrator construction time, which is why the CLI writes the environment
variables rather than passing arguments: one contract for the CLI, a bare
`python -c` driver and the container.

Three ways to retrieve a report, in increasing durability: printed at the end of
every run; on `orchestrator.telemetry` and in the `process_episode()` result
payload; and persisted to the `run_telemetry` table by `_record_telemetry`
(plus the JSON artifact when configured). See
[data-model.md](data-model.md#run_telemetry).

## Cost: no price table ships

**`cost.amount` is `null` unless you supply prices.** This is a deliberate
refusal, not an omission. A cost figure is `tokens × price`: the tokens are
measured, the price is an assumption that decays. As of 2026-09-18 the model
this pipeline pins — `gemini-2.0-flash`, hardcoded in
`WorkflowOrchestrator.__init__` — is no longer listed on Google's public pricing
page at all, so any constant committed here would be a number no reader could
check against its own cited source.

Supply one as configuration:

```bash
ANIME_TELEMETRY_PRICES=prices.json python main.py process-episode "My Hero Academia" 1 4 --full
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

The zeros are intentional. Fill them from a billing console or price list you
have actually opened and name it in `source`.

**Why it is labelled an assumption.** `PriceTable.to_dict()` stamps every report
with `"basis": "configured price table - an assumption supplied by the operator,
not measured"`, and echoes your `source` and `retrieved` verbatim into both the
JSON artifact and the printed summary. Nothing validates them — they are your
claim, and the report says so rather than laundering it into a measurement. A
price file that is missing or malformed is logged and ignored; cost simply stays
uncomputed rather than failing the run.

Cost is refused, with the reason recorded, in three distinct cases:

| Condition | `cost.note` |
|---|---|
| No usage metadata in the run | `no token counts were reported, so cost cannot be derived` |
| No table configured | `no price table configured (set ANIME_TELEMETRY_PRICES)` |
| Table has no rate for the model that answered | `the configured price table lists no rate for the models used` |

Note the coverage gap: only the summarisation call is token-instrumented, so
even a complete price table prices **one** of the three paid services. Imagen
and TTS spend is invisible to this instrument. Your billing console is the
authority on what a run actually cost.

## The demo numbers are not production numbers

[telemetry.md](telemetry.md#what-a-run-prints) contains a verbatim `make demo`
table. It is real output, and it is unrepresentative on purpose: the demo
replaces every paid boundary. `summarization` at 34 ms is a JSON file being
replayed; `image_generation` at 0.33 s is PIL drawing title cards;
`audio_synthesis` is a locally synthesised tone; `character_enrichment` at ~0 is
a canned dictionary. One caveat on that 0.33 s: it was measured before
`f2597bf`, when the demo was still building a real Imagen client per frame and
having the connection blocked by its own socket guard, so it covers work the
demo no longer does — and `59fd32d` removed the rest of it, since the stage now
holds a generator resolved once at construction and each frame only re-raises
the stored reason. The order of magnitude is unaffected — it is still PIL — but
the table has not been re-measured, and if anything it now overstates the
stage. The resulting 94.9% share for `video_encode` is an artifact
of everything else being faked — **do not read it as "the pipeline is
encode-bound"**.

What the demo numbers are good for: the HTML parse and the encode are real
production code doing real work, the instrumentation demonstrably records the
stages in order, and the report has the shape a real run produces.

**No live paid run has been recorded.** Nobody has published real latency or
token figures for this pipeline, and this document will not invent them.

## Known unmeasured dimensions

Stated plainly, because an incomplete instrument that implies completeness is
the thing this repo is trying to stop doing.

- **Per-scene granularity.** `image_generation` is one number for all scenes and
  `prompt_construction` is the whole loop. Per-image timing is exactly where a
  real Imagen run's variance lives, and it is not captured.
- **Retries.** `utils/retry.py` retries inside a stage, so a stage that retried
  three times is one timing with no attempt count. Episode-level `attempts` in
  the `episodes` table is a different, coarser counter.
- **Rate limiting.** No accounting for 429s or backoff waits; they are absorbed
  into whatever stage was running.
- **Cache hits.** `core/content_cache.py` is not instrumented — and has no
  production call sites at all — so a cached run and an uncached one are
  indistinguishable in the report.
- **Cross-run p50/p95.** There is no aggregation over `run_telemetry`: no
  rollup query, no CLI surface, no view. Rows accumulate but nothing reads them
  back except `get_run_telemetry(job_id)`, one job at a time. "Has stage 5 got
  slower this month?" is answerable only with hand-written SQL.
- **Memory, CPU, bytes over the wire, output size.** Not sampled.
  `record_quality_metrics` receives a measured `processing_time_ms` but explicit
  `None` for `memory_usage_mb` and `output_quality_score`, so a consumer can
  tell "not measured" from "measured zero".
- **The quality agents.** `agents/quality_agents/` runs post-hoc validation that
  no stage timer covers.
