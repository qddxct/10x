from __future__ import annotations

import pytest
from app.scrapers.base import ScrapeError, Scraper, ScraperOutcome


class _FakeScraper(Scraper):
    name = "fake"
    source = "sporttery"

    def __init__(self, *, fetch_raises=None, parse_raises=None, rows=None):
        self._fetch_raises = fetch_raises
        self._parse_raises = parse_raises
        self._rows = rows or []

    def fetch(self) -> str:
        if self._fetch_raises:
            raise self._fetch_raises
        return "<html/>"

    def parse(self, raw: str) -> list[dict]:
        if self._parse_raises:
            raise self._parse_raises
        return self._rows

    def persist(self, rows: list[dict]) -> int:
        return len(rows)


def test_run_success_returns_count():
    s = _FakeScraper(rows=[{"a": 1}, {"a": 2}, {"a": 3}])
    outcome = s.run()
    assert outcome == ScraperOutcome(status="success", records=3, error=None)


def test_run_success_with_zero_rows_is_partial():
    s = _FakeScraper(rows=[])
    outcome = s.run()
    assert outcome.status == "partial"
    assert outcome.records == 0


def test_run_fetch_failure_returns_failed():
    s = _FakeScraper(fetch_raises=RuntimeError("boom"))
    outcome = s.run()
    assert outcome.status == "failed"
    assert outcome.records == 0
    assert "boom" in (outcome.error or "")


def test_run_parse_failure_returns_failed():
    s = _FakeScraper(parse_raises=ValueError("bad html"))
    outcome = s.run()
    assert outcome.status == "failed"
    assert "bad html" in (outcome.error or "")


def test_scrape_error_message_includes_url_and_status():
    err = ScrapeError("http://example.com/x", 502, "bad gateway")
    msg = str(err)
    assert "http://example.com/x" in msg
    assert "502" in msg
    assert "bad gateway" in msg


def test_source_must_be_valid():
    class BadSource(_FakeScraper):
        source = "invalid"  # type: ignore[assignment]

    with pytest.raises(ValueError):
        BadSource().run()
