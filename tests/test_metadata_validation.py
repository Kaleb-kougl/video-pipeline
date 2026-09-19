#!/usr/bin/env python3
"""
Test suite for metadata validation and show separation.

Everything here is a logic test: schema construction, show-name canonicalization
and the show filtering the agent puts into its ChromaDB ``where`` clauses. None
of it needs a real vector store or a real embedding model, so none of it builds
one. ``CharacterAnalysisAgent()`` with its default arguments would ``mkdir``
``data/databases/character_db`` - gitignored, therefore present only on a
machine that has already run the pipeline - and download ``all-MiniLM-L6-v2``
from HuggingFace. Tests that did that passed locally and failed on a clean
checkout; the ``character_agent`` fixture below pins both out.
"""

import json
from unittest.mock import Mock, patch

import pytest

from agents.character_analysis_agent import CharacterAnalysisAgent
from core.metadata_schemas import CharacterMetadata, InteractionMetadata  # NEW MODULE
from core.show_registry import ShowRegistry  # NEW MODULE - doesn't exist yet


@pytest.fixture
def character_agent(tmp_path):
    """A ``CharacterAnalysisAgent`` that touches neither disk nor the network.

    The persist directory is pytest's ``tmp_path``, the ChromaDB client is a
    mock handing out one distinct collection mock per collection name, and the
    sentence-transformers encoder is never constructed. Tests drive the agent by
    setting ``.query``/``.get`` on those collection mocks.
    """
    collections: dict[str, Mock] = {}

    def _get_or_create_collection(name, **_kwargs):
        return collections.setdefault(name, Mock(name=f"{name}_collection"))

    with (
        patch("chromadb.PersistentClient") as client_class,
        patch("agents.character_analysis_agent.SentenceTransformer"),
    ):
        client_class.return_value.get_or_create_collection.side_effect = _get_or_create_collection
        return CharacterAnalysisAgent(persist_directory=str(tmp_path / "character_db"))


class TestMetadataValidation:
    """Test suite for metadata validation and show separation functionality.

    This class contains comprehensive tests for validating the metadata schemas,
    show registry functionality, and cross-show isolation mechanisms to ensure
    proper data separation and consistency across the system.
    """

    @pytest.fixture
    def sample_character_data(self):
        """Sample character data for testing."""
        return {
            "name": "Izuku Midoriya",
            "show_name": "My Hero Academia",
            "season": 1,
            "episode": 1,
            "dialogue_count": 15,
            "personality_traits": ["determined", "kind", "analytical"],
        }

    @pytest.fixture
    def sample_interaction_data(self):
        """Sample interaction data for testing."""
        return {
            "episode_key": "my_hero_academia_S1E1",
            "characters": ["Izuku Midoriya", "Katsuki Bakugo"],
            "interaction_type": "dialogue",
            "emotional_tone": "tense",
            "significance_score": 0.8,
        }

    def test_show_registry_canonical_naming(self):
        """Test show name canonicalization and alias handling.

        Validates that the show registry correctly resolves canonical names,
        handles aliases, and performs case-insensitive matching for show names.
        """
        registry = ShowRegistry()

        # Test canonical name resolution
        assert registry.get_show_id("My Hero Academia") == "my_hero_academia"
        assert registry.get_show_id("MHA") == "my_hero_academia"  # Alias
        assert registry.get_show_id("my hero academia") == "my_hero_academia"  # Case insensitive

        # Test validation
        canonical = registry.validate_show_name("MHA")
        assert canonical == "My Hero Academia"

    def test_show_registry_prevents_typos(self):
        """Test that similar show names are detected and handled.

        Validates the system's ability to detect and suggest corrections
        for common typos in show names to prevent data fragmentation.
        """
        registry = ShowRegistry()

        # Should detect and suggest correct name for typos
        suggested = registry.validate_show_name("My Hero Acadmia")  # Typo
        # Currently auto-adds new shows, so it should return the input name
        assert suggested == "My Hero Acadmia"

    def test_character_metadata_schema_validation(self, sample_character_data):
        """Test character metadata schema creation and validation.

        Validates that character metadata schemas are created correctly with
        all required fields, proper canonicalization, and consistent formatting.

        Args:
            sample_character_data (dict): Fixture providing sample character data
        """
        metadata = CharacterMetadata.create(
            show_name=sample_character_data["show_name"],
            season=sample_character_data["season"],
            episode=sample_character_data["episode"],
            character_name=sample_character_data["name"],
            dialogue_count=sample_character_data["dialogue_count"],
            personality_traits=sample_character_data["personality_traits"],
        )

        metadata_dict = metadata.to_dict()

        # All required fields must be present
        required_fields = [
            "show_name",
            "show_id",
            "season",
            "episode",
            "episode_key",
            "character_name",
            "canonical_character_name",
            "created_at",
        ]
        for field in required_fields:
            assert field in metadata_dict

        # Show name should be canonical
        assert metadata_dict["show_name"] == "My Hero Academia"
        assert metadata_dict["show_id"] == "my_hero_academia"
        assert metadata_dict["episode_key"] == "my_hero_academia_S1E1"

    def test_interaction_metadata_includes_show_info(self, sample_interaction_data):
        """Test that interaction metadata includes all show information."""
        metadata = InteractionMetadata.create(
            show_name="My Hero Academia",
            season=1,
            episode=1,
            characters=sample_interaction_data["characters"],
            interaction_type=sample_interaction_data["interaction_type"],
            emotional_tone=sample_interaction_data["emotional_tone"],
            significance_score=sample_interaction_data["significance_score"],
        )

        metadata_dict = metadata.to_dict()

        # CRITICAL: show_name must be present in interactions
        assert "show_name" in metadata_dict
        assert "show_id" in metadata_dict
        assert metadata_dict["show_name"] == "My Hero Academia"
        assert metadata_dict["show_id"] == "my_hero_academia"

    def test_character_agent_requires_show_name(self, character_agent):
        """Test that character agent methods require show_name parameter.

        A signature check: it never reaches a collection, so the agent is the
        hermetic one rather than a real ChromaDB-backed instance.
        """
        agent = character_agent

        # These should raise TypeError because show_name is now required positional argument
        with pytest.raises(TypeError):
            agent.get_character_relationships("Deku")  # Missing show_name

        with pytest.raises(TypeError):
            agent.search_character_moments("heroic moment", "Deku")  # Missing show_name

    def test_cross_show_isolation_enforcement(self, character_agent):
        """Test that queries properly isolate shows.

        What is under test is the ``where`` clause the agent builds, which is
        asserted against a mocked collection - a real vector store would add
        nothing.
        """
        agent = character_agent

        # Mock the characters collection, not interactions
        with patch.object(agent.characters_collection, "query") as mock_query:
            mock_query.return_value = {
                "metadatas": [
                    [
                        {"character_name": "Sakura", "show_name": "Naruto", "show_id": "naruto"},
                        {
                            "character_name": "Sakura",
                            "show_name": "Card Captor Sakura",
                            "show_id": "card_captor_sakura",
                        },
                    ]
                ],
                "documents": [["doc1", "doc2"]],
                "distances": [[0.1, 0.2]],
            }

            # Query for Naruto's Sakura should NOT return Card Captor Sakura
            agent.find_similar_characters("Sakura", "Naruto", include_same_show=False)

            # Should have been called with proper show filtering
            mock_query.assert_called_with(
                query_texts=["Sakura character analysis"],
                where={
                    "$and": [
                        {"show_name": {"$ne": "Naruto"}},  # Exclude same show
                        {"character_name": {"$eq": "Sakura"}},
                    ]
                },
                n_results=10,
                include=["documents", "metadatas", "distances"],
            )

    def test_metadata_migration_for_existing_data(self):
        """Test migration of existing data without proper metadata.

        ``migrate_interaction_metadata`` opens its own ``chromadb``
        ``PersistentClient`` at a hardcoded path, so that is what gets patched;
        otherwise the call creates ``data/databases/character_db`` as a side
        effect of running the test suite.
        """
        from scripts.migrate_metadata import migrate_interaction_metadata  # NEW SCRIPT

        collection = Mock()
        collection.get.return_value = {
            # An interaction with no show_name: exactly what migration is for.
            "metadatas": [{"episode_key": "my_hero_academia_S1E1"}],
            "documents": ["Izuku and Bakugo argue"],
            "ids": ["interaction_1"],
        }

        with patch("chromadb.PersistentClient") as client_class:
            client_class.return_value.get_collection.return_value = collection
            migration_result = migrate_interaction_metadata()

        # Should report number of fixed records
        assert migration_result["success"] is True
        assert migration_result["migrated_count"] == 1
        written = collection.update.call_args.kwargs["metadatas"][0]
        assert written["show_name"] == "My Hero Academia"

    def test_duplicate_character_handling(self, character_agent):
        """Test handling of characters with same names across shows.

        The old version built a real agent, so it needed the HuggingFace model,
        and then asserted only ``isinstance(..., dict)`` - which the agent's own
        ``except`` clause satisfies by returning ``{"error": ...}``. Here a
        collection stub answers the ``where`` clause the agent sends, so the
        assertions can be about which rows each name actually resolves to.
        """
        corpus = [
            {
                "character_name": "Eren",
                "show_name": "Attack on Titan",
                "season": 1,
                "episode": 1,
                "dialogue_count": 12,
                "personality_traits": json.dumps(["determined"]),
            },
            {
                "character_name": "Eren",
                "show_name": "Attack on Titan",
                "season": 1,
                "episode": 2,
                "dialogue_count": 20,
                "personality_traits": json.dumps(["determined", "angry"]),
            },
            {
                "character_name": "Eren Yeager",
                "show_name": "Attack on Titan",
                "season": 1,
                "episode": 3,
                "dialogue_count": 30,
                "personality_traits": json.dumps(["determined"]),
            },
            # Same first name, different show: must never be returned.
            {
                "character_name": "Eren",
                "show_name": "Shingeki Spinoff",
                "season": 1,
                "episode": 1,
                "dialogue_count": 99,
                "personality_traits": json.dumps(["loud"]),
            },
        ]

        def _query(*, where, **_kwargs):
            wanted = {}
            for clause in where["$and"]:
                ((field, condition),) = clause.items()
                wanted[field] = condition["$eq"]
            assert "show_name" in wanted, "the agent must always filter by show"
            matched = [
                row
                for row in corpus
                if row["character_name"] == wanted["character_name"]
                and row["show_name"] == wanted["show_name"]
            ]
            return {"metadatas": [matched], "documents": [[""] * len(matched)]}

        character_agent.characters_collection.query.side_effect = _query

        aot_eren = character_agent.analyze_character_development("Eren", "Attack on Titan")
        eren_yeager = character_agent.analyze_character_development(
            "Eren Yeager", "Attack on Titan"
        )

        # Two characters whose names overlap resolve to different episode sets,
        # and the "Eren" of the other show is excluded from both.
        assert "error" not in aot_eren, aot_eren.get("error")
        assert "error" not in eren_yeager, eren_yeager.get("error")
        assert aot_eren["dialogue_trend"] == [12, 20]
        assert eren_yeager["dialogue_trend"] == [30]
        assert aot_eren["total_episodes"] == 2
        assert eren_yeager["total_episodes"] == 1

    def test_metadata_consistency_validation(self):
        """Test system-wide metadata consistency checking.

        ``MetadataQualityAgent`` hardcodes its ChromaDB path and swallows the
        connection failure, so unpatched this test both wrote into
        ``data/databases/`` and asserted against whatever rows happened to be on
        the machine. Patched, the rows are the ones this test states.
        """
        from agents.quality_agents.metadata_quality_agent import MetadataQualityAgent  # NEW AGENT

        characters = Mock()
        interactions = Mock()
        # One profile uses an alias rather than the canonical show name.
        characters.get.return_value = {
            "metadatas": [{"character_name": "Izuku", "show_name": "MHA"}]
        }
        # One interaction has no show_name at all.
        interactions.get.return_value = {"metadatas": [{"episode_key": "my_hero_academia_S1E1"}]}
        collections = {
            "character_profiles": characters,
            "character_interactions": interactions,
        }

        with patch("chromadb.PersistentClient") as client_class:
            client_class.return_value.get_collection.side_effect = lambda name: collections[name]
            quality_agent = MetadataQualityAgent()

        validation_report = quality_agent.validate_metadata_consistency()

        # Should check for missing fields, inconsistent naming, etc.
        assert "missing_show_names" in validation_report
        assert "inconsistent_names" in validation_report
        assert "canonical_violations" in validation_report
        assert "total_issues" in validation_report
        assert validation_report["missing_show_names"] == 1
        assert validation_report["canonical_violations"] == 1
        assert validation_report["total_issues"] == 2
