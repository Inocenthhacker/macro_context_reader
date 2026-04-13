"""Tests for Beige Book PDF scraper — PRD-102 CC-1-FIX9."""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from macro_context_reader.economic_sentiment.scraper import (
    _extract_publications_from_year_page,
    _parse_date_from_context,
    _pdf_url,
    _read_cache,
    _write_cache,
    extract_text_from_pdf,
    split_pdf_into_sections,
    ALL_DISTRICTS,
    MIN_SUPPORTED_YEAR,
)


# ---------------------------------------------------------------------------
# PDF URL construction
# ---------------------------------------------------------------------------

class TestPdfUrl:
    def test_standard_format(self) -> None:
        assert _pdf_url("20260114") == (
            "https://www.federalreserve.gov/monetarypolicy/files/BeigeBook_20260114.pdf"
        )

    def test_2019_format(self) -> None:
        url = _pdf_url("20190306")
        assert "BeigeBook_20190306.pdf" in url
        assert url.startswith("https://")


# ---------------------------------------------------------------------------
# Publication discovery from year pages
# ---------------------------------------------------------------------------

class TestExtractPublicationsFromYearPage:
    def test_extracts_summary_format_with_pdf(self) -> None:
        """2024+ archive page with summary + PDF links."""
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
        assert pubs[0]["publication_date"] == datetime(2026, 1, 14)
        assert "BeigeBook_20260114.pdf" in pubs[0]["pdf_url"]

    def test_extracts_old_format_with_pdf(self) -> None:
        """Pre-2024 format with main page + PDF links."""
        html = """
        <html><body><div id="article">
        <p>January 17:
        <a href="/monetarypolicy/beigebook201801.htm">HTML</a> |
        <a href="/monetarypolicy/files/BeigeBook_20180117.pdf">PDF</a></p>
        </div></body></html>
        """
        pubs = _extract_publications_from_year_page(html, 2018)
        assert len(pubs) == 1
        assert pubs[0]["yyyy_nn"] == "201801"
        assert "BeigeBook_20180117.pdf" in pubs[0]["pdf_url"]

    def test_constructs_pdf_url_when_no_pdf_link(self) -> None:
        """If only HTML link exists, PDF URL is constructed from date."""
        html = """
        <html><body>
        <p>March 7:
        <a href="/monetarypolicy/beigebook201803.htm">HTML</a></p>
        </body></html>
        """
        pubs = _extract_publications_from_year_page(html, 2018)
        assert len(pubs) == 1
        # PDF URL constructed from parsed date (March 7 2018)
        assert "BeigeBook_" in pubs[0]["pdf_url"]
        assert ".pdf" in pubs[0]["pdf_url"]

    def test_pdf_only_discovery(self) -> None:
        """Pages with only PDF links (no HTML) should still discover publications."""
        html = """
        <html><body>
        <p>January 14:
        <a href="/monetarypolicy/files/BeigeBook_20200115.pdf">PDF</a></p>
        </body></html>
        """
        pubs = _extract_publications_from_year_page(html, 2020)
        assert len(pubs) == 1
        assert pubs[0]["publication_date"] == datetime(2020, 1, 15)

    def test_ignores_year_page_links(self) -> None:
        """Year page links (beigebook2020.htm) should not be extracted."""
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
# PDF section splitting
# ---------------------------------------------------------------------------

class TestSplitPdfIntoSections:
    @staticmethod
    def _make_pdf_text(districts: list[str] | None = None) -> str:
        """Build synthetic PDF text matching real Beige Book structure."""
        if districts is None:
            districts = list(ALL_DISTRICTS)

        national = (
            "Summary of Commentary on Current Economic Conditions\n"
            "by Federal Reserve District\n\n"
            + "Economic activity expanded at a moderate pace across most Federal "
            "Reserve Districts since the previous report. Consumer spending grew "
            "modestly, while manufacturing output was mixed. Employment continued "
            "to expand at a modest pace, and wage pressures remained elevated. "
            "Prices increased at a moderate rate across most Districts.\n" * 10
        )

        district_texts = ""
        for d in districts:
            body_para = (
                f"The {d} district reported moderate growth in economic activity. "
                f"Manufacturing expanded and employment rose steadily. "
                f"Consumer spending remained solid throughout the reporting period. "
                f"Contacts noted ongoing tightness in labor markets.\n"
            )
            emp_para = (
                f"Employment grew at a modest pace in the {d} district. "
                f"Firms reported difficulty filling open positions.\n"
            )
            price_para = (
                f"Prices increased at a moderate rate in the {d} district.\n"
            )
            # pdfplumber renders headers as two lines:
            # "Federal Reserve Bank of\n{name}\n"
            section = (
                f"Federal Reserve Bank of\n{d}\n"
                f"Summary of Economic Activity\n"
                + body_para * 10
                + "\nEmployment and Wages\n"
                + emp_para * 5
                + "\nPrices\n"
                + price_para * 5
            )
            district_texts += section

        return national + district_texts

    def test_extracts_all_12_districts(self) -> None:
        text = self._make_pdf_text()
        sections = split_pdf_into_sections(text)
        assert "national_summary" in sections
        for district in ALL_DISTRICTS:
            assert district in sections, f"Missing: {district}"
            assert len(sections[district]) > 500

    def test_national_summary_before_districts(self) -> None:
        text = self._make_pdf_text()
        sections = split_pdf_into_sections(text)
        assert "Economic activity" in sections["national_summary"]
        # National summary should NOT contain district-specific content
        assert "Boston district reported" not in sections["national_summary"]

    def test_district_content_not_mixed(self) -> None:
        """Each district section should primarily contain its own name."""
        text = self._make_pdf_text()
        sections = split_pdf_into_sections(text)
        # Boston section should mention Boston, not primarily New York
        assert "Boston" in sections["Boston"]
        assert "San Francisco" in sections["San Francisco"]

    def test_fails_on_missing_districts(self) -> None:
        text = (
            "National summary text here.\n" * 50
            + "Federal Reserve Bank of Boston\n"
            + "Boston content here.\n" * 50
        )
        with pytest.raises(ValueError, match="Districts not found"):
            split_pdf_into_sections(text)

    def test_handles_st_louis_dot_variation(self) -> None:
        """St. Louis with or without period should match."""
        text = self._make_pdf_text()
        # Default text uses "St. Louis" — verify it works
        sections = split_pdf_into_sections(text)
        assert "St. Louis" in sections

    def test_fails_on_short_district(self) -> None:
        """Districts with <500 chars should fail validation."""
        text = self._make_pdf_text()
        # Truncate Dallas section by inserting San Francisco header early
        text = text.replace(
            "Federal Reserve Bank of\nSan Francisco\n",
            "Federal Reserve Bank of\nDallas\nShort.\n"
            "Federal Reserve Bank of\nSan Francisco\n",
        )
        # This creates a duplicate Dallas — ordering check should catch it
        with pytest.raises(ValueError):
            split_pdf_into_sections(text)


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

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
# District completeness
# ---------------------------------------------------------------------------

class TestDistrictCompleteness:
    def test_all_12(self) -> None:
        assert len(ALL_DISTRICTS) == 12

    def test_canonical_order(self) -> None:
        assert ALL_DISTRICTS[0] == "Boston"
        assert ALL_DISTRICTS[-1] == "San Francisco"


# ---------------------------------------------------------------------------
# MIN_SUPPORTED_YEAR enforcement
# ---------------------------------------------------------------------------

class TestMinSupportedYear:
    def test_min_supported_year_is_2011(self) -> None:
        assert MIN_SUPPORTED_YEAR == 2011

    def test_discover_publications_rejects_pre_2011(self) -> None:
        from macro_context_reader.economic_sentiment.scraper import (
            _get_session, discover_publications,
        )
        session = _get_session()
        with pytest.raises(RuntimeError, match="MIN_SUPPORTED_YEAR"):
            discover_publications(session, start_year=2010)

    def test_discover_publications_accepts_2011(self) -> None:
        """2011 should not raise (boundary value)."""
        from macro_context_reader.economic_sentiment.scraper import discover_publications
        from unittest.mock import patch
        with patch(
            "macro_context_reader.economic_sentiment.scraper._request_with_retry",
            side_effect=Exception("mocked"),
        ):
            try:
                discover_publications(MagicMock(), start_year=2011)
            except RuntimeError as e:
                if "MIN_SUPPORTED_YEAR" in str(e):
                    raise


# ---------------------------------------------------------------------------
# PDF header regex
# ---------------------------------------------------------------------------

class TestFrbSectionRegex:
    def test_pattern_a_matches_all_districts(self) -> None:
        """2024+ format: 'Federal Reserve Bank of\\n{name}\\n'"""
        from macro_context_reader.economic_sentiment.scraper import _FRB_SECTION_RE_A
        for district in ALL_DISTRICTS:
            text = f"Federal Reserve Bank of\n{district}\nSummary"
            m = _FRB_SECTION_RE_A.search(text)
            assert m is not None, f"Pattern A failed for: {district}"

    def test_pattern_b_matches_all_districts(self) -> None:
        """2019 format: '\\n{name}\\nFederal Reserve Bank of\\n'"""
        from macro_context_reader.economic_sentiment.scraper import _FRB_SECTION_RE_B
        for district in ALL_DISTRICTS:
            text = f"\n{district}\nFederal Reserve Bank of\n"
            m = _FRB_SECTION_RE_B.search(text)
            assert m is not None, f"Pattern B failed for: {district}"

    def test_no_match_inline_name(self) -> None:
        """Should NOT match when district name is on same line (TOC/page ref)."""
        from macro_context_reader.economic_sentiment.scraper import _FRB_SECTION_RE_A
        assert _FRB_SECTION_RE_A.search("Federal Reserve Bank of Boston 7\n") is None

    def test_no_match_toc_dots(self) -> None:
        """Should NOT match table of contents entries with dots."""
        from macro_context_reader.economic_sentiment.scraper import _FRB_SECTION_RE_A
        assert _FRB_SECTION_RE_A.search(
            "Federal Reserve Bank of Boston ..................... 5\n"
        ) is None

    def test_no_match_random(self) -> None:
        from macro_context_reader.economic_sentiment.scraper import (
            _FRB_SECTION_RE_A, _FRB_SECTION_RE_B,
        )
        assert _FRB_SECTION_RE_A.search("GDP growth was moderate.") is None
        assert _FRB_SECTION_RE_B.search("GDP growth was moderate.") is None


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
    assert len(pubs) == 8, (
        f"Expected 8 publications for 2020, found {len(pubs)}: "
        f"{[p['yyyy_nn'] for p in pubs]}"
    )


@pytest.mark.integration
def test_pdf_parse_2019_all_districts() -> None:
    """Empirical: 2019-03 PDF parses all 12 districts with substantial content."""
    import requests as req
    url = "https://www.federalreserve.gov/monetarypolicy/files/BeigeBook_20190306.pdf"
    resp = req.get(url, timeout=60, headers={"User-Agent": "MacroContextReader/1.0"})
    resp.raise_for_status()

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(resp.content)
        pdf_path = Path(f.name)

    try:
        full_text = extract_text_from_pdf(pdf_path)
        sections = split_pdf_into_sections(full_text)

        assert "national_summary" in sections
        assert len(sections["national_summary"]) > 1000

        for district in ALL_DISTRICTS:
            assert district in sections, f"Missing: {district}"
            assert len(sections[district]) > 1500, (
                f"{district}: {len(sections[district])} chars (expected >1500)"
            )
    finally:
        pdf_path.unlink(missing_ok=True)


@pytest.mark.integration
def test_pdf_parse_2024_all_districts() -> None:
    """Same test on 2024 PDF to verify cross-era consistency."""
    import requests as req
    url = "https://www.federalreserve.gov/monetarypolicy/files/BeigeBook_20240117.pdf"
    resp = req.get(url, timeout=60, headers={"User-Agent": "MacroContextReader/1.0"})
    resp.raise_for_status()

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(resp.content)
        pdf_path = Path(f.name)

    try:
        full_text = extract_text_from_pdf(pdf_path)
        sections = split_pdf_into_sections(full_text)

        for district in ALL_DISTRICTS:
            assert district in sections, f"Missing: {district}"
            assert len(sections[district]) > 1500, (
                f"{district}: {len(sections[district])} chars"
            )
    finally:
        pdf_path.unlink(missing_ok=True)


@pytest.mark.integration
def test_pymupdf_extracts_multi_column_pdf() -> None:
    """Regression: COVID-era multi-column PDF (2021-06-02) correctly parsed via PyMuPDF."""
    import requests as req
    url = "https://www.federalreserve.gov/monetarypolicy/files/BeigeBook_20210602.pdf"
    resp = req.get(url, timeout=60, headers={"User-Agent": "MacroContextReader/1.0"})
    resp.raise_for_status()

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(resp.content)
        pdf_path = Path(f.name)

    try:
        text = extract_text_from_pdf(pdf_path)
        sections = split_pdf_into_sections(text)

        assert len(sections) == 13  # national + 12 districts
        expected = ["national_summary"] + list(ALL_DISTRICTS)
        for name in expected:
            assert name in sections, f"Missing: {name}"
            assert len(sections[name]) >= 500, (
                f"{name}: {len(sections[name])} chars (expected >= 500)"
            )
    finally:
        pdf_path.unlink(missing_ok=True)


def test_fallback_pattern_finds_standalone_districts() -> None:
    """Districts appearing only as standalone lines (no 'Federal Reserve Bank of' prefix)."""
    parts = ["National Summary\nEconomic activity grew moderately.\n" + "x " * 500 + "\n\n"]
    for d in ALL_DISTRICTS:
        parts.append(f"\n{d}\n" + f"The {d} district reported moderate growth. " * 80 + "\n\n")
    fake_text = "".join(parts)

    sections = split_pdf_into_sections(fake_text)
    assert "national_summary" in sections
    for d in ALL_DISTRICTS:
        assert d in sections, f"Missing via fallback: {d}"
        assert len(sections[d]) >= 500


@pytest.mark.integration
def test_publications_have_pdf_urls() -> None:
    """Verify discovered publications include PDF URLs."""
    from macro_context_reader.economic_sentiment.scraper import (
        _get_session, discover_publications,
    )
    session = _get_session()
    pubs = discover_publications(session, start_year=2020, end_date=datetime(2020, 12, 31))
    for pub in pubs:
        assert "pdf_url" in pub
        assert pub["pdf_url"].endswith(".pdf"), f"Not a PDF URL: {pub['pdf_url']}"
