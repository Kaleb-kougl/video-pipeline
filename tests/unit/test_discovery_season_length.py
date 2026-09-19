"""
Tests that episode discovery never invents a season length.

`discover_season_episodes` used to fall back to "try 25 episodes" for any show
it had no configuration for. For a 12-episode season that meant 13 searches for
episodes that do not exist, and every one of them came back in the result list -
as a `not_found` record at best, and as a fake `available` episode whenever a
constructed URL happened to validate. `main.py` then takes `len(episodes)` as
the season length, so the guess propagated.

An unknown season is now probed and stops on observed evidence: a run of
consecutive misses ends the season, and the trailing misses are dropped rather
than reported.
"""

import pytest

from agents.discovery_agent import EpisodeDiscoveryAgent


@pytest.fixture
def agent(monkeypatch) -> EpisodeDiscoveryAgent:
    """A discovery agent whose per-episode politeness delay does not sleep."""
    agent = EpisodeDiscoveryAgent()
    monkeypatch.setattr("agents.discovery_agent.time.sleep", lambda *_: None)
    return agent


def _season_of(length: int):
    """A fake search that finds exactly `length` episodes in every season."""

    def fake_search(show_name, season, episode, episode_title=None):
        if episode > length:
            return None
        return {
            "url": f"https://example.test/{season}/{episode}",
            "source": "fake",
            "quality_score": 0.9,
            "found_via": "search",
        }

    return fake_search


def test_unknown_show_does_not_probe_a_magic_number_of_episodes(agent, monkeypatch):
    """A 12-episode season yields 12 episodes, not 25 (13 of them invented)."""
    probed: list[int] = []

    real = _season_of(12)

    def counting_search(show_name, season, episode, episode_title=None):
        probed.append(episode)
        return real(show_name, season, episode, episode_title)

    monkeypatch.setattr(agent, "search_episode_enhanced", counting_search)

    episodes = agent.discover_season_episodes("Chainsaw Man", 1)

    assert [ep["episode"] for ep in episodes] == list(range(1, 13))
    assert all(ep["available"] for ep in episodes)
    # Stopped after the configured run of misses instead of walking to 25.
    assert max(probed) == 12 + agent.CONSECUTIVE_MISSES_TO_STOP
    assert 25 not in probed


def test_unknown_season_length_is_marked_as_such(agent, monkeypatch):
    """A probed count is labelled, so callers never read it as authoritative."""
    monkeypatch.setattr(agent, "search_episode_enhanced", _season_of(4))

    episodes = agent.discover_season_episodes("Chainsaw Man", 1)

    assert episodes
    assert {ep["episode_count_source"] for ep in episodes} == {"probe"}
    assert {ep["season_coverage"] for ep in episodes} == {"partial"}


def test_a_season_with_nothing_in_it_returns_nothing(agent, monkeypatch):
    """No episodes found means an empty list, not 25 `not_found` placeholders."""
    monkeypatch.setattr(agent, "search_episode_enhanced", lambda *a, **kw: None)

    assert agent.discover_season_episodes("Chainsaw Man", 9) == []


def test_a_gap_inside_a_season_is_kept(agent, monkeypatch):
    """Misses followed by a hit are real gaps and stay in the result."""

    def patchy(show_name, season, episode, episode_title=None):
        if episode in (1, 2, 5):
            return {"url": f"https://example.test/{episode}", "found_via": "search"}
        return None

    monkeypatch.setattr(agent, "search_episode_enhanced", patchy)

    episodes = agent.discover_season_episodes("Chainsaw Man", 1)

    assert [(ep["episode"], ep["available"]) for ep in episodes] == [
        (1, True),
        (2, True),
        (3, False),
        (4, False),
        (5, True),
    ]


def test_probe_ceiling_is_reported_as_partial(agent, monkeypatch, caplog):
    """A season that never stops is truncated loudly, not silently."""
    monkeypatch.setattr(agent, "search_episode_enhanced", _season_of(10_000))

    episodes = agent.discover_season_episodes("One Piece", 1)

    assert len(episodes) == agent.MAX_EPISODE_PROBES
    assert "probe ceiling" in caplog.text
    assert {ep["season_coverage"] for ep in episodes} == {"partial"}


def test_configured_season_length_is_still_honoured(agent, monkeypatch):
    """The show with a real configuration keeps its exact, known episode count."""
    monkeypatch.setattr(agent, "search_episode_enhanced", _season_of(13))

    episodes = agent.discover_season_episodes("My Hero Academia", 1)

    assert len(episodes) == 13
    assert {ep["episode_count_source"] for ep in episodes} == {"config"}
    assert {ep["season_coverage"] for ep in episodes} == {"complete"}
    # Titles come from the configuration, not from the search.
    assert episodes[0]["title"] == "Izuku_Midoriya_Origin"


def test_configured_season_reports_misses_within_the_known_length(agent, monkeypatch):
    """With a known length, a missing episode is a real gap and is reported."""
    monkeypatch.setattr(agent, "search_episode_enhanced", lambda *a, **kw: None)

    episodes = agent.discover_season_episodes("My Hero Academia", 1)

    assert len(episodes) == 13
    assert not any(ep["available"] for ep in episodes)


def test_unknown_show_stops_at_the_first_empty_season(agent, monkeypatch):
    """Season probing stops on evidence, not after a hardcoded five seasons."""
    seasons_seen: list[int] = []

    def two_seasons(show_name, season, episode, episode_title=None):
        seasons_seen.append(season)
        if season <= 2 and episode <= 3:
            return {"url": f"https://example.test/{season}/{episode}", "found_via": "search"}
        return None

    monkeypatch.setattr(agent, "search_episode_enhanced", two_seasons)

    episodes = agent.discover_all_episodes("Chainsaw Man")

    assert sorted({ep["season"] for ep in episodes}) == [1, 2]
    assert max(seasons_seen) == 3, "should stop right after the first empty season"
    assert len(episodes) == 6


def test_configured_show_walks_its_configured_seasons(agent, monkeypatch):
    """The configured show is driven by its configuration, not by probing."""
    monkeypatch.setattr(agent, "search_episode_enhanced", lambda *a, **kw: None)
    walked: list[tuple[str, int]] = []

    def record(show_name, season):
        walked.append((show_name, season))
        return []

    monkeypatch.setattr(agent, "discover_season_episodes", record)

    agent.discover_all_episodes("My Hero Academia")

    assert walked == [("My Hero Academia", season) for season in range(1, 8)]
