# Generation evals

The deterministic test suite covers the plumbing. It cannot tell you whether a
prompt edit made the *output* worse, because the output is produced by a model
and the tests replace the model with a fixture that returns a fixed answer.

This is the harness for the other question: **did the generation get worse?**

```bash
python evals/run_eval.py                       # offline, gated - this is what CI runs
python evals/run_eval.py --mode live           # real Gemini, needs GOOGLE_API_KEY
python evals/run_eval.py --mode live --record  # ...and overwrite the committed fixtures
python evals/run_eval.py --mode live --judge   # ...and collect the advisory judge score
python evals/run_eval.py --update-baseline     # re-commit the numbers (review the diff)
```

Everything under evaluation is the summarisation stage:
`WorkflowOrchestrator.generate_structured_summary`, which turns a transcript
into an `Episode_Summary_Schema` (`show`, `season`, `episode`,
`youtube_transcript`, `plot_points`). That is the one place in the pipeline
where quality is decided by a model rather than by code.

## The two modes, and why the distinction matters

| | offline (default) | live |
|---|---|---|
| Model | recorded fixtures replayed through `ReplayModel` | real Gemini via `init_chat_model` |
| Needs a key | no | `GOOGLE_API_KEY` |
| Network | blocked by a socket guard, not by convention | yes |
| Deterministic | yes | no |
| Gates CI | yes | no |
| Answers "did my prompt change hurt?" | **no** | yes |

Both modes call the same production method, so the prompt template, the
show-name interpolation and the structured-output contract are exercised
identically. Only the model behind them differs. The banner at the top of the
scorecard says which mode produced the numbers.

**Offline mode cannot detect a bad prompt edit on its own.** The fixtures are
recordings; they do not react to a prompt change. Anyone who claims otherwise is
selling a tautology. What offline mode actually buys:

1. It locks the rubric and the golden set, so the *scorer* cannot drift
   unnoticed while everyone assumes the numbers mean the same thing.
2. It runs the prompt-contract check (below), which does catch a class of prompt
   regression with no key and no network.
3. It is the replay half of a record/replay loop. The intended workflow for a
   prompt change is: edit the prompt → `--mode live --record` → inspect the
   scorecard → commit the new fixtures and baseline. The regression shows up as
   a reviewable diff in `evals/baseline.json` instead of as a feeling.

## What is measured

Seven deterministic metrics, each in `[0, 1]`, combined into a weighted mean per
case. An LLM judge exists but is never part of the gated number - see below.

| Metric | Weight | What it computes | Why |
|---|---|---|---|
| `schema_validity` | 0.20 | Output satisfies `Episode_Summary_Schema`, and `show`/`season`/`episode` match the case | A structured-output failure breaks the pipeline downstream, not just the text. Split into four parts so "right shape, wrong episode number" is visible as 0.75 rather than collapsing into the same 0.0 as a parse failure. |
| `output_present` | 0.10 | Script has ≥20 words, ≥1 plot point, no refusal boilerplate | Refusal/empty-output rate. A refusal may be the honest answer, but it is still an episode the pipeline cannot render, so it has to show up in the number. |
| `plot_point_grounding` | 0.30 | Per plot point: 1.0 if it names an entity extracted from the transcript, 0.0 if it names something that appears *nowhere* in the source, 0.5 if it names nothing either way | The closest deterministic proxy for hallucination that needs no second model. Highest weight because it is the only metric that measures truth rather than form. |
| `entity_coverage` | 0.10 | Of the 5 most frequent transcript entities, how many appear anywhere in the output | Grounding alone is satisfiable by naming one character and ignoring the rest - the ensemble-episode failure mode. This is the recall half. |
| `length_adherence` | 0.10 | Script word count vs `target_minutes × 150`, full marks within ±35%, zero at half or double | 150 WPM is the pipeline's own assumption, not an invented one: `media/media_utils.py::create_silent_audio_fallback` estimates runtime as `word_count / 2.5`. The metric therefore tracks what the renderer will actually do with the script. |
| `cta_compliance` | 0.10 | Are *like*, *comment* and *subscribe* all present | The prompt literally says "Make sure to ask watchers to Like, Comment, and subscribe somewhere in the video." |
| `no_intro_compliance` | 0.10 | Does the opening ~200 characters contain channel-intro boilerplate | The prompt literally says "Do not do an introduction." |

The last two are the cheapest high-signal evals available for a generation
system: **checking whether the model obeyed an instruction its own prompt
issued** is unambiguous, needs no reference output, and regresses loudly.

### Entity extraction

Deterministic, no NER model, no network: speaker labels (`NAME:` at line start)
plus title-cased tokens that are not sentence-initial, minus a short stopword
list, with possessives normalised. Full-caps tokens are ignored in the second
pass because in these transcripts they are shouting and scene headers, which the
speaker pass already covers.

### The hallucination cap

Six of the seven metrics score *form*. Without a correction, a fluent, entirely
invented summary scores about 0.70 - which would be an eval that rewards
confident nonsense. So a case score is capped at `1 − (fraction of plot points
naming entities absent from the source)`, floored at 0.25. That is the whole
rule, and it is why `near_empty` baselines at 0.25.

### The prompt contract

Before scoring, the harness renders the real prompt through the production code
path and asserts it still contains the instructions the rubric grades obedience
to. Delete `Do not do an introduction` from
`agents/workflow_orchestrator.py` and the **offline** run fails, because the
harness is now scoring obedience to an instruction nobody is issuing. This is
the part of offline mode that is not a tautology. Verified by simulation:
stripping that line makes the offline run exit 1 with
`prompt contract broken`.

### The LLM judge

Available with `--mode live --judge`. Reported per case, weight 0.00, never
gated. A judge shares the failure modes of the system under test - same model
family, same prompt sensitivity, same silent drift across model versions - so
gating a build on it means a green CI depends on a number nobody can reproduce.
It is there because it catches incoherence the deterministic rubric is blind to,
and for nothing else.

## The golden set

Five synthetic transcripts for fictional shows (`evals/cases/`). Nothing
scraped, nothing copyrighted. They are chosen to stress different failure modes,
not to be representative:

| Case | Stresses |
|---|---|
| `short_episode` | Baseline. Two speakers, one clean escalating plot line. Anything below ~0.95 here is a real regression. |
| `dialogue_heavy` | Thirty short exchanges, three speakers, plot implied rather than stated. Models summarise the mood and drop the names. |
| `near_empty` | A scrape that succeeded structurally and returned nothing usable. The interesting case. |
| `odd_formatting` | Timestamps, HTML entities, ALL-CAPS shouting, inconsistent speaker markers, lowercase dialogue. |
| `ensemble_arc` | Five named speakers plus a narrator. The minor characters get dropped first. |

## Current numbers

Offline mode, committed fixtures, as of the baseline in `evals/baseline.json`:

```
  PROMPT CONTRACT ......................... PASS

  short_episode    0.980   clean; misses one low-frequency title entity
  dialogue_heavy   0.800   capped by 1 invented name; CTA missing "like"/"comment"
  near_empty       0.250   hallucination cap - invents an entire cast
  odd_formatting   0.870   obeys the CTA instruction, disobeys the no-intro one
  ensemble_arc     0.960   drops Halden and Vesper from a five-hander

  cta_compliance        0.867
  entity_coverage       0.800
  length_adherence      0.968
  no_intro_compliance   0.800
  output_present        1.000
  plot_point_grounding  0.780
  schema_validity       1.000

  AGGREGATE             0.772   (gate: 0.750)
```

**These specific numbers are not yet evidence about the real model.** No
`GOOGLE_API_KEY` was available when the golden set was built, so the committed
fixtures are hand-authored stand-ins, written to be plausible outputs and to
exercise every branch of the rubric. Each one says so in its `_provenance`
field. The first `--mode live --record` run replaces them with genuine captures
and the baseline moves; that commit is where the numbers start meaning
something. Everything else - the metrics, the gate, the golden set, the
contract check - is real today.

## The CI gate

`evals/run_eval.py` exits non-zero when any of these hold:

1. The aggregate drops below `gate.min_aggregate_score` (0.750, about 0.02 under
   the current aggregate - tight enough to catch a regression, loose enough that
   rounding does not fail a build).
2. Any single case regresses by more than `gate.max_case_regression` (0.05). The
   aggregate alone would let one case collapse while the others absorb it.
3. The prompt contract breaks.

All three paths were verified by forcing them, not by inspection:

| Forced failure | Result |
|---|---|
| Fixture edited to open with an intro and drop the CTA | `short_episode` 0.980 → 0.780, exit 1 |
| Fixture edited to omit `plot_points` (schema violation) | `ensemble_arc` 0.960 → 0.000, exit 1, error reported per case |
| `Do not do an introduction` stripped from the rendered prompt | prompt contract FAIL, exit 1 |

A human-readable scorecard goes to stdout; the machine-readable one goes to
`evals/results/scorecard.json` (gitignored) for diffing between runs. `--no-gate`
reports without failing.

## What this eval does NOT capture

Being specific about this matters more than the numbers above.

- **Offline mode does not evaluate the prompt.** Stated three times in this
  document because it is the single easiest thing to misread about the harness.
  Only `--mode live` answers that question.
- **The committed fixtures are stand-ins, not recordings** (see above). Until a
  live record run lands, the baseline measures the rubric, not the model.
- **Grounding is entity overlap, not entailment.** "Mira trusts Osgood" and
  "Mira betrays Osgood" score identically. Every plot point could be factually
  inverted and the grounding metric would not notice. That is the largest blind
  spot in the rubric and the strongest argument for the live judge existing at
  all.
- **Nothing downstream of the summary is scored.** Image prompts, TTS, scene
  timing, the encode - all unmeasured here. The offline demo (`make demo`)
  covers that the pipeline *runs*; nothing covers whether the video is good.
- **Length adherence measures an unconstrained variable.** The episode prompt
  never tells the model a target length; `target_minutes` lives only in the
  season-summary path. The metric is measuring something nobody asked the model
  for. It is weighted at 0.10 for that reason, and the finding itself - *the
  prompt has no length instruction* - is arguably worth more than the score.
- **Five cases is a smoke test, not a distribution.** They were written to hit
  specific failure modes, so the aggregate is not an estimate of real-world
  quality and should never be quoted as one. It is a tripwire.
- **No variance measurement.** Live mode runs each case once at default
  temperature. A change inside run-to-run noise is indistinguishable from no
  change. Doing this properly means n≥5 samples per case and comparing
  distributions; the harness does not do that yet.
- **No cost, latency or token accounting.** A prompt change that doubles spend
  for +0.01 looks like a straight win here.
- **The rubric is gameable, deliberately.** A model that name-drops every
  character and ends with "like, comment, subscribe" scores well without
  understanding the episode. These metrics are a floor - they catch things
  getting *broken*. They do not certify that things are *good*.
- **Non-English or heavily stylised transcripts are untested.** Entity
  extraction assumes Latin script and English capitalisation conventions.
