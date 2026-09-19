# ADR 0002 — Inject collaborators additively, with keyword-only `None` defaults

**Status:** Accepted · **Date:** 2026-09-18 · **Commit:** `e49717c`

## Context

`WorkflowOrchestrator.__init__` constructed eleven collaborators plus a
`DatabaseManager` and a Gemini model, so it could not be built without network,
credentials and a filesystem. `main.py` then built its *own* `DatabaseManager`
and called `WorkflowOrchestrator()` with no arguments, which built a **second**
one at a different hardcoded path along with duplicate copies of six agents —
two databases and two agent sets in one process.

## Decision

Injection is **additive**. Every collaborator became a keyword-only parameter
defaulting to `None`, falling back to exactly the construction it always did, and
the fallback tests `is not None` rather than truthiness so a legitimate falsy
double is not silently replaced.

No existing call site changed meaning, so every intermediate state was shippable —
the property that made this landable in one commit without a flag day. `main.py`
now builds its dependencies once and passes them in.

`core/protocols.py` defines **three** runtime-checkable Protocols, each justified
by implementations that exist today rather than by architecture: `ChatModel` and
`StructuredOutputModel` (LangChain's `BaseChatModel` against the fakes in
`tests/conftest.py`, the demo and `evals/harness.py`) and `CharacterAnalyzer`
(`CharacterAnalysisAgent` against the e2e and demo stand-ins).

The module docstring records what deliberately did **not** get a protocol and
why: `DatabaseManager` has one implementation; `content_cache`'s
`generate_image` has only a test fake and already raises a clear `TypeError`; the
visual-coherence render callable has no production implementation. Ceremony
avoided on purpose.

**No composition root was added.** `main.py` already is one. A container handing
back the same objects `AnimeVideoGenerator` uses directly would be a pass-through
layer.

## Consequences

Good: the orchestrator is constructible with no network, no API key and no
database — the central test unsets both key variables, makes `socket.socket` and
`create_connection` raise, replaces all nine collaborator classes with objects
that explode if called, and still constructs it. That was impossible before.
Another test pins one database, one agent set and one model per process.

Accepted costs:

- **Ten of the parameters are typed `Any`.** Only three collaborators earned a
  protocol, so the seam is real at runtime but mostly unchecked at type level.
  This was the deliberate trade: protocols justified by two implementations, not
  by symmetry.
- **The constructor is wide.** Thirteen keyword-only parameters at `e49717c`,
  fourteen today (`telemetry` arrived with `c262fff`). Additive injection grows
  the signature by one per collaborator, forever. A grouped config object would
  read better and was not worth the churn yet.
- **The media-render seam is still patched, not injected.** `create_images`,
  `wave_file` and `mp4_file_enhanced` remain module-level calls that tests
  monkeypatch. That is the last seam, and the one the demo depends on.
- Module-level `moviepy` imports mean "instantiable in a test" still requires
  import-level care.
