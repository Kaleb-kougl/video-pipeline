#!/usr/bin/env python3
"""
Regression tests for ChromaDB array boolean evaluation.

ChromaDB returns ``embeddings`` as a numpy array. Code that wrote
``if results["embeddings"]:`` therefore raised
``ValueError: The truth value of an array with more than one element is
ambiguous``. Every consumer below was changed to guard with an explicit
``is None`` / ``len(...) == 0`` check instead, and these tests keep it that way.

This module used to be a single ``test_chromadb_array_fixes()`` that wrapped six
checks in ``try/except``, printed a tick or a cross, and *returned* a bool.
pytest ignores a return value, so the module reported as one passing test while
four of its six checks were failing - and three of those four called methods
that have never existed in this repository:

* ``VectorSearchManager.semantic_search`` - the method is ``search_episodes``.
* ``MetadataQualityAgent.check_metadata_quality`` - the method is
  ``validate_metadata_consistency``.
* ``scripts.migrate_metadata.interactions_collection`` - the module builds its
  client and collection inside the function; there is no module-level
  collection to patch.

Each check is now its own ``test_`` function with real assertions. The checks
also assert that the call produced data: every function under test swallows its
own exceptions and returns an empty result, so "it did not raise" is not on its
own evidence that the array guards held.
"""

import sys
import unittest.mock as mock
from pathlib import Path

import numpy as np
import pytest

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# An embedding matrix exactly as ChromaDB hands it back: a numpy array, which is
# what made `if results["embeddings"]:` raise.
NUMPY_EMBEDDINGS = np.array([[0.1, 0.2, 0.3]])


@pytest.fixture
def character_query_results():
    """A ``collection.query()`` payload for character profiles.

    ``query()`` nests one list per query text, and the metadata carries every
    key ``_get_season_episodes`` reads - a partial profile would raise a
    ``KeyError`` that the method's own ``except`` would hide.
    """
    return {
        "metadatas": [
            [
                {
                    "character_name": "Izuku",
                    "show_name": "My Hero Academia",
                    "season": 1,
                    "episode": 1,
                    "dialogue_count": 15,
                    "personality_traits": '["determined", "brave"]',
                },
                {
                    "character_name": "Bakugo",
                    "show_name": "My Hero Academia",
                    "season": 1,
                    "episode": 2,
                    "dialogue_count": 8,
                    "personality_traits": '["hot-tempered"]',
                },
            ]
        ],
        "documents": [["Izuku profile", "Bakugo profile"]],
        "embeddings": [np.array([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])],
    }


@pytest.fixture
def interaction_query_results():
    """A ``collection.query()`` payload for character interactions."""
    return {
        "metadatas": [
            [
                {
                    "episode_key": "My Hero Academia_S1E1",
                    "characters": '["Izuku", "Bakugo"]',
                    "interaction_type": "rivalry",
                    "emotional_tone": "tense",
                    "significance_score": 0.8,
                }
            ]
        ],
        "documents": [["Izuku and Bakugo argue"]],
        "embeddings": [NUMPY_EMBEDDINGS],
    }


@pytest.fixture
def empty_query_results():
    """What ChromaDB returns for a query that matched nothing."""
    return {"metadatas": [], "documents": [], "embeddings": []}


@pytest.fixture
def character_agent(tmp_path):
    """Builds a ``CharacterAnalysisAgent`` that touches neither disk nor network.

    The real constructor does two things none of the checks below are about: it
    ``mkdir``s ``data/databases/character_db`` (gitignored, so it exists only on
    a machine that has already run the pipeline) and it downloads the
    ``all-MiniLM-L6-v2`` sentence-transformers model. Both are pinned out here -
    the persist directory to pytest's ``tmp_path``, ChromaDB and the encoder to
    mocks - so these tests exercise the array guards and nothing else, and pass
    on a clean checkout with no network.
    """

    def _make(characters_payload, interactions_payload):
        from agents.character_analysis_agent import CharacterAnalysisAgent

        with (
            mock.patch("chromadb.PersistentClient"),
            mock.patch("agents.character_analysis_agent.SentenceTransformer"),
        ):
            agent = CharacterAnalysisAgent(persist_directory=str(tmp_path / "character_db"))

        characters_collection = mock.Mock()
        interactions_collection = mock.Mock()
        characters_collection.query.return_value = characters_payload
        interactions_collection.query.return_value = interactions_payload
        agent.characters_collection = characters_collection
        agent.interactions_collection = interactions_collection
        return agent

    return _make


def test_season_episodes_reads_numpy_embeddings(
    character_agent, character_query_results, interaction_query_results, caplog
):
    """``_get_season_episodes`` must survive numpy embeddings and return data."""
    agent = character_agent(character_query_results, interaction_query_results)

    season = agent._get_season_episodes("My Hero Academia", 1)

    assert "Failed to get season episodes" not in caplog.text, (
        "the method swallowed an exception instead of reading the results"
    )
    assert season["episodes"] == [1, 2]
    assert season["episode_data"][1]["characters"]["Izuku"]["dialogue_count"] == 15
    # The embedding actually came through rather than being guarded away.
    assert season["episode_data"][1]["characters"]["Izuku"]["embedding"] is not None
    assert season["episode_data"][1]["interactions"][0]["type"] == "rivalry"


def test_season_episodes_handles_none_results(character_agent):
    """A collection that returns ``None`` metadata must not raise."""
    none_results = {"metadatas": None, "documents": None, "embeddings": None}
    agent = character_agent(none_results, none_results)

    assert agent._get_season_episodes("My Hero Academia", 1) == {}


def test_season_episodes_handles_empty_nested_results(character_agent):
    """Empty nested lists are the "no match" shape, and must not raise either."""
    empty_nested = {"metadatas": [[]], "documents": [[]], "embeddings": [[]]}
    agent = character_agent(empty_nested, empty_nested)

    assert agent._get_season_episodes("My Hero Academia", 1) == {}


def test_vector_search_formats_results_alongside_numpy_embeddings(tmp_path, caplog):
    """``VectorSearchManager.search_episodes`` is the semantic-search entry point.

    The old harness called ``semantic_search``, which this class has never
    defined; the resulting ``AttributeError`` was printed and counted as a
    failure that nothing could see.
    """
    from utils.vector_search import VectorSearchManager

    with (
        mock.patch("chromadb.PersistentClient"),
        mock.patch("utils.vector_search.SentenceTransformer") as encoder_class,
    ):
        encoder_class.return_value = mock.Mock()
        manager = VectorSearchManager(persist_directory=str(tmp_path / "vector_db"))

    collection = mock.Mock()
    collection.query.return_value = {
        "documents": [["Izuku destroys the zero pointer to save Ochaco."]],
        "metadatas": [
            [
                {
                    "show_name": "My Hero Academia",
                    "season": 1,
                    "episode": 4,
                    "chunk_index": 0,
                }
            ]
        ],
        "distances": [[0.25]],
        "embeddings": [NUMPY_EMBEDDINGS],
    }
    manager.collection = collection

    results = manager.search_episodes("hero entrance exam", limit=5)

    assert "Search failed" not in caplog.text
    assert len(results) == 1
    assert results[0]["show_name"] == "My Hero Academia"
    assert results[0]["episode"] == 4
    assert results[0]["similarity_score"] == pytest.approx(0.75)


def test_metadata_quality_agent_counts_issues_alongside_numpy_embeddings(caplog):
    """``MetadataQualityAgent.validate_metadata_consistency`` is the quality check.

    The old harness called ``check_metadata_quality``, which has never existed.
    ``collection.get()`` returns flat lists (unlike ``query()``), so the payloads
    here are flat - the old harness fed it ``query()``-shaped data as well.
    """
    from agents.quality_agents.metadata_quality_agent import MetadataQualityAgent

    with mock.patch("chromadb.PersistentClient"):
        agent = MetadataQualityAgent()

    interactions = mock.Mock()
    characters = mock.Mock()
    interactions.get.return_value = {
        # One interaction has no show_name at all.
        "metadatas": [{"episode_key": "my_hero_academia_S1E1"}],
        "embeddings": NUMPY_EMBEDDINGS,
    }
    characters.get.return_value = {
        # One profile uses an alias rather than the canonical show name.
        "metadatas": [{"character_name": "Izuku", "show_name": "MHA"}],
        "embeddings": NUMPY_EMBEDDINGS,
    }
    agent.interactions_collection = interactions
    agent.characters_collection = characters

    report = agent.validate_metadata_consistency()

    assert "error" not in report, report.get("error")
    assert "Metadata validation failed" not in caplog.text
    assert report["missing_show_names"] == 1
    assert report["canonical_violations"] == 1
    assert report["total_issues"] == 2


def test_migration_reads_get_results_alongside_numpy_embeddings():
    """``migrate_interaction_metadata`` opens its own client and collection.

    The old harness patched ``scripts.migrate_metadata.interactions_collection``,
    a module attribute that does not exist, so the check could only ever fail.
    The collection is reached through ``chromadb.PersistentClient``, so that is
    what has to be patched.
    """
    from scripts.migrate_metadata import migrate_interaction_metadata

    collection = mock.Mock()
    collection.get.return_value = {
        "metadatas": [{"episode_key": "my_hero_academia_S1E4"}],
        "documents": ["Izuku and All Might"],
        "ids": ["interaction_1"],
        "embeddings": NUMPY_EMBEDDINGS,
    }

    with mock.patch("chromadb.PersistentClient") as client_class:
        client_class.return_value.get_collection.return_value = collection
        result = migrate_interaction_metadata()

    assert result == {"success": True, "migrated_count": 1}
    collection.update.assert_called_once()
    written = collection.update.call_args.kwargs["metadatas"][0]
    assert written["show_name"] == "My Hero Academia"
    assert written["show_id"] == "my_hero_academia"
    assert written["season"] == 1
    assert written["episode"] == 4


def test_migration_handles_an_empty_collection():
    """No interactions is a successful no-op, not an error."""
    from scripts.migrate_metadata import migrate_interaction_metadata

    collection = mock.Mock()
    collection.get.return_value = {"metadatas": [], "documents": [], "ids": []}

    with mock.patch("chromadb.PersistentClient") as client_class:
        client_class.return_value.get_collection.return_value = collection
        result = migrate_interaction_metadata()

    assert result == {"success": True, "migrated_count": 0}
    collection.update.assert_not_called()


if __name__ == "__main__":
    # `scripts/run_regression_suite.py` runs this module as a script. Delegating
    # to pytest keeps a direct run and a collected run executing the same checks
    # and reporting the same exit status.
    raise SystemExit(pytest.main([__file__, *sys.argv[1:]]))
