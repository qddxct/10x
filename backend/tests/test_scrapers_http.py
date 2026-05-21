from __future__ import annotations

import httpx
import pytest
from app.scrapers.http import (
    DEFAULT_USER_AGENT,
    RetryExhaustedError,
    build_client,
)


def _mock(responses: list[httpx.Response] | list[Exception]) -> httpx.MockTransport:
    index = {"i": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        i = index["i"]
        index["i"] += 1
        item = responses[i]
        if isinstance(item, Exception):
            raise item
        return item

    return httpx.MockTransport(handler)


def test_default_headers_include_user_agent():
    transport = _mock([httpx.Response(200, json={"ok": True})])
    with build_client(transport=transport, retries=0, backoff=0) as client:
        resp = client.get("http://example.com/x")
    assert resp.status_code == 200
    assert resp.request.headers.get("User-Agent") == DEFAULT_USER_AGENT


def test_custom_timeout_is_applied():
    transport = _mock([httpx.Response(200, text="ok")])
    with build_client(timeout=3.5, transport=transport, retries=0, backoff=0) as client:
        assert client.timeout.read == 3.5


def test_retry_on_5xx_then_success():
    transport = _mock(
        [
            httpx.Response(503),
            httpx.Response(502),
            httpx.Response(200, text="ok"),
        ]
    )
    with build_client(transport=transport, retries=3, backoff=0) as client:
        resp = client.get("http://example.com/x")
    assert resp.status_code == 200


def test_retry_on_connect_error():
    transport = _mock(
        [
            httpx.ConnectError("boom"),
            httpx.Response(200, text="ok"),
        ]
    )
    with build_client(transport=transport, retries=2, backoff=0) as client:
        resp = client.get("http://example.com/x")
    assert resp.status_code == 200


def test_no_retry_on_4xx():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(404, text="nope")

    transport = httpx.MockTransport(handler)
    with build_client(transport=transport, retries=3, backoff=0) as client:
        resp = client.get("http://example.com/x")
    assert resp.status_code == 404
    assert calls["n"] == 1


def test_retry_exhausted_raises():
    transport = _mock([httpx.Response(500)] * 4)
    with (
        build_client(transport=transport, retries=3, backoff=0) as client,
        pytest.raises(RetryExhaustedError),
    ):
        client.get("http://example.com/x")
