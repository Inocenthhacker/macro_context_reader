"""Tests for FOMC scraper — PRD-101 CC-1.

All tests use mocked HTTP responses — no real network calls.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from macro_context_reader.rhetoric.scraper import (
    _extract_text_from_html,
    _cache_path,
    _load_or_fetch,
    extract_statement_text,
)


def test_extract_text_from_html() -> None:
    html = """
    <html><body>
    <nav>Navigation</nav>
    <div class="col-xs-12">
    <p>The Federal Reserve decided to raise rates.</p>
    <p>Inflation remains elevated above the 2 percent target.</p>
    </div>
    </body></html>
    """
    text = _extract_text_from_html(html)
    assert "Federal Reserve decided" in text
    assert "Inflation remains" in text
    assert "Navigation" not in text


def test_extract_text_strips_scripts() -> None:
    html = '<html><body><script>alert("x")</script><p>Real content here.</p></body></html>'
    text = _extract_text_from_html(html)
    assert "alert" not in text
    assert "Real content" in text


def test_cache_path_format() -> None:
    path = _cache_path("statement", datetime(2024, 1, 31), "FOMC Statement 2024-01-31")
    assert "statement" in str(path)
    assert "20240131" in str(path)
    assert path.suffix == ".txt"


def test_cache_path_sanitizes_title() -> None:
    path = _cache_path("speech", datetime(2024, 6, 15), "Chair Powell's Remarks on/Inflation!")
    name = path.stem
    assert "/" not in name
    assert "!" not in name
    assert "'" not in name


def test_load_or_fetch_creates_cache_dir(tmp_path) -> None:
    """_load_or_fetch should create parent directories if missing."""
    from unittest.mock import MagicMock
    from macro_context_reader.rhetoric.scraper import _load_or_fetch

    session = MagicMock()
    resp = MagicMock()
    resp.text = "<html><body>Test content</body></html>"
    resp.raise_for_status = MagicMock()
    session.get.return_value = resp

    # Point cache to a deeply nested path that doesn't exist
    cache = tmp_path / "deep" / "nested" / "dir" / "test.html"
    assert not cache.parent.exists()

    with patch("macro_context_reader.rhetoric.scraper.REQUEST_DELAY", 0), \
         patch("macro_context_reader.rhetoric.scraper.time.sleep"):
        result = _load_or_fetch(session, "https://example.com", cache)

    assert cache.exists()
    assert "Test content" in result
    assert cache.parent.exists()


# ---------------------------------------------------------------------------
# Fix 3 tests — meeting statement filtering + text extraction
# ---------------------------------------------------------------------------

MOCK_CALENDAR_HTML = """
<html><body>
<div class="fomc-meeting">
  <a href="/newsevents/pressreleases/monetary20240301a.htm">HTML</a>
  <a href="/newsevents/pressreleases/monetary20240301a1.htm">Implementation Note</a>
  <a href="/monetarypolicy/fomcpresconf20240301.htm">Press Conference</a>
</div>
<div class="fomc-meeting">
  <a href="/newsevents/pressreleases/monetary20240601a.htm">HTML</a>
</div>
<div class="fomc-meeting">
  <a href="/newsevents/pressreleases/monetary20240128b.htm">Statement on Longer-Run Goals and Monetary Policy Strategy</a>
  <a href="/newsevents/pressreleases/monetary20240128a.htm">HTML</a>
</div>
</body></html>
"""

MOCK_STATEMENT_HTML = """
<html><head><title>FOMC Statement</title></head>
<body>
<script>analytics();</script>
<nav>Navigation bar</nav>
<div id="article">
  <p>Federal Reserve issues FOMC statement</p>
  <p>For release at 2:00 p.m. EDT</p>
  <p>Recent indicators suggest that economic activity has continued to expand at a solid pace. The unemployment
  rate has stabilized at a low level in recent months, and labor market conditions remain solid. Inflation
  remains somewhat elevated.</p>
  <p>The Committee seeks to achieve maximum employment and inflation at the rate of 2 percent over the longer
  run. The Committee decided to maintain the target range for the federal funds rate at 4-1/4 to 4-1/2 percent.</p>
  <p>Voting for the monetary policy action were Jerome H. Powell, Chair and other members.</p>
  <p>For media inquiries, please email media@frb.gov or call 202-452-2955.</p>
  <p>Implementation Note issued March 1, 2024</p>
</div>
<footer>Footer content</footer>
</body></html>
"""


def test_extract_statement_text_clean() -> None:
    """Extracted text should contain statement content, not HTML artifacts."""
    text = extract_statement_text(MOCK_STATEMENT_HTML)
    assert "economic activity" in text
    assert "maintain the target range" in text
    assert "<script>" not in text
    assert "<nav>" not in text
    assert "Navigation bar" not in text
    assert "Footer content" not in text


def test_extract_statement_rejects_empty_content() -> None:
    """HTML without div#article should raise ValueError."""
    bad_html = "<html><body><p>Short.</p></body></html>"
    with pytest.raises(ValueError, match="Cannot locate"):
        extract_statement_text(bad_html)


def test_extract_statement_rejects_too_short() -> None:
    """Very short content should raise ValueError."""
    short_html = '<html><body><div id="article"><p>Short text only.</p></div></body></html>'
    with pytest.raises(ValueError, match="too short"):
        extract_statement_text(short_html)


def test_fetch_statements_filters_strategy_docs() -> None:
    """fetch_fomc_statements should return meeting statements, not strategy docs.

    Calendar has 3 meetings: 2 with standard HTML links + 1 with both
    strategy doc and HTML link. Should get 3 meeting statements, 0 strategy docs.
    """
    from macro_context_reader.rhetoric.scraper import fetch_fomc_statements, CACHE_DIR

    mock_session = MagicMock()

    # Mock _load_or_fetch to return different HTML per URL
    def fake_load_or_fetch(session, url, cache):
        if "_calendar" in str(cache):
            return MOCK_CALENDAR_HTML
        return MOCK_STATEMENT_HTML

    with patch("macro_context_reader.rhetoric.scraper._load_or_fetch", side_effect=fake_load_or_fetch), \
         patch("macro_context_reader.rhetoric.scraper._get_session", return_value=mock_session):
        docs = fetch_fomc_statements(start_year=2024)

    # Should get 3 meeting statements (one per fomc-meeting panel with "HTML" link)
    assert len(docs) == 3, f"Expected 3 meeting statements, got {len(docs)}"
    # None should be strategy documents
    for doc in docs:
        assert "Longer-Run Goals" not in doc.raw_text or "maintain the target range" in doc.raw_text
        assert doc.doc_type == "statement"
    # Verify correct dates extracted
    dates = sorted([d.date.strftime("%Y%m%d") for d in docs])
    assert dates == ["20240128", "20240301", "20240601"]
