"""
The ``WorkflowOrchestrator`` construction seam.

Before injection existed, ``WorkflowOrchestrator()`` built eleven collaborators,
a ``DatabaseManager`` at a hardcoded path and a Gemini client, all inside
``__init__``. It could not be instantiated without a filesystem, a network and
an API key, and ``main.py`` - which already owned a database and six agents -
got a second copy of every one of them by calling it with no arguments.

These tests pin down both halves of the fix:

* every collaborator can be supplied, so the orchestrator builds from fakes
  alone with sockets disabled and no provider client ever constructed;
* every collaborator may still be omitted, so the no-argument call that the
  demo, the eval harness and the e2e suite rely on behaves exactly as before.
"""

import socket
from typing import Any
from unittest.mock import patch

import pytest

from agents.config_manager import EpisodeConfigManager
from agents.discovery_agent import EpisodeDiscoveryAgent
from agents.quality_agent import QualityAssuranceAgent
from agents.transcript_agent import TranscriptDiscoveryAgent
from agents.video_agent import VideoGenerationAgent
from agents.workflow_orchestrator import WorkflowOrchestrator
from core.adaptive_quality_manager import AdaptiveQualityManager
from core.database import DatabaseManager
from core.intelligent_format_adapter import IntelligentFormatAdapter
from core.protocols import CharacterAnalyzer, ChatModel, StructuredOutputModel
from core.visual_coherence_manager import VisualCoherenceManager


class FakeCharacterAnalyzer:
    """A ``CharacterAnalyzer`` that answers from memory instead of ChromaDB."""

    def __init__(self, profiles: dict[str, Any] | None = None):
        self.profiles = profiles or {}
        self.calls: list[tuple] = []

    def analyze_episode_characters(
        self, show_name: str, season: Any, episode: Any, transcript: str
    ) -> dict[str, Any]:
        self.calls.append((show_name, season, episode, transcript))
        return self.profiles


class Unbuildable:
    """Stands in for a collaborator class that must never be constructed."""

    def __init__(self, name: str):
        self.name = name

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError(f"{self.name} was constructed even though a collaborator was injected")


@pytest.fixture
def no_sockets(monkeypatch):
    """Make any attempt at network I/O an immediate, loud failure."""

    def explode(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "socket", explode)
    monkeypatch.setattr(socket, "create_connection", explode)


@pytest.fixture
def fully_injected(database_manager, fake_chat_model, no_sockets, monkeypatch):
    """
    A ``WorkflowOrchestrator`` assembled entirely from stand-ins.

    Sockets are disabled and every class the orchestrator would otherwise
    construct for itself is replaced with one that raises on call, so a passing
    test proves the injected objects were used rather than merely accepted.
    """
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    for attribute in (
        "init_chat_model",
        "DatabaseManager",
        "CharacterAnalysisAgent",
        "ContentAgent",
        "VideoGenerationAgent",
        "QualityAssuranceAgent",
        "EpisodeDiscoveryAgent",
        "TranscriptDiscoveryAgent",
        "EpisodeConfigManager",
    ):
        monkeypatch.setattr("agents.workflow_orchestrator." + attribute, Unbuildable(attribute))

    character_analyzer = FakeCharacterAnalyzer({"Naruto": {"importance_score": 0.9}})
    collaborators = {
        "db": database_manager,
        "model": fake_chat_model,
        "content_agent": object(),
        "video_agent": object(),
        "qa_agent": object(),
        "discovery_agent": object(),
        "transcript_agent": object(),
        "config_manager": object(),
        "character_analysis_agent": character_analyzer,
        "character_enhancer": object(),
        "visual_coherence": object(),
        "quality_manager": object(),
        "format_adapter": object(),
    }
    return WorkflowOrchestrator(**collaborators), collaborators


def test_builds_from_fakes_with_no_network_api_key_or_self_construction(fully_injected):
    """
    The whole point of the seam: a fully injected orchestrator needs nothing real.

    Sockets raise, the API-key variables are unset and every collaborator class
    in the module raises if called, so reaching the end of ``__init__`` at all
    is the assertion. The identity checks below confirm the objects handed in
    are the ones actually held.
    """
    orchestrator, collaborators = fully_injected

    assert orchestrator.db is collaborators["db"]
    assert orchestrator.model is collaborators["model"]
    assert orchestrator.content_agent is collaborators["content_agent"]
    assert orchestrator.video_agent is collaborators["video_agent"]
    assert orchestrator.qa_agent is collaborators["qa_agent"]
    assert orchestrator.discovery_agent is collaborators["discovery_agent"]
    assert orchestrator.transcript_agent is collaborators["transcript_agent"]
    assert orchestrator.config_manager is collaborators["config_manager"]
    assert orchestrator.character_analysis_agent is collaborators["character_analysis_agent"]
    assert orchestrator.character_enhancer is collaborators["character_enhancer"]
    assert orchestrator.visual_coherence is collaborators["visual_coherence"]
    assert orchestrator.quality_manager is collaborators["quality_manager"]
    assert orchestrator.format_adapter is collaborators["format_adapter"]


def test_structured_output_is_taken_from_the_injected_model(fully_injected):
    """The structured-output model is derived from the injected chat model."""
    orchestrator, collaborators = fully_injected

    assert orchestrator.model_with_structure is collaborators["model"].structured_model
    assert orchestrator.model_with_structure is not None


def test_injected_model_drives_real_summarisation(fully_injected, sample_episode_summary):
    """
    The seam is functional, not decorative.

    ``generate_structured_summary`` is production code: it builds the real
    prompt template and invokes the model. With a fake model injected it runs
    end to end with no provider package involved.
    """
    orchestrator, collaborators = fully_injected

    summary = orchestrator.generate_structured_summary(
        {"transcript": "Naruto: Shadow Clone Jutsu!", "analysis": "action heavy"},
        "Naruto",
    )

    assert summary == sample_episode_summary.model_dump()
    prompt_text = str(collaborators["model"].structured_model.prompts[0])
    assert "Naruto" in prompt_text
    assert "Shadow Clone Jutsu" in prompt_text


def test_injecting_a_database_constructs_no_second_one(database_manager, fake_chat_model):
    """
    The duplication bug, pinned.

    ``main.py`` builds a ``DatabaseManager`` from settings and hands it over;
    if the orchestrator built its own as well, the process would run with two
    databases at two different paths. ``DatabaseManager`` raising here means
    only the injected one can survive.
    """
    with patch("agents.workflow_orchestrator.DatabaseManager", Unbuildable("DatabaseManager")):
        orchestrator = WorkflowOrchestrator(
            db=database_manager,
            model=fake_chat_model,
            character_analysis_agent=FakeCharacterAnalyzer(),
        )

    assert orchestrator.db is database_manager


def test_omitted_collaborators_are_still_built_as_before(temp_db_path, fake_chat_model):
    """
    Injection is additive: anything left out is constructed exactly as it was.

    ``scripts/demo.py``, ``evals/harness.py`` and the e2e suite all call
    ``WorkflowOrchestrator(db_path=...)`` and rely on getting the real agents,
    so this guards their contract.
    """
    with patch(
        "agents.workflow_orchestrator.CharacterAnalysisAgent",
        return_value=FakeCharacterAnalyzer(),
    ):
        orchestrator = WorkflowOrchestrator(db_path=temp_db_path, model=fake_chat_model)

    assert isinstance(orchestrator.db, DatabaseManager)
    assert isinstance(orchestrator.video_agent, VideoGenerationAgent)
    assert isinstance(orchestrator.qa_agent, QualityAssuranceAgent)
    assert isinstance(orchestrator.discovery_agent, EpisodeDiscoveryAgent)
    assert isinstance(orchestrator.transcript_agent, TranscriptDiscoveryAgent)
    assert isinstance(orchestrator.config_manager, EpisodeConfigManager)
    assert isinstance(orchestrator.visual_coherence, VisualCoherenceManager)
    assert isinstance(orchestrator.quality_manager, AdaptiveQualityManager)
    assert isinstance(orchestrator.format_adapter, IntelligentFormatAdapter)
    assert orchestrator.character_enhancer.character_analyzer is (
        orchestrator.character_analysis_agent
    )


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_real_and_fake_character_analyzers_share_one_protocol():
    """Both implementations of the character seam satisfy ``CharacterAnalyzer``."""
    from agents.character_analysis_agent import CharacterAnalysisAgent

    assert issubclass(CharacterAnalysisAgent, CharacterAnalyzer)
    assert isinstance(FakeCharacterAnalyzer(), CharacterAnalyzer)


def test_fake_chat_model_satisfies_the_chat_model_protocol(fake_chat_model):
    """The stand-in used across tests, the demo and the evals is a ``ChatModel``."""
    assert isinstance(fake_chat_model, ChatModel)
    assert isinstance(fake_chat_model.with_structured_output(object), StructuredOutputModel)


def test_langchain_chat_models_satisfy_the_chat_model_protocol():
    """
    The production side of the same seam.

    ``BaseChatModel`` is checked as a class rather than an instance so that no
    provider client, credential lookup or network call is involved.
    """
    from langchain_core.language_models.chat_models import BaseChatModel

    assert issubclass(BaseChatModel, ChatModel)
