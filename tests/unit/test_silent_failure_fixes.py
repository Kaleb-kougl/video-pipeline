"""
Regression tests for three failures that used to be silent.

Each of these was a value the pipeline produced confidently and wrongly: a
consistency score computed against another episode's palette, a metadata
hierarchy whose subclasses could not honour the factory they inherited, and a
database write that failed while the caller was told it had succeeded.
"""

from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from core.exceptions import CharacterStoreError, PipelineError
from core.metadata_schemas import BaseMetadata, CharacterMetadata, InteractionMetadata
from core.visual_coherence_manager import VisualCoherenceManager


class TestEpisodeIdIsRequired:
    """
    ``episode_context.get("episode_id")`` returning ``None`` was a latent bug.

    ``None`` is a perfectly valid dict key, so every context without an
    ``episode_id`` shared one bucket in ``episode_color_palettes`` and
    ``style_templates``. The first image to arrive established "the" palette and
    every later image - from any episode - was scored against it.
    """

    @pytest.fixture
    def manager(self) -> VisualCoherenceManager:
        return VisualCoherenceManager(consistency_threshold=0.8)

    @pytest.fixture
    def image(self) -> np.ndarray:
        rng = np.random.default_rng(seed=7)
        return rng.integers(0, 255, (64, 64, 3), dtype=np.uint8)

    @pytest.mark.parametrize(
        "context",
        [
            pytest.param({}, id="missing"),
            pytest.param({"episode_id": None}, id="explicit-none"),
            pytest.param({"episode_id": ""}, id="empty"),
            pytest.param({"episode_id": "   "}, id="blank"),
            pytest.param({"episode_id": 17}, id="not-a-string"),
        ],
    )
    async def test_a_context_without_an_episode_id_is_rejected(self, manager, image, context):
        with pytest.raises(ValueError, match="episode_id"):
            await manager._calculate_style_consistency(image, context)

    async def test_no_none_key_is_ever_written_to_the_reference_data(self, manager, image):
        with pytest.raises(ValueError):
            await manager._calculate_style_consistency(image, {"visual_style": "anime"})

        assert None not in manager.style_templates
        assert None not in manager.episode_color_palettes
        assert manager.style_templates == {}, "a rejected context must leave no trace"

    async def test_two_episodes_keep_separate_style_templates(self, manager, image):
        await manager._calculate_style_consistency(image, {"episode_id": "naruto_s1e1"})
        await manager._calculate_style_consistency(image, {"episode_id": "bleach_s1e1"})

        assert set(manager.style_templates) == {"naruto_s1e1", "bleach_s1e1"}

    async def test_evaluation_rejects_a_context_without_an_episode_id(self, manager, monkeypatch):
        """The failure is raised before any scoring happens, not swallowed into 0.5."""
        rng = np.random.default_rng(seed=11)
        monkeypatch.setattr(
            "cv2.imread", lambda path: rng.integers(0, 255, (32, 32, 3), dtype=np.uint8)
        )

        with pytest.raises(ValueError, match="episode_id"):
            await manager._evaluate_visual_consistency("/any/image.png", {}, ["Naruto"])


class TestMetadataHierarchyIsCoherent:
    """
    The subclasses used to override ``BaseMetadata.create`` incompatibly.

    A caller holding a ``BaseMetadata`` could not call ``create(show, s, e)`` on
    an arbitrary subclass, which is the definition of a Liskov violation and the
    reason the module sat behind a mypy ``ignore_errors``. The shared step is now
    the *fields*, not the constructor.
    """

    def test_the_base_class_no_longer_advertises_a_factory_its_subclasses_break(self):
        assert not hasattr(BaseMetadata, "create"), (
            "BaseMetadata.create was the signature every subclass violated; "
            "the shared step is identity_fields()"
        )

    def test_identity_fields_builds_a_complete_base_record(self):
        fields = BaseMetadata.identity_fields("My Hero Academia", 1, 5)
        metadata = BaseMetadata(**fields)

        assert metadata.season == 1
        assert metadata.episode == 5
        assert metadata.episode_key == f"{metadata.show_id}_S1E5"
        assert metadata.created_at, "created_at must be stamped"

    def test_identity_fields_canonicalizes_the_show_name(self):
        fields = BaseMetadata.identity_fields("my hero academia", 2, 3)

        assert (
            fields["show_id"] == BaseMetadata.identity_fields("My Hero Academia", 2, 3)["show_id"]
        )

    def test_every_subclass_factory_shares_the_same_identity(self):
        character = CharacterMetadata.create("My Hero Academia", 1, 5, "Deku", 12, ["brave"])
        interaction = InteractionMetadata.create(
            "My Hero Academia", 1, 5, ["Deku", "Bakugo"], "conflict", "tense", 0.8
        )

        assert character.episode_key == interaction.episode_key
        assert character.show_id == interaction.show_id
        assert character.show_name == interaction.show_name

    def test_subclass_records_still_serialize_their_own_fields(self):
        payload = CharacterMetadata.create("Naruto", 1, 1, "Naruto", 3, ["loud"]).to_dict()

        assert payload["character_name"] == "Naruto"
        assert payload["dialogue_count"] == 3
        assert payload["episode_key"].endswith("_S1E1")


class TestCharacterStoreFailuresAreNotSwallowed:
    """
    A failed ChromaDB write used to be logged and forgotten.

    ``analyze_episode_characters`` then returned a complete set of profiles that
    had never reached the database, and every later query reported "no data"
    rather than "the writes failed".
    """

    @staticmethod
    def _agent_with_broken_collections():
        """Build an agent without touching a real ChromaDB instance."""
        from agents.character_analysis_agent import CharacterAnalysisAgent

        def explode(**kwargs: Any) -> None:
            raise RuntimeError("chromadb is unreachable")

        agent = object.__new__(CharacterAnalysisAgent)
        agent.characters_collection = SimpleNamespace(upsert=explode)
        agent.interactions_collection = SimpleNamespace(upsert=explode)
        agent.development_collection = SimpleNamespace(upsert=explode)
        return agent

    @staticmethod
    def _profile():
        from agents.character_analysis_agent import CharacterProfile

        return CharacterProfile(
            name="Deku",
            canonical_name="Deku",
            aliases=[],
            dialogue_chunks=["I am here."],
            personality_traits=["determined"],
            relationships={},
            character_arc=[],
            first_appearance={"show": "My Hero Academia", "season": 1, "episode": 1},
            total_dialogue_count=1,
            shows={"My Hero Academia"},
            semantic_embedding=None,
        )

    def test_a_failed_profile_write_raises(self):
        agent = self._agent_with_broken_collections()

        with pytest.raises(CharacterStoreError, match="Deku"):
            agent._store_character_profile(self._profile(), "my_hero_academia_S1E1")

    def test_a_failed_profile_write_keeps_the_underlying_cause(self):
        agent = self._agent_with_broken_collections()

        with pytest.raises(CharacterStoreError) as caught:
            agent._store_character_profile(self._profile(), "my_hero_academia_S1E1")

        assert isinstance(caught.value.__cause__, RuntimeError)
        assert "chromadb is unreachable" in str(caught.value.__cause__)

    def test_the_domain_errors_share_one_base(self):
        """Callers that want to catch "anything the pipeline raises on purpose" can."""
        assert issubclass(CharacterStoreError, PipelineError)
