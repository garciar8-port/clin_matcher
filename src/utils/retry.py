"""Tenacity-based retry utilities for LLM and API calls."""

from __future__ import annotations

import logging

import httpx
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

logger = logging.getLogger(__name__)


def _log_retry(retry_state: RetryCallState) -> None:
    """Log retry attempts for observability."""
    logger.warning(
        "Retrying %s (attempt %d): %s",
        retry_state.fn.__name__ if retry_state.fn else "unknown",
        retry_state.attempt_number,
        retry_state.outcome.exception() if retry_state.outcome else "unknown",
    )


llm_retry = retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential_jitter(initial=2, max=60, jitter=5),
    before_sleep=_log_retry,
    reraise=True,
)

api_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=2, max=60, jitter=3),
    retry=retry_if_exception_type((httpx.HTTPError,)),
    before_sleep=_log_retry,
    reraise=True,
)
