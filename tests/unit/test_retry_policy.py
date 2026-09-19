"""
Tests for the shared retry policy (``utils/retry.py``) and its adopters.

The hand-rolled backoff loops these replaced were never tested, which is how
``agents/content_agent.py`` shipped a retry loop that never retried (its
``break`` sat on the failure branch). Every test here runs with a zero delay
range so the real backoff schedule is exercised without actually sleeping.
"""

import logging

import pytest
import requests

from agents.content_agent import ContentAgent
from utils.retry import with_http_retries

logger = logging.getLogger(__name__)

NO_DELAY = (0.0, 0.0)


class FlakyCallable:
    """A callable that fails ``fail_times`` times and then succeeds."""

    def __init__(self, fail_times: int, error: Exception | None = None, success: object = "ok"):
        self.fail_times = fail_times
        self.error = error or requests.exceptions.ConnectionError("connection reset")
        self.success = success
        self.calls = 0

    def __call__(self) -> object:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise self.error
        return self.success


class TestWithHttpRetries:
    """The retry policy itself."""

    def test_a_callable_that_succeeds_on_the_third_attempt_succeeds(self):
        """The headline case: two transient failures, then a result."""
        flaky = FlakyCallable(fail_times=2, success={"transcript": "..."})

        result = with_http_retries(
            flaky, attempts=3, delay_range=NO_DELAY, logger=logger, description="flaky fetch"
        )

        assert result == {"transcript": "..."}
        assert flaky.calls == 3, "should have taken exactly three attempts"

    def test_a_callable_that_never_succeeds_reraises_the_last_error(self):
        """
        Exhaustion re-raises the original exception, not ``tenacity.RetryError``.

        Callers already have ``except requests.exceptions.RequestException``
        handlers; wrapping would have silently broken every one of them.
        """
        flaky = FlakyCallable(fail_times=99)

        with pytest.raises(requests.exceptions.ConnectionError):
            with_http_retries(
                flaky, attempts=3, delay_range=NO_DELAY, logger=logger, description="doomed fetch"
            )

        assert flaky.calls == 3, "should have used its full attempt budget"

    def test_a_non_transient_exception_is_not_retried(self):
        """
        A bug is not a network blip.

        This is the behaviour change that matters: the old loops caught bare
        ``Exception``, so a ``KeyError`` from a renamed field was retried three
        times and then reported as "this source has no transcript".
        """
        flaky = FlakyCallable(fail_times=99, error=KeyError("quality_score"))

        with pytest.raises(KeyError):
            with_http_retries(
                flaky, attempts=3, delay_range=NO_DELAY, logger=logger, description="buggy parse"
            )

        assert flaky.calls == 1, "a non-transient error must fail on the first attempt"

    def test_an_empty_result_is_retried_and_finally_returned(self):
        """
        An empty body is retryable, but exhaustion is an answer, not an error.

        The scrapers report "nothing here" as ``None``/``[]`` rather than by
        raising, so the policy retries falsy results and then hands the falsy
        value back.
        """
        calls = []

        def always_empty() -> list[str]:
            calls.append(1)
            return []

        result = with_http_retries(
            always_empty, attempts=3, delay_range=NO_DELAY, logger=logger, description="empty"
        )

        assert result == []
        assert len(calls) == 3

    def test_an_empty_result_recovers_on_a_later_attempt(self):
        """Two empty bodies then real content: the content wins."""
        results = [None, None, {"transcript": "found it"}]

        def flaky_body() -> object:
            return results.pop(0)

        assert with_http_retries(
            flaky_body, attempts=3, delay_range=NO_DELAY, logger=logger, description="body"
        ) == {"transcript": "found it"}

    def test_retry_on_empty_can_be_switched_off(self):
        """An opt-out for callers where a falsy result is a final answer."""
        calls = []

        def always_empty() -> list[str]:
            calls.append(1)
            return []

        assert (
            with_http_retries(
                always_empty,
                attempts=3,
                delay_range=NO_DELAY,
                logger=logger,
                description="empty",
                retry_on_empty=False,
            )
            == []
        )
        assert len(calls) == 1


class TestContentAgentRetriesAnUnreachableUrl:
    """
    Regression tests for the retry loop that never retried.

    ``get_html_content`` returns ``None`` rather than raising when a page cannot
    be fetched. The old loop's ``break`` was on the failure branch, so that
    ``None`` ended the loop on the first pass and the agent reported
    "Max retries exceeded" having made exactly one attempt.
    """

    @staticmethod
    def _agent() -> ContentAgent:
        class UnusedModel:
            def invoke(self, prompt: str) -> str:
                raise AssertionError("the model must not be reached when there is no content")

        agent = ContentAgent(UnusedModel())
        agent.delay_range = NO_DELAY
        return agent

    def test_an_unreachable_url_is_retried_the_full_number_of_times(self, monkeypatch):
        attempts = []

        def failing_fetch(url: str) -> None:
            attempts.append(url)
            return None

        monkeypatch.setattr("utils.web_utils.get_html_content", failing_fetch)

        agent = self._agent()
        result = agent.extract_and_analyze("https://example.com/missing")

        assert len(attempts) == agent.retry_count, (
            f"expected {agent.retry_count} attempts, got {len(attempts)} - "
            "the retry loop is not retrying an empty fetch"
        )
        assert result["success"] is False
        assert "https://example.com/missing" in result["error"]

    def test_a_url_that_recovers_on_the_third_attempt_is_analysed(self, monkeypatch):
        pages = [None, None, "<html><h1>Ep 1</h1><div class='full-script'>Hello there</div></html>"]

        def flaky_fetch(url: str) -> str | None:
            return pages.pop(0)

        monkeypatch.setattr("utils.web_utils.get_html_content", flaky_fetch)

        class Model:
            def invoke(self, prompt: str) -> str:
                return "analysis"

        agent = ContentAgent(Model())
        agent.delay_range = NO_DELAY

        result = agent.extract_and_analyze("https://example.com/flaky")

        assert result["success"] is True
        assert result["analysis"] == "analysis"
        assert pages == [], "all three attempts should have been consumed"

    def test_a_model_failure_is_reported_not_raised(self, monkeypatch):
        """
        The agent's contract with the orchestrator is a result dict.

        ``workflow_orchestrator`` branches on ``result["success"]``, so the
        broad handler at this boundary is deliberate - it is documented as such
        in ``extract_and_analyze``.
        """
        monkeypatch.setattr(
            "utils.web_utils.get_html_content",
            lambda url: "<html><div class='full-script'>text</div></html>",
        )

        class BrokenModel:
            def invoke(self, prompt: str) -> str:
                raise RuntimeError("provider is down")

        agent = ContentAgent(BrokenModel())
        agent.delay_range = NO_DELAY

        result = agent.extract_and_analyze("https://example.com/ok")

        assert result["success"] is False
        assert "provider is down" in result["error"]
