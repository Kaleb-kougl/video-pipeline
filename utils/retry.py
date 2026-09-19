"""
The one retry policy the network-facing agents share.

Why this module exists
----------------------
``tenacity`` was pinned in ``pyproject.toml`` and ``requirements.txt`` and
imported nowhere, while three agents hand-rolled the same loop::

    for attempt in range(self.retry_count):
        try:
            if attempt > 0:
                time.sleep(random.uniform(*self.delay_range) * (2 ** attempt))
            ...
        except requests.exceptions.RequestException:
            if attempt == self.retry_count - 1:
                break

Three copies, three sets of subtly different semantics, and one of them
(``agents/content_agent.py``) had a ``break`` on the *failure* branch, so it
never actually retried. The dependency was adopted rather than dropped because
it is already installed everywhere - ``langchain-core`` requires it - so using
it costs nothing, and because the loops it replaces are the kind of code that
is easy to get subtly wrong and hard to test by hand.

The backoff schedule is deliberately identical to the loops it replaces:
``uniform(*delay_range) * 2 ** attempt_number`` seconds before each retry.
"""

from __future__ import annotations

import logging
import random
from collections.abc import Callable
from typing import TypeVar, cast

import requests
from tenacity import (
    RetryCallState,
    Retrying,
    retry_if_exception_type,
    retry_if_result,
    stop_after_attempt,
)

T = TypeVar("T")

__all__ = ["TRANSIENT_HTTP_ERRORS", "with_http_retries"]

# What counts as "try again": connection resets, DNS failures, timeouts and the
# HTTPError that `raise_for_status()` raises. Note this deliberately includes
# 4xx, matching the behaviour of the loops this replaces. Anything outside this
# tuple - an AttributeError in a parser, a KeyError on a renamed field - is a
# bug in our code and is left to propagate on the first attempt.
TRANSIENT_HTTP_ERRORS = (requests.exceptions.RequestException,)


def with_http_retries(
    call: Callable[[], T],
    *,
    attempts: int,
    delay_range: tuple[float, float],
    logger: logging.Logger,
    description: str,
    retry_on_empty: bool = True,
) -> T:
    """
    Call ``call`` with jittered exponential backoff on transient HTTP failures.

    Args:
        call: Zero-argument callable performing one attempt.
        attempts: Total number of attempts, including the first.
        delay_range: ``(low, high)`` seconds; the jitter drawn before scaling.
        logger: Logger to report each retry on.
        description: Human-readable name of the operation, used in log lines.
        retry_on_empty: Also retry when ``call`` returns a falsy value. The
            scrapers need this because an empty body or an unparseable page is
            reported as ``None``/``[]`` rather than raised.

    Returns:
        Whatever ``call`` returned. If every attempt returned a falsy value,
        that last falsy value is returned rather than raised: "no transcript
        here" is an answer, not an error.

    Raises:
        requests.exceptions.RequestException: If the final attempt failed with a
            transient HTTP error. The original exception is re-raised, not
            wrapped in ``tenacity.RetryError``, so callers keep their ordinary
            ``except requests.exceptions.RequestException`` handlers.
        Exception: Any non-transient exception, immediately and unretried.
    """
    low, high = delay_range

    def _wait(retry_state: RetryCallState) -> float:
        # attempt_number is 1-based for the attempt that just failed, which
        # reproduces the original `uniform(...) * 2 ** attempt` exactly.
        return random.uniform(low, high) * (2**retry_state.attempt_number)

    def _should_retry_result(result: object) -> bool:
        return retry_on_empty and not result

    def _log_retry(retry_state: RetryCallState) -> None:
        outcome = retry_state.outcome
        if outcome is not None and outcome.failed:
            logger.warning(
                f"{description} failed (attempt {retry_state.attempt_number}/{attempts}): "
                f"{outcome.exception()}"
            )
        else:
            logger.debug(
                f"{description} returned no usable content "
                f"(attempt {retry_state.attempt_number}/{attempts}), retrying"
            )

    def _give_up(retry_state: RetryCallState) -> T:
        outcome = retry_state.outcome
        if outcome is not None and outcome.failed:
            exception = outcome.exception()
            if exception is not None:
                raise exception
        return cast(T, outcome.result() if outcome is not None else None)

    retrying = Retrying(
        stop=stop_after_attempt(attempts),
        wait=_wait,
        retry=(
            retry_if_exception_type(TRANSIENT_HTTP_ERRORS) | retry_if_result(_should_retry_result)
        ),
        before_sleep=_log_retry,
        retry_error_callback=_give_up,
    )

    return retrying(call)
