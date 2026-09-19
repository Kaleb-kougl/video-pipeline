# ADR 0001 — Score generation with a deterministic rubric, not an LLM judge

**Status:** Accepted · **Date:** 2026-09-18 · **Commits:** `37614a1`, `cb5c640`

## Context

This is a nondeterministic LLM pipeline. The unit suite covers plumbing: it
replaces the model with a fixture that returns a fixed answer, so it cannot tell
whether a prompt edit made the *output* worse. That is the one question worth
asking about generation, and nothing answered it.

The obvious answer — have a model grade the output — makes the gate itself
nondeterministic, costs an API call per case, and cannot run in CI without a key.

## Decision

`make eval` scores `WorkflowOrchestrator.generate_structured_summary` over a
five-case golden set of synthetic transcripts (short, dialogue-heavy, near-empty,
oddly formatted, ensemble) using **seven deterministic metrics**: schema
validity, output presence, plot-point grounding, entity coverage, length
adherence, and compliance with the two instructions the prompt itself issues.

Grading a model against its own stated requirements needs no reference output and
is unambiguous. An LLM judge exists behind `--judge` but is **advisory only** and
is not part of the gated score.

Two guards make the number mean something:

- **A hallucination cap.** Six of the seven metrics score *form*, so a fluent
  invention scored ~0.70. A case is now capped by the fraction of plot points
  naming entities absent from the source, so hallucination cannot be outvoted by
  good structure.
- **A prompt-contract check.** Offline mode replays fixtures, which risks
  becoming a tautology. The harness renders the real prompt through production
  code and asserts it still issues what the rubric grades. Drop an instruction
  from the prompt and the contract check fails, rather than the score silently
  becoming meaningless.

Gate: aggregate < 0.750, any case regressing > 0.05, or a broken prompt contract.
All three paths were forced and observed failing, not assumed.

`cb5c640` wired the gate into `make eval` and CI — it shipped in `37614a1` with
nothing invoking it — and made offline mean offline: `.env` set
`LANGSMITH_TRACING`, LangChain read it at import time, and the "offline" eval was
opening connections to a third party on every run.

## Consequences

Good: the gate is reproducible, free, needs no credential, and runs on every push.
A prompt change that regresses the score now fails the build.

**The cost we accepted, stated plainly:** grounding is measured by *entity
overlap*, not entailment. The rubric checks that the names in a plot point appear
somewhere in the source. It cannot distinguish

> "Mira trusts Osgood"  from  "Mira betrays Osgood"

Both name the same two entities, both are grounded, both score identically. A
summary that inverts every relationship in the episode can score 1.0 on
grounding. This is the single largest hole in the harness and it is not a
rounding error — it is the difference between "the summary is about the right
episode" and "the summary is true."

Also accepted:

- Six of seven metrics score form, so the aggregate is mostly a fluency-and-shape
  number with a hallucination ceiling bolted on.
- The committed fixtures are hand-authored stand-ins (no `GOOGLE_API_KEY` was
  available), labelled as such in each file's `_provenance`. They exercise every
  branch of the rubric but are not evidence about Gemini. The first
  `--mode live --record` re-baselines, and that is where the numbers start
  meaning something.
- Nothing downstream of the summary is measured, nor run-to-run variance.

## What I would do differently

Add a small entailment check — even a cheap NLI model, or an advisory judge
scoped *only* to relation polarity — and let it fail the build rather than sit
behind `--judge`. The purity of "no model in the gate" bought reproducibility at
the price of not checking correctness, and correctness is what the eval was for.
The right shape is probably a deterministic gate plus a separate, smaller,
model-scored check whose flakiness is bounded because it asks one narrow
question.

See [../evals.md](../evals.md).
