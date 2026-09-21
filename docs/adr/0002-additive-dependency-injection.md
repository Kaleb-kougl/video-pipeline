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

## Update — 2026-09-21 (`f2597bf`)

The Decision above is left exactly as written. It records what was true at
`e49717c`, and it points a reader at `git show e49717c` as the primary source;
editing the count to match today's code would make the record disagree with the
commit it cites, and would erase the fact that the bar was applied consistently
on two different days to two different answers. Amendment, not rewrite.

**`core/protocols.py` now defines four runtime-checkable Protocols, not three.**
`f2597bf` added `ImageFileGenerator` — `generate_image(prompt, destination) ->
str`. It cleared the same bar the original three cleared, and for the same
reason: it had two implementations the moment it landed
(`media.media_utils.ImagenImageGenerator` and `tests.conftest.FakeImageGenerator`),
rather than being justified by symmetry.

**One of the three "no protocol on purpose" cases was reclassified, not
reversed.** The Decision lists the visual-coherence render callable as having no
production implementation. That ceased to be true when `create_image` stopped
building a `genai.Client` inline and started taking an injectable generator, so
the case for exclusion expired and the protocol followed. The other two still
hold for the stated reasons: `DatabaseManager` has one implementation, and
`content_cache`'s `generate_image(prompt) -> dict` turned out not to be an image
generator at all but a cache-payload callback — it never renders anything — so
it stays duck-typed, and its fake was renamed `FakeImagePayloadSource` to stop
the two shapes being mistaken for one.

**The accepted cost "the media-render seam is still patched, not injected" is
partly paid down.** `create_image` now accepts an `image_generator`, and
`build_image_generator()` raises `ImageGeneratorUnavailable` rather than
returning a half-built client. But `create_images` does not forward a generator
to `create_image`, so no production caller injects one yet, and `create_images`,
`wave_file` and `mp4_file_enhanced` remain module-level calls that the tests and
the demo monkeypatch. The other accepted costs are untouched:
`ImageFileGenerator` is not a `WorkflowOrchestrator` parameter, so the ten
`Any`-typed parameters and the fourteen keyword-only ones are unchanged.
