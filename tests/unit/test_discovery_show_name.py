"""
Regression tests for show-name handling in EpisodeDiscoveryAgent.

`discover_episode_url` used to ignore its caller entirely and search for a
hardcoded "My Hero Academia", so every other show silently got the wrong
search - and then fell through to legacy URL patterns built from a base URL
that also points at that one series. These tests pin both halves down.
"""

import pytest

from agents.discovery_agent import EpisodeDiscoveryAgent


@pytest.fixture
def agent() -> EpisodeDiscoveryAgent:
    """A discovery agent with no network calls performed during construction."""
    return EpisodeDiscoveryAgent()


def test_discover_episode_url_searches_for_the_requested_show(agent, monkeypatch):
    """The show name the caller passes is the one that gets searched."""
    searched: list[tuple] = []

    def fake_search(show_name, season, episode, episode_title=None):
        searched.append((show_name, season, episode, episode_title))
        return {"url": f"https://example.test/{show_name}/s{season}e{episode}"}

    monkeypatch.setattr(agent, "search_episode_enhanced", fake_search)

    url = agent.discover_episode_url("Chainsaw Man", 1, 3, ["Meowy's Whereabouts"])

    assert searched == [("Chainsaw Man", 1, 3, "Meowy's Whereabouts")]
    assert url == "https://example.test/Chainsaw Man/s1e3"


def test_discover_episode_url_for_show_threads_its_show_name(agent, monkeypatch):
    """The `_for_show` variant is a real delegation, not a separate code path."""
    searched: list[str] = []

    def fake_search(show_name, season, episode, episode_title=None):
        searched.append(show_name)
        return None

    monkeypatch.setattr(agent, "search_episode_enhanced", fake_search)
    monkeypatch.setattr(
        agent, "validate_episode_url", lambda url: pytest.fail(f"legacy fallback used: {url}")
    )

    assert agent.discover_episode_url_for_show("Attack on Titan", 4, 28) is None
    assert searched == ["Attack on Titan"]


def test_no_legacy_fallback_for_a_show_the_base_url_does_not_cover(agent, monkeypatch):
    """
    A failed search for some other show must not fall back to legacy URLs.

    `self.base_url` is hardcoded to one series, so a legacy URL built for
    "Naruto" resolves to a My Hero Academia transcript and validates happily.
    """
    monkeypatch.setattr(
        agent, "search_episode_enhanced", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        agent,
        "validate_episode_url",
        lambda url: pytest.fail(f"legacy URL validated for the wrong show: {url}"),
    )

    assert agent.discover_episode_url("Naruto", 1, 1, ["Enter: Naruto Uzumaki!"]) is None


def test_legacy_fallback_still_runs_for_the_legacy_show(agent, monkeypatch):
    """The show the base URL does cover keeps its legacy fallback."""
    monkeypatch.setattr(agent, "search_episode_enhanced", lambda *args, **kwargs: None)
    validated: list[str] = []

    def fake_validate(url: str) -> bool:
        validated.append(url)
        return True

    monkeypatch.setattr(agent, "validate_episode_url", fake_validate)

    url = agent.discover_episode_url("My Hero Academia", 1, 4)

    assert url == agent.generate_episode_url(1, 4)
    assert validated == [url]


@pytest.mark.parametrize("name", ["My Hero Academia", "my hero academia", "bnha", " MHA "])
def test_is_legacy_show_accepts_known_aliases(agent, name):
    assert agent.is_legacy_show(name) is True


@pytest.mark.parametrize("name", ["Naruto", "One Piece", "My Hero Academia Vigilantes"])
def test_is_legacy_show_rejects_other_shows(agent, name):
    assert agent.is_legacy_show(name) is False
