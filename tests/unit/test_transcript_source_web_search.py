"""
Tests that the scraped-Google web-search leg fails visibly instead of quietly.

`_search_with_google` scrapes google.com HTML directly, which Google blocks or
rate-limits for scripted clients. It used to swallow every failure and return
`[]`, so "blocked" and "searched, found nothing" reached callers as the same
empty list, and `discover_sources_for_show` reported a short source list as
though the web had been searched.

The leg is now opt-in, every failure mode raises `WebSearchUnavailable`, and the
outcome is recorded on the agent.
"""

import logging

import pytest
import requests

from agents.transcript_source_agent import TranscriptSourceDiscoveryAgent, WebSearchUnavailable

RESULTS_HTML = """
<html><body>
  <a href="/url?q=https://transcripts.example.org/chainsaw-man&amp;sa=U">Transcripts</a>
  <a href="/url?q=https://www.google.com/preferences">Settings</a>
  <a href="https://support.google.com/websearch">Help</a>
</body></html>
"""

BLOCK_HTML = """
<html><body><h1>About this page</h1>
<p>Our systems have detected unusual traffic from your computer network.</p>
<form id="captcha-form"></form></body></html>
"""


class FakeResponse:
    def __init__(self, text: str = "", status_code: int = 200, url: str = "https://google.com/s"):
        self.text = text
        self.status_code = status_code
        self.url = url


@pytest.fixture
def agent(monkeypatch) -> TranscriptSourceDiscoveryAgent:
    """An opt-in agent whose rate limiting does not actually sleep."""
    agent = TranscriptSourceDiscoveryAgent(enable_web_search=True)
    monkeypatch.setattr("agents.transcript_source_agent.time.sleep", lambda *_: None)
    return agent


def _stub_get(monkeypatch, response):
    def fake_get(*args, **kwargs):
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr("agents.transcript_source_agent.requests.get", fake_get)


def test_web_search_is_off_unless_asked_for():
    """Scraping a search engine is not baseline behaviour."""
    assert TranscriptSourceDiscoveryAgent().enable_web_search is False
    assert TranscriptSourceDiscoveryAgent(enable_web_search=True).enable_web_search is True


def test_disabled_leg_says_it_did_not_run(caplog):
    """A disabled leg must not look like "searched and found nothing"."""
    agent = TranscriptSourceDiscoveryAgent()

    with caplog.at_level(logging.INFO, logger="agents.transcript_source_agent"):
        assert agent._perform_web_search("Chainsaw Man") == []

    assert agent.last_web_search_status == "disabled"
    assert "opt-in" in caplog.text
    assert "does not mean the web was searched" in caplog.text


def test_a_parsable_results_page_yields_urls(agent, monkeypatch):
    """The happy path still works, and google's own links are filtered out."""
    _stub_get(monkeypatch, FakeResponse(RESULTS_HTML))

    assert agent._search_with_google("chainsaw man transcript") == [
        "https://transcripts.example.org/chainsaw-man"
    ]


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (FakeResponse(BLOCK_HTML), "block/captcha"),
        (FakeResponse("", status_code=429), "HTTP 429"),
        (FakeResponse("<html></html>"), "no '/url?q=' result links"),
        (FakeResponse("", url="https://www.google.com/sorry/index"), "block/captcha"),
        (requests.ConnectionError("dns failure"), "request to google.com failed"),
    ],
)
def test_every_failure_mode_is_distinguishable_from_no_results(
    agent, monkeypatch, response, expected
):
    """A blocked, throttled or unparseable response must not return `[]`."""
    _stub_get(monkeypatch, response)

    with pytest.raises(WebSearchUnavailable) as excinfo:
        agent._search_with_google("chainsaw man transcript")

    assert expected in str(excinfo.value)


def test_blocked_search_is_logged_loudly_and_stops_the_leg(agent, monkeypatch, caplog):
    """One refusal is enough: stop querying and record the leg as unavailable."""
    calls: list[str] = []

    def blocked(query):
        calls.append(query)
        raise WebSearchUnavailable("google.com returned a block/captcha interstitial")

    monkeypatch.setattr(agent, "_search_with_google", blocked)

    with caplog.at_level(logging.ERROR, logger="agents.transcript_source_agent"):
        assert agent._perform_web_search("Chainsaw Man", season=1) == []

    assert len(calls) == 1, "kept hammering an engine that already refused us"
    assert agent.last_web_search_status == "unavailable"
    assert "UNAVAILABLE" in caplog.text
    assert "NOT the same as" in caplog.text


def test_a_completed_search_reports_ok(agent, monkeypatch):
    """Only a query that actually ran may be reported as a real search."""
    monkeypatch.setattr(agent, "_search_with_google", lambda query: [])

    assert agent._perform_web_search("Chainsaw Man") == []
    assert agent.last_web_search_status == "ok"


@pytest.mark.parametrize(
    ("enable", "expected_status"),
    [(False, "disabled"), (True, "unavailable")],
)
def test_discovery_reports_the_web_search_outcome(monkeypatch, caplog, enable, expected_status):
    """
    Callers of the public API can tell whether the web-search leg ran.

    Without this, an empty discovery result reads as "nothing exists" when it
    really means "two of three legs never ran".
    """
    agent = TranscriptSourceDiscoveryAgent(enable_web_search=enable)
    monkeypatch.setattr("agents.transcript_source_agent.time.sleep", lambda *_: None)
    monkeypatch.setattr(agent, "_search_known_patterns", lambda *a, **kw: [])
    monkeypatch.setattr(
        agent,
        "_search_with_google",
        lambda query: (_ for _ in ()).throw(WebSearchUnavailable("blocked")),
    )

    with caplog.at_level(logging.INFO, logger="agents.transcript_source_agent"):
        sources = agent.discover_sources_for_show("Chainsaw Man", season=1)

    assert sources == []
    assert agent.last_web_search_status == expected_status
    assert agent.last_discovery_report["web_search"] == expected_status
    assert f"web search: {expected_status}" in caplog.text
