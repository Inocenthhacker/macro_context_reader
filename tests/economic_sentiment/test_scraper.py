"""Tests for Beige Book scraper — PRD-102 CC-1."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from macro_context_reader.economic_sentiment.scraper import (
    _cache_path,
    _extract_text_from_html,
    _split_pdf_into_sections,
    ALL_DISTRICTS,
    DISTRICT_HEADER_PATTERN,
)


class TestCachePath:
    def test_format(self) -> None:
        path = _cache_path(datetime(2024, 1, 15), "national_summary")
        assert path.name == "20240115_national_summary.txt"
        assert "beige_book" in str(path)

    def test_sanitizes_district_name(self) -> None:
        path = _cache_path(datetime(2024, 3, 1), "St. Louis")
        assert "st__louis" in path.name or "st_louis" in path.name

    def test_parent_dir_exists(self, tmp_path, monkeypatch) -> None:
        import macro_context_reader.economic_sentiment.scraper as mod
        monkeypatch.setattr(mod, "CACHE_DIR", tmp_path / "cache")
        path = _cache_path(datetime(2024, 1, 1), "test")
        assert path.parent.exists()


class TestExtractTextFromHTML:
    def test_strips_scripts(self) -> None:
        html = "<html><body><script>alert(1)</script><div id='article'><p>Economic activity expanded.</p></div></body></html>"
        text = _extract_text_from_html(html)
        assert "alert" not in text
        assert "Economic activity" in text

    def test_extracts_article_div(self) -> None:
        html = "<html><body><nav>Nav</nav><div id='article'><p>GDP grew 3%.</p></div></body></html>"
        text = _extract_text_from_html(html)
        assert "GDP grew" in text
        assert "Nav" not in text

    def test_fallback_to_body(self) -> None:
        html = "<html><body><p>Manufacturing expanded.</p></body></html>"
        text = _extract_text_from_html(html)
        assert "Manufacturing expanded" in text


class TestDistrictHeaderPattern:
    def test_matches_standard_header(self) -> None:
        text = "First District -- Boston"
        assert DISTRICT_HEADER_PATTERN.search(text) is not None

    def test_matches_with_dash(self) -> None:
        text = "Twelfth District - San Francisco"
        assert DISTRICT_HEADER_PATTERN.search(text) is not None

    def test_no_match_random_text(self) -> None:
        text = "GDP growth was moderate across regions."
        assert DISTRICT_HEADER_PATTERN.search(text) is None


class TestSplitPDFIntoSections:
    def test_splits_basic_document(self) -> None:
        text = (
            "National economic activity expanded at a moderate pace across all regions. GDP grew steadily. "
            "Consumer spending was robust across regions. Labor markets remained tight overall.\n\n"
            "First District -- Boston\n"
            "Economic activity in New England expanded moderately during the reporting period. "
            "Manufacturing output increased and employment grew at a steady pace throughout the district. "
            "Contacts reported continued tightness in labor markets.\n\n"
            "Second District -- New York\n"
            "Growth was strong in the New York district during the latest reporting period. "
            "Financial services expanded at a solid pace and tourism activity remained elevated. "
            "Real estate markets showed mixed signals across the district."
        )
        sections = _split_pdf_into_sections(text)
        assert "national_summary" in sections
        assert "Boston" in sections
        assert "New York" in sections
        assert "Manufacturing" in sections["Boston"]

    def test_no_headers_returns_national(self) -> None:
        text = "Overall economic conditions improved. GDP grew 2.5% in Q3."
        sections = _split_pdf_into_sections(text)
        assert "national_summary" in sections
        assert len(sections) == 1

    def test_all_12_districts_recognized(self) -> None:
        """Verify all district names are in ALL_DISTRICTS."""
        assert len(ALL_DISTRICTS) == 12
        assert "St. Louis" in ALL_DISTRICTS
        assert "Kansas City" in ALL_DISTRICTS


class TestDistrictCompleteness:
    def test_ordinal_mapping_complete(self) -> None:
        from macro_context_reader.economic_sentiment.scraper import _ORDINAL_DISTRICTS
        assert len(_ORDINAL_DISTRICTS) == 12
        assert set(_ORDINAL_DISTRICTS.values()) == set(ALL_DISTRICTS)
