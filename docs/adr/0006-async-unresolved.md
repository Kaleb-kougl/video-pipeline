# ADR 0006 — What to do about `async` (unresolved)

**Status:** **Proposed / open.** No decision has been made. · **Date:** 2026-09-19

This ADR exists to stop the question being re-litigated from scratch each time
someone notices it, and to record that the current state is an accident rather
than a choice.

## Context

`agents/` and `core/` contain **27 `async def`s** spread over five modules —
`workflow_orchestrator.py` (4), `intelligent_format_adapter.py` (9),
`visual_coherence_manager.py` (9), `character_episode_enhancer.py` (4),
`adaptive_quality_manager.py` (1).

They coexist with blocking I/O in the request paths: `requests.get` in
`discovery_agent.py` and `transcript_source_agent.py`, and `time.sleep` in
`discovery_agent.py`, `transcript_agent.py` and `transcript_source_agent.py`.

So the async is not buying concurrency. Nothing runs concurrently: the coroutines
are awaited one after another, and the calls that would actually benefit — HTTP
fetches during discovery — are synchronous and sleep the whole loop when they
back off. What the `async` keywords currently buy is an `asyncio.run` at every
entry point, `pytest-asyncio` in the test suite, and a colour distinction that
callers have to respect without getting anything for it.

This is a batch CLI. It processes one episode, or a season sequentially. There is
no server, no request fan-in, no latency budget that concurrency would serve.

## Options

1. **Drop async.** Convert the 27 coroutines to plain functions, delete
   `asyncio.run` from the entry points and `pytest-asyncio` from the suite.
   Mechanical, large, touches every entry point, and reduces the codebase to what
   it actually does.
2. **Complete async.** Replace `requests` with `httpx.AsyncClient`, `time.sleep`
   with `asyncio.sleep`, and add real concurrency where it pays — parallel
   episode probing during season discovery, parallel image generation. Larger,
   and re-opens the concurrency story that `7116567` deliberately closed by
   deleting `ParallelImageGenerator` (see [ADR 0004](0004-delete-rather-than-repair.md)).
3. **Leave it.** Zero cost today, and the inconsistency keeps costing a little
   attention forever.

## Current recommendation (not a decision)

**Option 1 — drop async.** It matches what the program does, and option 2's
payoff is speculative until someone is actually waiting on a season batch. If
season-level throughput ever becomes a real complaint, async can be reintroduced
deliberately, at the one seam that needs it, with a benchmark justifying it.

The argument against: dropping it is a large diff with no user-visible benefit,
and if concurrency is coming anyway it is wasted motion in both directions.

## Why this is still open

Nobody has measured how long a season batch actually takes, so the case for
option 2 cannot be priced. [ADR 0005](0005-measure-never-estimate.md) shipped the
instrument that would price it; the measurement has not been taken. **This
decision should be made after a season run is measured, not before.**
