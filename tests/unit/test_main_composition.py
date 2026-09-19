"""
``main.py`` composes the process's dependencies exactly once.

``AnimeVideoGenerator.__init__`` used to build a ``DatabaseManager`` from
settings and six agents, and then call ``WorkflowOrchestrator()`` with no
arguments - which built a *second* ``DatabaseManager`` at its own hardcoded
``data/databases/video_generator.db`` plus duplicate copies of those six
agents and a second chat client. One process, two databases, two agent sets:
writes made through one were invisible to the other.

This test builds the real ``AnimeVideoGenerator`` against a throwaway settings
object, with only the three boundaries that need a key, a vector store or a
network replaced, and asserts every shared collaborator is one object.
"""

from typing import Any
from unittest.mock import patch

import pytest

from config.settings import get_settings


class FakeVectorSearchManager:
    """Stand-in for the optional vector search backend."""


class FakeCharacterAgent:
    """Stand-in for the ChromaDB-backed character analysis agent."""

    def analyze_episode_characters(
        self, show_name: str, season: Any, episode: Any, transcript: str
    ) -> dict[str, Any]:
        return {}


@pytest.fixture
def generator(tmp_path, fake_chat_model):
    """A real ``AnimeVideoGenerator`` confined to ``tmp_path``."""
    import main

    settings = get_settings().model_copy(
        update={
            "database_path": str(tmp_path / "video_generator.db"),
            "output_directory": str(tmp_path / "output"),
        }
    )
    character_agent = FakeCharacterAgent()

    with (
        patch("main.get_settings", return_value=settings),
        patch("langchain.chat_models.init_chat_model", return_value=fake_chat_model),
        patch("main.CharacterAnalysisAgent", return_value=character_agent),
        patch("main.VectorSearchManager", return_value=FakeVectorSearchManager()),
    ):
        instance = main.AnimeVideoGenerator()

    instance.test_character_agent = character_agent
    return instance


def test_one_database_per_process(generator, tmp_path):
    """The orchestrator shares the application's database instead of opening its own."""
    assert generator.orchestrator.db is generator.db
    assert generator.db.db_path == str(tmp_path / "video_generator.db")


def test_one_set_of_agents_per_process(generator):
    """Each agent the application owns is the same object the orchestrator uses."""
    assert generator.orchestrator.transcript_agent is generator.transcript_agent
    assert generator.orchestrator.content_agent is generator.content_agent
    assert generator.orchestrator.video_agent is generator.video_agent
    assert generator.orchestrator.qa_agent is generator.quality_agent
    assert generator.orchestrator.discovery_agent is generator.discovery_agent
    assert generator.orchestrator.config_manager is generator.config_manager
    assert generator.orchestrator.character_analysis_agent is generator.test_character_agent


def test_one_chat_model_per_process(generator, fake_chat_model):
    """Only the injected chat model is used; no second client is initialised."""
    assert generator.model is fake_chat_model
    assert generator.orchestrator.model is fake_chat_model
    assert generator.orchestrator.model_with_structure is fake_chat_model.structured_model
