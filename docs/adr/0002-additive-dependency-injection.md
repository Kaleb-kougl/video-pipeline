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

## Update — 2026-09-21 (`59fd32d`, `3005fc4`)

A second note rather than an edit to the first, on the precedent the first note
set. That note is a dated record of `f2597bf` and cites that commit as its
primary source; its closing paragraph is now wrong, and rewriting it in place
would leave a section headed by one commit describing a tree produced by
another — the same objection it raises against editing the Decision. Two running
counts above are wrong as written for the same reason ("fourteen today" in
Consequences, "the fourteen keyword-only ones" in the first update). They are
corrected here, not edited, exactly as the protocol count was.

**The debt the first update recorded is paid.** `create_images` now takes an
optional `image_generator` and forwards it to every `create_image`, so the one
function every production caller goes through no longer routes around the seam.
`WorkflowOrchestrator` takes `image_generator` as a keyword-only collaborator
like the rest, and `main.py` builds one per process and hands it to both the
orchestrator and the season-summary path. **An Imagen client is now constructed
once per run rather than once per frame**: a twelve-scene episode used to build
twelve identical clients, and no caller could substitute any of them.

**The constructor is fifteen keyword-only parameters, not fourteen.** Thirteen
at `e49717c`, fourteen with `telemetry` (`c262fff`), fifteen with
`image_generator` (`59fd32d`). The accepted cost "additive injection grows the
signature by one per collaborator, forever" is being paid on schedule, and a
grouped config object is still not worth the churn. **Ten are still typed
`Any`** — `image_generator` is `ImageFileGenerator`, so it is the fourth
parameter with a protocol behind it rather than an eleventh `Any`.

**The accepted cost "the media-render seam is still patched, not injected" is
now true of two functions, not three.** `wave_file` and `mp4_file_enhanced`
remain module-level calls that the tests and the demo monkeypatch; audio and
encode are what is left of that seam. `create_images` has left it, and the
distinction that matters is not that a parameter exists — it existed at
`f2597bf` too — but that production supplies it. The wiring test asserts that by
recording calls to `build_image_generator` and failing if any happened, because
`create_image` catches broadly and a bare assertion would have been swallowed
into a placeholder.

**The additive rule held, with one deliberate extension.** `image_generator`
defaults to `None` and the fallback tests `is not None`, so
`WorkflowOrchestrator()` and the four-argument `create_images(...)` still mean
what they always meant. But `media.media_utils.resolve_image_generator` never
raises: with no key, or no client library, it returns an
`UnavailableImageGenerator` carrying the reason, which re-raises at the point
`create_image` already handles it. A run therefore always holds an object, and
`None` keeps one meaning at a call site — "nobody wired a generator", a defect —
instead of also meaning "the wiring ran and there is none", which is an ordinary
offline Tuesday. The four `_report_image_fallback` branches and their printed
messages are byte-identical either way.

**Construction moved to the point of use at the other client too (`3005fc4`).**
`VideoGenerationAgent` built a Gemini client in its constructor; it now calls
`VideoGenerationAgent.build_client`, which raises `GeminiClientUnavailable`
naming the package and the install command. That is the shape
`build_image_generator` already had, and it is what let the module-scope
`from google import genai` become a guarded import — until then the orchestrator
imported that agent, so importing the orchestrator hard-required google-genai
even though nothing on the path used it. No protocol was added, and the ADR's
bar is why: nothing reads `self.client`, so there is no second implementation to
substitute and nothing to type against.
