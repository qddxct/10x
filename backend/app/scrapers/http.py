"""HTTP client factory for scrapers.

Provides a configured :class:`httpx.Client` with sane defaults, a default
User-Agent, and transparent retry-on-5xx / transient-error behaviour.
"""

from __future__ import annotations

import logging
import time

import httpx

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = "Sporttery10xBot/0.1 (+https://example.com/bot)"
DEFAULT_TIMEOUT = 10.0
DEFAULT_RETRIES = 3
DEFAULT_BACKOFF = 0.5

RETRYABLE_STATUS = {500, 502, 503, 504}


class RetryExhaustedError(httpx.HTTPError):
    """Raised when the retry budget is exhausted."""


class _RetryTransport(httpx.BaseTransport):
    def __init__(
        self,
        wrapped: httpx.BaseTransport,
        *,
        retries: int,
        backoff: float,
    ) -> None:
        self._wrapped = wrapped
        self._retries = max(0, retries)
        self._backoff = max(0.0, backoff)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        attempts = self._retries + 1
        last_error: Exception | None = None
        last_response: httpx.Response | None = None

        for attempt in range(1, attempts + 1):
            try:
                response = self._wrapped.handle_request(request)
            except (httpx.ConnectError, httpx.ReadError, httpx.ReadTimeout) as err:
                last_error = err
                logger.warning(
                    "scraper http transient error attempt=%s url=%s err=%s",
                    attempt,
                    request.url,
                    err,
                )
                if attempt == attempts:
                    raise RetryExhaustedError(str(err)) from err
                self._sleep(attempt)
                continue

            if response.status_code in RETRYABLE_STATUS:
                last_response = response
                logger.warning(
                    "scraper http retryable status=%s attempt=%s url=%s",
                    response.status_code,
                    attempt,
                    request.url,
                )
                if attempt == attempts:
                    response.close()
                    raise RetryExhaustedError(
                        f"retry exhausted status={response.status_code}"
                    )
                response.close()
                self._sleep(attempt)
                continue

            return response

        # Defensive; should be unreachable because every branch either returns
        # or raises above.
        if last_error is not None:
            raise RetryExhaustedError(str(last_error)) from last_error
        if last_response is not None:
            return last_response
        raise RetryExhaustedError("unknown retry failure")

    def _sleep(self, attempt: int) -> None:
        if self._backoff <= 0:
            return
        delay = self._backoff * (2 ** (attempt - 1))
        time.sleep(delay)

    def close(self) -> None:
        self._wrapped.close()


def build_client(
    *,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    backoff: float = DEFAULT_BACKOFF,
    headers: dict[str, str] | None = None,
    transport: httpx.BaseTransport | None = None,
) -> httpx.Client:
    base_transport = transport or httpx.HTTPTransport()
    retrying = _RetryTransport(base_transport, retries=retries, backoff=backoff)

    merged_headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    if headers:
        merged_headers.update(headers)

    return httpx.Client(
        transport=retrying,
        timeout=httpx.Timeout(timeout),
        headers=merged_headers,
        follow_redirects=True,
    )
