"""Tests for Beige Book scraper — PRD-102 CC-1, CC-1-FIX2, CC-1-FIX3, CC-1-FIX4, CC-1-FIX5, CC-1-FIX6."""

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
    detect_url_scheme,
    extract_beige_book_content,
    parse_monolithic_beige_book,
    ALL_DISTRICTS,
    DISTRICT_HEADER_PATTERN,
    DISTRICT_URL_SLUGS,
    MIN_SUPPORTED_YEAR,
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
# Monolithic Beige Book parsing (2017-2023 era)
# ---------------------------------------------------------------------------

class TestParseMonolithicBeigeBook:
    @staticmethod
    def _make_monolithic_html(districts: list[str] | None = None) -> str:
        """Build a synthetic monolithic Beige Book HTML page."""
        if districts is None:
            districts = list(ALL_DISTRICTS)
        paras = "".join(
            f"<p>{'Economic activity expanded moderately across all districts. ' * 5}</p>"
            for _ in range(3)
        )
        national = f"<h3>Summary of Commentary on Current Economic Conditions</h3>{paras}"
        district_sections = ""
        for d in districts:
            district_text = "".join(
                f"<p>The {d} district reported moderate growth in activity. "
                f"Manufacturing expanded and employment rose steadily. "
                f"Consumer spending remained solid throughout the period.</p>"
                for _ in range(3)
            )
            district_sections += f"<h3>{d}</h3>{district_text}"
        return f'<html><body><div id="article">{national}{district_sections}</div></body></html>'

    def test_extracts_all_12_districts(self) -> None:
        html = self._make_monolithic_html()
        sections = parse_monolithic_beige_book(html)
        assert "national_summary" in sections
        for district in ALL_DISTRICTS:
            assert district in sections, f"Missing district: {district}"
            assert len(sections[district]) > 100

    def test_national_summary_before_first_district(self) -> None:
        html = self._make_monolithic_html()
        sections = parse_monolithic_beige_book(html)
        assert "Economic activity" in sections["national_summary"]

    def test_fails_on_too_few_districts(self) -> None:
        html = self._make_monolithic_html(districts=["Boston", "New York"])
        with pytest.raises(ValueError, match="districts extracted"):
            parse_monolithic_beige_book(html)

    def test_fails_on_no_content_div(self) -> None:
        html = "<html><body><p>no article div</p></body></html>"
        with pytest.raises(ValueError, match="Cannot locate"):
            parse_monolithic_beige_book(html)

    def test_handles_federal_reserve_bank_of_prefix(self) -> None:
        """Headers like 'Federal Reserve Bank of Boston' should also match."""
        paras = "".join(
            f"<p>{'Economic activity expanded moderately across all districts. ' * 5}</p>"
            for _ in range(3)
        )
        national = f"<h3>Summary</h3>{paras}"
        district_sections = ""
        for d in ALL_DISTRICTS:
            district_text = "".join(
                f"<p>The {d} district reported moderate growth over the period. "
                f"Manufacturing sector expanded and employment rose steadily. "
                f"Consumer spending remained solid throughout the reporting period.</p>"
                for _ in range(3)
            )
            district_sections += f"<h3>Federal Reserve Bank of {d}</h3>{district_text}"
        html = f'<html><body><div id="article">{national}{district_sections}</div></body></html>'
        sections = parse_monolithic_beige_book(html)
        for district in ALL_DISTRICTS:
            assert district in sections, f"Missing: {district}"


# ---------------------------------------------------------------------------
# MIN_SUPPORTED_YEAR enforcement
# ---------------------------------------------------------------------------

class TestMinSupportedYear:
    def test_min_supported_year_is_2017(self) -> None:
        assert MIN_SUPPORTED_YEAR == 2017

    def test_discover_publications_rejects_pre_2017(self) -> None:
        from macro_context_reader.economic_sentiment.scraper import (
            _get_session, discover_publications,
        )
        session = _get_session()
        with pytest.raises(RuntimeError, match="MIN_SUPPORTED_YEAR"):
            discover_publications(session, start_year=2016)

    def test_discover_publications_rejects_2011(self) -> None:
        from macro_context_reader.economic_sentiment.scraper import (
            _get_session, discover_publications,
        )
        session = _get_session()
        with pytest.raises(RuntimeError, match="MIN_SUPPORTED_YEAR"):
            discover_publications(session, start_year=2011)

    def test_discover_publications_accepts_2017(self) -> None:
        """2017 should not raise (boundary value)."""
        from macro_context_reader.economic_sentiment.scraper import discover_publications
        # Just verify it doesn't raise — actual network call skipped via mock
        from unittest.mock import patch
        with patch(
            "macro_context_reader.economic_sentiment.scraper._request_with_retry",
            side_effect=Exception("mocked — skip network"),
        ):
            # Should not raise RuntimeError for start_year validation
            # Will fail on network, but that's fine — we're testing the guard
            try:
                discover_publications(MagicMock(), start_year=2017)
            except RuntimeError as e:
                if "MIN_SUPPORTED_YEAR" in str(e):
                    raise  # re-raise if it's the year guard — that's a bug
                # Other RuntimeErrors (network) are expected


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
def test_discovery_2017_onwards_real_fed_archive() -> None:
    """Live test: 2017 should have exactly 8 publications from real Fed archive."""
    from macro_context_reader.economic_sentiment.scraper import (
        _get_session, discover_publications,
    )
    session = _get_session()
    pubs = discover_publications(session, start_year=2017, end_date=datetime(2017, 12, 31))
    pubs_2017 = [p for p in pubs if p["publication_date"].year == 2017]
    assert len(pubs_2017) == 8, (
        f"2017 should have 8 publications, got {len(pubs_2017)}: "
        f"{[p['yyyy_nn'] for p in pubs_2017]}"
    )


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


@pytest.mark.integration
def test_detect_url_scheme_2024_is_fragmented() -> None:
    """Empirical: 2024 publications use fragmented URL scheme."""
    from macro_context_reader.economic_sentiment.scraper import _get_session
    session = _get_session()
    scheme = detect_url_scheme("202401", session)
    assert scheme == "fragmented", f"Expected fragmented for 202401, got {scheme}"


@pytest.mark.integration
def test_detect_url_scheme_2019_is_monolithic() -> None:
    """Empirical: 2019 publications use monolithic URL scheme."""
    from macro_context_reader.economic_sentiment.scraper import _get_session
    session = _get_session()
    scheme = detect_url_scheme("201901", session)
    assert scheme == "monolithic", f"Expected monolithic for 201901, got {scheme}"


@pytest.mark.integration
def test_parse_monolithic_extracts_all_districts_real_2019() -> None:
    """Integration: fetch real 2019-01 Beige Book and verify all 12 districts parsed."""
    import requests as req
    url = "https://www.federalreserve.gov/monetarypolicy/beigebook201901.htm"
    resp = req.get(url, timeout=30, headers={"User-Agent": "MacroContextReader/1.0"})
    resp.raise_for_status()
    sections = parse_monolithic_beige_book(resp.text)

    assert "national_summary" in sections
    assert len(sections["national_summary"]) > 500, (
        f"National summary too short: {len(sections['national_summary'])} chars"
    )

    for district in ALL_DISTRICTS:
        assert district in sections, f"Missing district: {district}"
        assert len(sections[district]) > 200, (
            f"District {district} text too short: {len(sections[district])} chars"
        )
