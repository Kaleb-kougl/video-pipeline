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


# ---------------------------------------------------------------------------
# `known_source_patterns` used to carry "community_sites" and
# "streaming_platforms" keys that `_search_known_patterns` never iterated: the
# config advertised source families the agent never looked at. The domains are
# still useful for *classifying* a URL, so they moved to `source_type_domains`,
# which `_analyze_potential_source` actually reads.
# ---------------------------------------------------------------------------


def _requested_hosts(agent, show_name: str) -> set[str]:
    """Hosts that `_search_known_patterns` actually tries for `show_name`."""
    from urllib.parse import urlparse

    seen: set[str] = set()

    def record(url, source_type, name, season=None):
        seen.add(urlparse(url).netloc)
        return None

    agent._check_source_availability = record
    agent._search_known_patterns(show_name)
    return seen


def test_every_configured_source_family_is_actually_searched(agent):
    """A family in `known_source_patterns` that nothing crawls is dead config."""
    from urllib.parse import urlparse

    show_name = "Chainsaw Man"
    slug = agent._normalize_show_name(show_name)
    requested = _requested_hosts(agent, show_name)

    for family, patterns in agent.known_source_patterns.items():
        for pattern in patterns:
            host = urlparse(pattern.format(slug) if "{}" in pattern else pattern).netloc
            assert host in requested, (
                f"{family} lists {pattern}, but _search_known_patterns never requests {host}; "
                "either crawl it or move it to source_type_domains"
            )


def test_uncrawlable_domains_are_not_advertised_as_source_patterns(agent):
    """The catalogue and streaming domains live with the classification data."""
    flattened = " ".join(
        pattern for patterns in agent.known_source_patterns.values() for pattern in patterns
    )
    for domain in ("myanimelist.net", "anidb.net", "animenewsnetwork.com", "crunchyroll.com"):
        assert domain not in flattened, (
            f"{domain} is listed as a crawl pattern but is in UNSEARCHED_SOURCES"
        )
        assert any(domain in d for ds in agent.source_type_domains.values() for d in ds), (
            f"{domain} was dropped instead of being kept as classification data"
        )


@pytest.mark.parametrize(
    ("url", "expected_type"),
    [
        ("https://myheroacademia.fandom.com/wiki/Episode_1", "wiki"),
        ("https://www.reddit.com/r/anime/comments/abc", "community"),
        ("https://anidb.net/anime/12345", "community"),
        ("https://www.animenewsnetwork.com/encyclopedia/anime.php", "community"),
        ("https://www.crunchyroll.com/series/abc", "official"),
        ("https://www.netflix.com/title/123", "official"),
        ("https://some-random-blog.example/transcript-dump", "fan_site"),
    ],
)
def test_classification_domains_are_wired_into_source_typing(agent, url, expected_type):
    """`source_type_domains` is read by the classifier, not just documented."""
    classified: list[str] = []

    agent._check_source_availability = lambda u, source_type, name, season=None: (
        classified.append(source_type) or None
    )
    agent._analyze_potential_source(url, "Chainsaw Man")

    assert classified == [expected_type]
