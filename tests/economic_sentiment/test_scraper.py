"""Tests for Beige Book scraper — PRD-102 CC-1, CC-1-FIX2."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from macro_context_reader.economic_sentiment.scraper import (
    _build_url,
    _cache_path,
    _read_cache,
    _split_pdf_into_sections,
    _write_cache,
    extract_beige_book_content,
    ALL_DISTRICTS,
    DISTRICT_HEADER_PATTERN,
    DISTRICT_URL_SLUGS,
)


# ---------------------------------------------------------------------------
# URL generation
# ---------------------------------------------------------------------------

class TestBuildUrl:
    def test_national_summary(self) -> None:
        url = _build_url(datetime(2026, 1, 15), "national_summary")
        assert url == "https://www.federalreserve.gov/monetarypolicy/beigebook202601-summary.htm"

    def test_district_report(self) -> None:
        url = _build_url(datetime(2026, 1, 15), "district_report", "New York")
        assert url == "https://www.federalreserve.gov/monetarypolicy/beigebook202601-newyork.htm"

    def test_district_st_louis(self) -> None:
        url = _build_url(datetime(2024, 3, 1), "district_report", "St. Louis")
        assert "stlouis" in url

    def test_district_kansas_city(self) -> None:
        url = _build_url(datetime(2024, 3, 1), "district_report", "Kansas City")
        assert "kansascity" in url

    def test_district_san_francisco(self) -> None:
        url = _build_url(datetime(2024, 3, 1), "district_report", "San Francisco")
        assert "sanfrancisco" in url

    def test_raises_on_unknown_district(self) -> None:
        with pytest.raises(ValueError, match="Unknown district"):
            _build_url(datetime(2024, 1, 1), "district_report", "Atlantis")

    def test_raises_on_district_missing_for_report(self) -> None:
        with pytest.raises(ValueError, match="district required"):
            _build_url(datetime(2024, 1, 1), "district_report")

    def test_raises_on_unknown_doc_type(self) -> None:
        with pytest.raises(ValueError, match="Unknown doc_type"):
            _build_url(datetime(2024, 1, 1), "speech")

    def test_all_districts_have_slugs(self) -> None:
        assert set(DISTRICT_URL_SLUGS.keys()) == set(ALL_DISTRICTS)
        assert len(DISTRICT_URL_SLUGS) == 12


# ---------------------------------------------------------------------------
# Content extraction
# ---------------------------------------------------------------------------

class TestExtractBeigeBookContent:
    def _long_content(self, n: int = 100) -> str:
        return "Economic activity expanded moderately across districts. " * n

    def test_extracts_article_div(self) -> None:
        html = f'<html><body><nav>Nav</nav><div id="article"><p>{self._long_content()}</p></div></body></html>'
        result = extract_beige_book_content(html)
        assert "Economic activity" in result
        assert "<html>" not in result
        assert "Nav" not in result

    def test_extracts_col_xs_fallback(self) -> None:
        html = f'<html><body><div class="col-xs-12 col-sm-8"><p>{self._long_content()}</p></div></body></html>'
        result = extract_beige_book_content(html)
        assert "Economic activity" in result

    def test_extracts_main_fallback(self) -> None:
        html = f'<html><body><main><p>{self._long_content()}</p></main></body></html>'
        result = extract_beige_book_content(html)
        assert "Economic activity" in result

    def test_strips_scripts(self) -> None:
        html = f'<html><body><script>alert(1)</script><div id="article"><p>{self._long_content()}</p></div></body></html>'
        result = extract_beige_book_content(html)
        assert "alert" not in result

    def test_rejects_too_short(self) -> None:
        html = '<html><body><div id="article"><p>Short text only.</p></div></body></html>'
        with pytest.raises(ValueError, match="too short"):
            extract_beige_book_content(html)

    def test_rejects_missing_content_div(self) -> None:
        html = "<html><body><p>No content div here.</p></body></html>"
        with pytest.raises(ValueError, match="Cannot locate"):
            extract_beige_book_content(html)

    def test_filters_short_lines(self) -> None:
        html = f'<html><body><div id="article"><p>Hi</p><p>{self._long_content()}</p></div></body></html>'
        result = extract_beige_book_content(html)
        # "Hi" line (2 chars) should be filtered out
        assert "Hi\n" not in result


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

class TestCachePath:
    def test_format(self) -> None:
        path = _cache_path(datetime(2024, 1, 15), "national_summary")
        assert path.name == "20240115_national_summary.txt"
        assert "beige_book" in str(path)

    def test_sanitizes_district_name(self) -> None:
        path = _cache_path(datetime(2024, 3, 1), "stlouis")
        assert "stlouis" in path.name

    def test_parent_dir_created(self, tmp_path, monkeypatch) -> None:
        import macro_context_reader.economic_sentiment.scraper as mod
        monkeypatch.setattr(mod, "CACHE_DIR", tmp_path / "cache" / "deep")
        path = _cache_path(datetime(2024, 1, 1), "test")
        assert path.parent.exists()

    def test_custom_extension(self) -> None:
        path = _cache_path(datetime(2024, 1, 1), "index", ext="html")
        assert path.suffix == ".html"


class TestReadWriteCache:
    def test_write_creates_dirs(self, tmp_path) -> None:
        path = tmp_path / "a" / "b" / "file.txt"
        _write_cache(path, "hello")
        assert path.read_text(encoding="utf-8") == "hello"

    def test_read_returns_none_if_missing(self, tmp_path) -> None:
        path = tmp_path / "nonexistent.txt"
        assert _read_cache(path) is None

    def test_read_returns_content(self, tmp_path) -> None:
        path = tmp_path / "test.txt"
        path.write_text("content", encoding="utf-8")
        assert _read_cache(path) == "content"


# ---------------------------------------------------------------------------
# Archive date extraction
# ---------------------------------------------------------------------------

class TestArchiveDateExtraction:
    def test_extracts_dates_from_mock_html(self) -> None:
        from macro_context_reader.economic_sentiment.scraper import _DATE_HTML_RE

        mock_html = """
        <a href="/monetarypolicy/beigebook201601-summary.htm">January 2016</a>
        <a href="/monetarypolicy/beigebook202003-summary.htm">March 2020</a>
        <a href="/monetarypolicy/beigebook202601-summary.htm">January 2026</a>
        """
        dates = set()
        for m in _DATE_HTML_RE.finditer(mock_html):
            dates.add(m.group(1))

        assert "201601" in dates
        assert "202003" in dates
        assert "202601" in dates

    def test_pdf_pattern(self) -> None:
        from macro_context_reader.economic_sentiment.scraper import _DATE_PDF_RE

        href = "/monetarypolicy/files/BeigeBook_20240117.pdf"
        m = _DATE_PDF_RE.search(href)
        assert m is not None
        assert m.group(1) == "20240117"


# ---------------------------------------------------------------------------
# PDF splitting
# ---------------------------------------------------------------------------

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


class TestDistrictHeaderPattern:
    def test_matches_standard_header(self) -> None:
        assert DISTRICT_HEADER_PATTERN.search("First District -- Boston") is not None

    def test_matches_with_dash(self) -> None:
        assert DISTRICT_HEADER_PATTERN.search("Twelfth District - San Francisco") is not None

    def test_no_match_random_text(self) -> None:
        assert DISTRICT_HEADER_PATTERN.search("GDP growth was moderate.") is None


# ---------------------------------------------------------------------------
# District completeness
# ---------------------------------------------------------------------------

class TestDistrictCompleteness:
    def test_all_12_districts(self) -> None:
        assert len(ALL_DISTRICTS) == 12

    def test_ordinal_mapping_complete(self) -> None:
        from macro_context_reader.economic_sentiment.scraper import _ORDINAL_DISTRICTS
        assert len(_ORDINAL_DISTRICTS) == 12
        assert set(_ORDINAL_DISTRICTS.values()) == set(ALL_DISTRICTS)

    def test_url_slugs_complete(self) -> None:
        assert set(DISTRICT_URL_SLUGS.keys()) == set(ALL_DISTRICTS)


# ---------------------------------------------------------------------------
# Clear cache
# ---------------------------------------------------------------------------

class TestClearCache:
    def test_clear_creates_empty_dir(self, tmp_path, monkeypatch) -> None:
        import macro_context_reader.economic_sentiment.scraper as mod
        cache_dir = tmp_path / "bb_cache"
        cache_dir.mkdir()
        (cache_dir / "old_file.txt").write_text("stale")
        monkeypatch.setattr(mod, "CACHE_DIR", cache_dir)

        mod.clear_cache()

        assert cache_dir.exists()
        assert list(cache_dir.iterdir()) == []
