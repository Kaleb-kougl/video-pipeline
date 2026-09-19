"""
Tests for character name canonicalization and alias detection.

`CharacterProfile.canonical_name` used to be `canonical_name=name` with a TODO
next to it, and `aliases` was always `[]`. The field therefore agreed with
whatever spelling the transcript happened to use, which meant "Iida:",
"IIDA-kun:" and "Iida sensei:" produced three separate characters, each
claiming its own spelling was canonical.
"""

import pytest

import agents.character_analysis_agent as caa
from agents.character_analysis_agent import CharacterAnalysisAgent

pytest.importorskip("chromadb", reason="character analysis requires ChromaDB")


@pytest.fixture(scope="module")
def agent(tmp_path_factory, request):
    """
    A real agent backed by a throwaway ChromaDB directory.

    Sentence-transformer embeddings are switched off: they would download a
    model, and none of these tests look at the embedding.
    """
    original = caa.SENTENCE_TRANSFORMERS_AVAILABLE
    caa.SENTENCE_TRANSFORMERS_AVAILABLE = False
    request.addfinalizer(lambda: setattr(caa, "SENTENCE_TRANSFORMERS_AVAILABLE", original))
    persist_dir = tmp_path_factory.mktemp("character_db")
    return CharacterAnalysisAgent(persist_directory=str(persist_dir))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Iida", "Iida"),
        ("IIDA", "Iida"),
        ("  iida  ", "Iida"),
        ("Iida\tTenya", "Iida Tenya"),
        ("Iida-kun", "Iida"),
        ("Iida-San", "Iida"),
        ("All Might sensei", "All Might"),
        ("Mr. Aizawa", "Aizawa"),
        ("Professor Oak", "Oak"),
        ("Bakugo (shouting)", "Bakugo"),
        ("Deku [whispering]", "Deku"),
        ("o'brien", "O'Brien"),
    ],
)
def test_canonicalization_normalizes_decoration(agent, raw, expected):
    assert agent._canonicalize_character_name(raw) == expected


@pytest.mark.parametrize("raw", ["", "  ", "A", "1234", "???", "(beat)"])
def test_canonicalization_rejects_non_names(agent, raw):
    assert agent._canonicalize_character_name(raw) is None


def test_honorific_is_never_stripped_down_to_nothing(agent):
    """A bare honorific is still a (bad) name, not an empty string."""
    assert agent._canonicalize_character_name("Sensei") == "Sensei"


def test_canonicalization_is_idempotent(agent):
    once = agent._canonicalize_character_name("IIDA-kun ")
    assert agent._canonicalize_character_name(once) == once


def test_variant_spellings_merge_into_one_character(agent):
    """The original bug: three spellings, three characters, no aliases."""
    transcript = (
        "Iida: Everyone, please form an orderly line before we begin the exercise.\n"
        "IIDA-kun: Thank you for cooperating with the class representative.\n"
        "Iida sensei: We will now proceed to the training ground together.\n"
        "Uraraka: You really do take this seriously, don't you?\n"
    )

    dialogues, aliases = agent._extract_character_dialogues_with_aliases(transcript)

    assert set(dialogues) == {"Iida", "Uraraka"}
    # No dialogue is dropped when labels merge.
    assert len(dialogues["Iida"]) == 3
    assert aliases["Iida"] == ["Iida Sensei", "Iida-Kun"]
    assert "Uraraka" not in aliases


def test_profile_records_canonical_name_and_aliases(agent):
    transcript = (
        "Bakugo: Stay out of my way, I am going to win this one on my own.\n"
        "BAKUGO-kun: Do not tell me what I already know about my own quirk.\n"
    )

    profiles = agent.analyze_episode_characters("Test Show", 1, 1, transcript)

    assert "Bakugo" in profiles
    profile = profiles["Bakugo"]
    assert profile.canonical_name == "Bakugo"
    assert profile.aliases == ["Bakugo-Kun"]


def test_canonical_name_is_not_a_blind_echo_of_the_input(agent):
    """`canonical_name=name` would pass everything except this."""
    profile = agent._create_character_profile(
        "  MIDORIYA-kun ",
        ["I am going to be the greatest hero, no matter how long it takes."],
        "Test Show",
        1,
        1,
    )

    assert profile.canonical_name == "Midoriya"
    assert profile.canonical_name != profile.name


def test_stage_directions_are_filtered_out(agent):
    """
    The false-positive list is upper case, canonical names are title case.

    Comparing them directly meant the filter never fired.
    """
    transcript = (
        "NARRATOR: In a world where most of the population has some kind of power...\n"
        "Deku: I want to be a hero more than anything else in the world.\n"
    )

    dialogues, _aliases = agent._extract_character_dialogues_with_aliases(transcript)

    assert "Narrator" not in dialogues
    assert "Deku" in dialogues
