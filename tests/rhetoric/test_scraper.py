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
