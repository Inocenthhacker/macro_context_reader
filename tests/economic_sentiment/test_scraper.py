"""Tests for Beige Book scraper — PRD-102 CC-1, CC-1-FIX2, CC-1-FIX3, CC-1-FIX4."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from macro_context_reader.economic_sentiment.scraper import (
    _cache_path,
    _district_url,
    _extract_publications_from_year_page,
    _main_page_url,
    _parse_date_from_context,
    _read_cache,
    _split_pdf_into_sections,
    _summary_url,
    _write_cache,
    extract_beige_book_content,
    ALL_DISTRICTS,
    DISTRICT_HEADER_PATTERN,
    DISTRICT_URL_SLUGS,
)


# ---------------------------------------------------------------------------
# URL construction from yyyy_nn
# ---------------------------------------------------------------------------

class TestUrlConstruction:
    def test_summary_url(self) -> None:
        assert _summary_url("202601") == (
            "https://www.federalreserve.gov/monetarypolicy/beigebook202601-summary.htm"
        )

    def test_district_url_new_york(self) -> None:
        url = _district_url("202601", "New York")
        assert url == "https://www.federalreserve.gov/monetarypolicy/beigebook202601-new-york.htm"

    def test_district_url_st_louis(self) -> None:
        assert "st-louis" in _district_url("202601", "St. Louis")

    def test_district_url_kansas_city(self) -> None:
        assert "kansas-city" in _district_url("202601", "Kansas City")

    def test_district_url_san_francisco(self) -> None:
        assert "san-francisco" in _district_url("202601", "San Francisco")

    def test_district_url_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown district"):
            _district_url("202601", "Atlantis")

    def test_main_page_url(self) -> None:
        assert _main_page_url("201801") == (
            "https://www.federalreserve.gov/monetarypolicy/beigebook201801.htm"
        )

    def test_all_districts_have_slugs(self) -> None:
        assert set(DISTRICT_URL_SLUGS.keys()) == set(ALL_DISTRICTS)
        assert len(DISTRICT_URL_SLUGS) == 12

    def test_yyyy_nn_not_calendar_month(self) -> None:
        """Verify URLs use yyyy_nn code, NOT calendar month.

        March 2026 = beigebook202602, NOT beigebook202603.
        This is the core bug this fix addresses.
        """
        url = _summary_url("202602")
        assert "beigebook202602-summary" in url
        # There is no way to derive "202602" from a March date — it must be discovered


# ---------------------------------------------------------------------------
# Publication discovery from year pages
# ---------------------------------------------------------------------------

class TestExtractPublicationsFromYearPage:
    def test_extracts_summary_format(self) -> None:
        """2024+ format with -summary suffix."""
        html = """
        <html><body><div id="article">
        <p>January 14:
        <a href="/monetarypolicy/beigebook202601-summary.htm">HTML</a> |
        <a href="/monetarypolicy/files/BeigeBook_20260114.pdf">PDF</a></p>
        <p>March 4:
        <a href="/monetarypolicy/beigebook202602-summary.htm">HTML</a> |
        <a href="/monetarypolicy/files/BeigeBook_20260304.pdf">PDF</a></p>
        </div></body></html>
        """
        pubs = _extract_publications_from_year_page(html, 2026)
        assert len(pubs) == 2
        assert pubs[0]["yyyy_nn"] == "202601"
        assert pubs[0]["has_summary"] is True
        assert pubs[1]["yyyy_nn"] == "202602"
        assert pubs[1]["has_summary"] is True

    def test_extracts_old_format(self) -> None:
        """Pre-2024 format without -summary suffix."""
        html = """
        <html><body><div id="article">
        <p>January 17:
        <a href="/monetarypolicy/beigebook201801.htm">HTML</a> |
        <a href="/monetarypolicy/files/BeigeBook_20180117.pdf">PDF</a></p>
        <p>March 7:
        <a href="/monetarypolicy/beigebook201803.htm">HTML</a></p>
        </div></body></html>
        """
        pubs = _extract_publications_from_year_page(html, 2018)
        assert len(pubs) == 2
        assert pubs[0]["yyyy_nn"] == "201801"
        assert pubs[0]["has_summary"] is False
        assert pubs[1]["yyyy_nn"] == "201803"

    def test_pdf_date_overrides_text_date(self) -> None:
        """PDF link provides exact YYYYMMDD date."""
        html = """
        <html><body>
        <p>January 14:
        <a href="/monetarypolicy/beigebook202601-summary.htm">HTML</a> |
        <a href="/monetarypolicy/files/BeigeBook_20260114.pdf">PDF</a></p>
        </body></html>
        """
        pubs = _extract_publications_from_year_page(html, 2026)
        assert len(pubs) == 1
        assert pubs[0]["publication_date"] == datetime(2026, 1, 14)

    def test_ignores_year_page_links(self) -> None:
        """Year page links (beigebook2020.htm) should not be extracted as publications."""
        html = """
        <html><body>
        <a href="/monetarypolicy/beigebook2020.htm">2020</a>
        <a href="/monetarypolicy/beigebook202001.htm">January</a>
        </body></html>
        """
        pubs = _extract_publications_from_year_page(html, 2020)
        assert len(pubs) == 1
        assert pubs[0]["yyyy_nn"] == "202001"

    def test_empty_html_returns_empty(self) -> None:
        pubs = _extract_publications_from_year_page("<html></html>", 2020)
        assert pubs == []


class TestParseDateFromContext:
    def test_parses_month_day(self) -> None:
        dt = _parse_date_from_context("January 14: HTML | PDF", 2026)
        assert dt == datetime(2026, 1, 14)

    def test_parses_march(self) -> None:
        dt = _parse_date_from_context("March 4", 2026)
        assert dt == datetime(2026, 3, 4)

    def test_returns_none_on_garbage(self) -> None:
        assert _parse_date_from_context("no date here", 2026) is None


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
        assert "Nav" not in result

    def test_extracts_col_xs_fallback(self) -> None:
        html = f'<html><body><div class="col-xs-12 col-sm-8"><p>{self._long_content()}</p></div></body></html>'
        result = extract_beige_book_content(html)
        assert "Economic activity" in result

    def test_extracts_main_fallback(self) -> None:
        html = f'<html><body><main><p>{self._long_content()}</p></main></body></html>'
        assert "Economic activity" in extract_beige_book_content(html)

    def test_strips_scripts(self) -> None:
        html = f'<html><body><script>alert(1)</script><div id="article"><p>{self._long_content()}</p></div></body></html>'
        assert "alert" not in extract_beige_book_content(html)

    def test_rejects_too_short(self) -> None:
        html = '<html><body><div id="article"><p>Short.</p></div></body></html>'
        with pytest.raises(ValueError, match="too short"):
            extract_beige_book_content(html)

    def test_rejects_missing_content_div(self) -> None:
        html = "<html><body><p>No content div.</p></body></html>"
        with pytest.raises(ValueError, match="Cannot locate"):
            extract_beige_book_content(html)


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

class TestCachePath:
    def test_format(self) -> None:
        path = _cache_path(datetime(2024, 1, 15), "national_summary")
        assert path.name == "20240115_national_summary.txt"
        assert "beige_book" in str(path)

    def test_parent_dir_created(self, tmp_path, monkeypatch) -> None:
        import macro_context_reader.economic_sentiment.scraper as mod
        monkeypatch.setattr(mod, "CACHE_DIR", tmp_path / "cache" / "deep")
        path = _cache_path(datetime(2024, 1, 1), "test")
        assert path.parent.exists()

    def test_custom_extension(self) -> None:
        assert _cache_path(datetime(2024, 1, 1), "idx", ext="html").suffix == ".html"


class TestReadWriteCache:
    def test_write_creates_dirs(self, tmp_path) -> None:
        path = tmp_path / "a" / "b" / "file.txt"
        _write_cache(path, "hello")
        assert path.read_text(encoding="utf-8") == "hello"

    def test_read_returns_none_if_missing(self, tmp_path) -> None:
        assert _read_cache(tmp_path / "nope.txt") is None

    def test_read_returns_content(self, tmp_path) -> None:
        p = tmp_path / "test.txt"
        p.write_text("data", encoding="utf-8")
        assert _read_cache(p) == "data"


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

    def test_no_headers_returns_national(self) -> None:
        sections = _split_pdf_into_sections("Overall economic conditions improved. GDP grew 2.5%.")
        assert "national_summary" in sections
        assert len(sections) == 1


class TestDistrictHeaderPattern:
    def test_matches_standard(self) -> None:
        assert DISTRICT_HEADER_PATTERN.search("First District -- Boston") is not None

    def test_matches_with_dash(self) -> None:
        assert DISTRICT_HEADER_PATTERN.search("Twelfth District - San Francisco") is not None

    def test_no_match_random(self) -> None:
        assert DISTRICT_HEADER_PATTERN.search("GDP growth was moderate.") is None


# ---------------------------------------------------------------------------
# District completeness
# ---------------------------------------------------------------------------

class TestDistrictCompleteness:
    def test_all_12(self) -> None:
        assert len(ALL_DISTRICTS) == 12

    def test_ordinal_mapping(self) -> None:
        from macro_context_reader.economic_sentiment.scraper import _ORDINAL_DISTRICTS
        assert len(_ORDINAL_DISTRICTS) == 12
        assert set(_ORDINAL_DISTRICTS.values()) == set(ALL_DISTRICTS)

    def test_url_slugs_complete(self) -> None:
        assert set(DISTRICT_URL_SLUGS.keys()) == set(ALL_DISTRICTS)


# ---------------------------------------------------------------------------
# Clear cache
# ---------------------------------------------------------------------------

class TestClearCache:
    def test_creates_empty_dir(self, tmp_path, monkeypatch) -> None:
        import macro_context_reader.economic_sentiment.scraper as mod
        d = tmp_path / "bb_cache"
        d.mkdir()
        (d / "old.txt").write_text("stale")
        monkeypatch.setattr(mod, "CACHE_DIR", d)
        mod.clear_cache()
        assert d.exists()
        assert list(d.iterdir()) == []


# ---------------------------------------------------------------------------
# Integration tests — require network access
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_discovery_finds_2026_publications() -> None:
    """Empirical: 2026 has at least 2 publications (Jan, Mar)."""
    from macro_context_reader.economic_sentiment.scraper import (
        _get_session, discover_publications,
    )
    session = _get_session()
    pubs = discover_publications(session, start_year=2026)
    assert len(pubs) >= 2, f"Expected >=2 publications for 2026, found {len(pubs)}"
    codes = [p["yyyy_nn"] for p in pubs]
    assert "202601" in codes, f"202601 not found in {codes}"
    assert "202602" in codes, f"202602 not found in {codes}"


@pytest.mark.integration
def test_discovery_covers_2020() -> None:
    """Empirical: 2020 should have all 8 publications from archive."""
    from macro_context_reader.economic_sentiment.scraper import (
        _get_session, discover_publications,
    )
    session = _get_session()
    pubs = discover_publications(session, start_year=2020, end_date=datetime(2020, 12, 31))
    assert len(pubs) == 8, f"Expected 8 publications for 2020, found {len(pubs)}: {[p['yyyy_nn'] for p in pubs]}"


@pytest.mark.integration
def test_all_district_urls_valid_empirically() -> None:
    """Validate all 12 district slugs by HEAD request.

    Uses January 2026 (yyyy_nn=202601) confirmed from archive.
    """
    import requests as req
    failed = []
    for district, slug in DISTRICT_URL_SLUGS.items():
        url = _district_url("202601", district)
        resp = req.head(url, timeout=10, allow_redirects=True)
        if resp.status_code != 200:
            failed.append((district, url, resp.status_code))
    assert not failed, f"District URLs returned non-200: {failed}"


@pytest.mark.integration
def test_national_summary_url_valid_empirically() -> None:
    """Validate national summary URL returns HTTP 200."""
    import requests as req
    url = _summary_url("202601")
    resp = req.head(url, timeout=10, allow_redirects=True)
    assert resp.status_code == 200, f"Summary URL returned {resp.status_code}: {url}"
