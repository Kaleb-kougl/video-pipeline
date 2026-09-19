"""
Tests that transcript source discovery reports its own coverage honestly.

`TranscriptSourceDiscoveryAgent` used to fan out to `_check_myanimelist`,
`_check_anidb`, `_check_anime_news_network` and `_check_crunchyroll`, each of
which was a comment and `return None`. Callers only ever see a flat list of
sources, so "not implemented" was indistinguishable from "checked, nothing
found". These tests keep the stubs from coming back and pin the replacement
contract: the unsupported sources are named, not silently skipped.
"""

import logging

import pytest

from agents.transcript_source_agent import TranscriptSourceDiscoveryAgent


@pytest.fixture
def agent() -> TranscriptSourceDiscoveryAgent:
    return TranscriptSourceDiscoveryAgent()


@pytest.mark.parametrize(
    "method_name",
    [
        "_check_myanimelist",
        "_check_anidb",
        "_check_anime_news_network",
        "_check_crunchyroll",
        "_search_anime_specific_sources",
    ],
)
def test_placeholder_checkers_are_gone(agent, method_name):
    """A checker that always returns None is worse than no checker at all."""
    assert not hasattr(agent, method_name), (
        f"{method_name} is back; if it is implemented for real, delete this "
        "assertion and test the implementation instead"
    )


def test_unsearched_sources_are_declared(agent):
    """The sources the agent cannot reach are named on the class, not hidden."""
    assert set(agent.UNSEARCHED_SOURCES) == {
        "MyAnimeList",
        "AniDB",
        "Anime News Network",
        "Crunchyroll",
    }


def test_discovery_reports_which_sources_were_not_searched(agent, monkeypatch, caplog):
    """
    An empty result must not read as "every source was checked and came up empty".

    The discovery run says out loud which source families it never queried.
    """
    monkeypatch.setattr(agent, "_search_known_patterns", lambda *args, **kwargs: [])
    monkeypatch.setattr(agent, "_perform_web_search", lambda *args, **kwargs: [])

    with caplog.at_level(logging.INFO, logger="agents.transcript_source_agent"):
        sources = agent.discover_sources_for_show("Chainsaw Man", season=1)

    assert sources == []
    summary = "\n".join(record.getMessage() for record in caplog.records)
    for unsearched in agent.UNSEARCHED_SOURCES:
        assert unsearched in summary


def test_docstring_states_the_limitation(agent):
    """The limitation belongs in the API docs, not only in a log line."""
    doc = TranscriptSourceDiscoveryAgent.discover_sources_for_show.__doc__ or ""
    assert "not" in doc.lower()
    assert "UNSEARCHED_SOURCES" in doc
