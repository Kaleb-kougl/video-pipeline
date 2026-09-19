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
* ``generate_image(prompt) -> dict`` (``core.content_cache``) - only the test
  fake implements it today; ``content_cache`` already checks for the method at
  runtime and raises a clear ``TypeError``.
* The image-rendering callable injected into
  ``core.visual_coherence_manager.VisualCoherenceManager`` - it already has a
  documented ``ImageGenerator`` alias next to the class that uses it, and no
  production implementation exists yet.
"""

from typing import Any, Protocol, runtime_checkable

__all__ = ["CharacterAnalyzer", "ChatModel", "StructuredOutputModel"]


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
