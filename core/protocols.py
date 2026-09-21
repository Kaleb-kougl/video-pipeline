"""
Structural types for the collaborators the pipeline injects.

Each protocol below names a boundary that already has **two or more real
implementations** in this repository - the production object and at least one
stand-in that the test suite, the offline demo or the eval harness substitutes
for it. Writing the shape down turns an undocumented duck-typing convention
into something a type checker and a test can both check.

Boundaries that currently have exactly one implementation are deliberately
*not* given a protocol here, because a protocol with a single implementor is
ceremony rather than design:

* ``core.database.DatabaseManager`` - the tests use the real class against a
  throwaway SQLite file in ``tmp_path``; there is no second implementation, so
  it is injected as itself (see ``WorkflowOrchestrator(db=...)``).
* ``generate_image(prompt) -> dict`` (``core.content_cache``) - see the note
  below; it is a cache-payload callback rather than an image generator, and
  still has exactly one (stub) implementation.

Image generation: three descriptions, one seam
----------------------------------------------

Three places in this repository used to describe "the image generator", and no
two of them agreed:

1. ``core.visual_coherence_manager.ImageGenerator`` - a *callable* taking an
   enhanced prompt and returning the path of a file the callable chose.
2. ``core.content_cache.get_or_generate_image`` - an object with
   ``generate_image(prompt) -> dict``, the dict being cached as the content.
3. ``tests.conftest.FakeImageGenerator`` - the only implementation of (2),
   returning ``{"url": ...}``.

Only one of those is an image generator. (2) never renders anything: it asks
for a JSON-serialisable payload to put in an LRU cache, and would be satisfied
by a dict literal. It is a **cache-payload callback**, it is duck-typed
against a runtime ``TypeError``, its signature is pinned by
``docs/CONTENT_CACHING_GUIDE.md``, and it still has one stub implementation, so
it stays out of this module - renamed in ``tests/conftest.py`` to say what it
is.

(1) *is* the seam, seen from a consumer that does not care where the file
lands: ``VisualCoherenceManager`` only needs a path it can hand to OpenCV. But
the pipeline's actual renderer does care. ``media.media_utils.create_image``
computes a deterministic path - ``{show}/Season{season}/Episode{episode}/
{show}_{episode}_{index}.png`` - and ``mp4_file_enhanced`` later reopens that
exact string. A generator that picks its own path would force the renderer to
move the file afterwards, which is the one thing it must not get wrong.

So the settled shape below takes the destination as an argument and returns the
path it wrote. Notably it is *not* ``-> bytes``: the only consumer of bytes
would be a ``write_bytes`` call in ``create_image``, and the Imagen client hands
back an object whose documented operation is ``image.save(path)``. Returning
bytes would mean reaching past that API into ``image.image_bytes`` and pushing a
megabyte of PNG through memory to save a line. ``ImageFileGenerator`` is named
for the shape rather than reusing the bare name ``ImageGenerator``, which
``core.visual_coherence_manager`` already binds to the callable form; the
callable form is this protocol's method with the destination bound by the
caller, and ``tests.conftest.FakeImageGenerator`` satisfies both at once.
"""

from typing import Any, Protocol, runtime_checkable

__all__ = [
    "CharacterAnalyzer",
    "ChatModel",
    "ImageFileGenerator",
    "StructuredOutputModel",
]


@runtime_checkable
class StructuredOutputModel(Protocol):
    """
    What ``ChatModel.with_structured_output(schema)`` returns.

    Implementations: the LangChain runnable produced by a real chat model,
    ``tests.conftest.FakeStructuredModel``, ``scripts.demo.CannedStructuredModel``
    and the replay model in ``evals/harness.py``.
    """

    def invoke(self, prompt: Any) -> Any:
        """Run the prompt and return an object matching the requested schema."""
        ...


@runtime_checkable
class ChatModel(Protocol):
    """
    The slice of a LangChain chat model this pipeline actually uses.

    Implementations: the Gemini model returned by ``init_chat_model``,
    ``tests.conftest.FakeChatModel``, ``scripts.demo.CannedChatModel`` and
    ``evals.harness.ReplayModel``. Only ``invoke`` and
    ``with_structured_output`` are used anywhere in the pipeline, which is why
    a three-line stand-in has always been enough to replace Gemini.
    """

    def invoke(self, prompt: Any) -> Any:
        """Run the prompt and return the model's free-text response."""
        ...

    def with_structured_output(self, schema: Any) -> StructuredOutputModel:
        """Return a model constrained to answer with ``schema``."""
        ...


@runtime_checkable
class CharacterAnalyzer(Protocol):
    """
    Supplies per-episode character profiles.

    Implementations: ``agents.character_analysis_agent.CharacterAnalysisAgent``
    (ChromaDB plus a downloaded sentence-transformers model),
    ``tests.e2e.test_episode_pipeline.FakeCharacterAnalysisAgent`` and
    ``scripts.demo.CannedCharacterAnalysisAgent``.

    ``season`` and ``episode`` are typed ``Any`` on purpose: the real agent
    annotates them ``int``, while ``WorkflowOrchestrator`` passes the ``str``
    values that come back from the summary schema. That inconsistency predates
    this protocol and is left alone rather than silently papered over.
    """

    def analyze_episode_characters(
        self, show_name: str, season: Any, episode: Any, transcript: str
    ) -> dict[str, Any]:
        """Return a mapping of character name to that character's profile."""
        ...


@runtime_checkable
class ImageFileGenerator(Protocol):
    """
    Renders a prompt into an image file at a path the caller chooses.

    Implementations: ``media.media_utils.ImagenImageGenerator`` (Google Imagen
    through ``google-genai``) and ``tests.conftest.FakeImageGenerator``, which
    writes a real PNG with PIL and never opens a socket.

    The caller owns the path because the pipeline's filenames are load-bearing:
    ``media.media_utils.create_image`` writes
    ``{show}/Season{season}/Episode{episode}/{show}_{episode}_{index}.png`` and
    ``mp4_file_enhanced`` reopens that same string when it assembles the video.

    Failure is an exception, not a sentinel. A generator that cannot be
    *constructed* - no API key, no client library, an unusable credential -
    raises ``media.media_utils.ImageGeneratorUnavailable`` from its factory, and
    ``create_image`` degrades to a placeholder title card with the reason
    logged. That is the same discipline ``b6fde06`` applied to
    ``CharacterAnalysisAgent``: an optional path has to be optional for every
    reason it can fail, not just the one that was thought of first.
    """

    def generate_image(self, prompt: str, destination: str) -> str:
        """
        Render ``prompt`` into an image file at ``destination``.

        Args:
            prompt: The fully enhanced prompt to render.
            destination: Filesystem path the image must be written to. The
                parent directory already exists.

        Returns:
            The path actually written, which must be ``destination``.

        Raises:
            Exception: Any failure to produce the file. Callers that have a
                fallback are expected to catch broadly and degrade.
        """
        ...
