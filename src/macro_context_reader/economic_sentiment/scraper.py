"""Beige Book scraper — PRD-102 CC-1-FIX9.

PDF-based: each Beige Book is downloaded as a single PDF (consistent format
2011-present), then split into national summary + 12 district sections using
"Federal Reserve Bank of {name}" headers in the extracted text.

Architecture:
  1. discover_publications() scrapes Fed archive + current index pages
     → list of {publication_date, yyyy_nn, pdf_url}
  2. fetch_all_beige_books() downloads each PDF, extracts text via PyMuPDF,
     splits into sections, returns list[BeigeBookDocument]
  3. Single code path for all years (no monolithic/fragmented branching)

PyMuPDF (fitz) handles multi-column layouts natively, critical for
COVID-era publications (2020-2022) with 2-column format.
Fallback regex finds districts without "Federal Reserve Bank of" prefix
(e.g. St. Louis appearing as standalone line in some PDFs).

PDF URL pattern: /monetarypolicy/files/BeigeBook_{YYYYMMDD}.pdf
Cache: data/economic_sentiment/raw/beige_book/pdf/ (raw PDFs)
       data/economic_sentiment/raw/beige_book/text/ (extracted sections)
Rate limiting: 2s between requests.

Refs: PRD-102 CC-1-FIX9
"""

from __future__ import annotations

import logging
import re
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import TypedDict

import fitz  # PyMuPDF
import requests
from bs4 import BeautifulSoup

from macro_context_reader.economic_sentiment.schemas import BeigeBookDocument

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]
CACHE_DIR = _REPO_ROOT / "data" / "economic_sentiment" / "raw" / "beige_book"

BASE_URL = "https://www.federalreserve.gov"
BB_BASE = f"{BASE_URL}/monetarypolicy"
ARCHIVE_URL = f"{BB_BASE}/beige-book-archive.htm"
CURRENT_URL = f"{BB_BASE}/publications/beige-book-default.htm"

# PDF format is consistent from 2011 onward
MIN_SUPPORTED_YEAR = 2011

USER_AGENT = "MacroContextReader/1.0 (academic research)"
REQUEST_DELAY = 2.0
MAX_RETRIES = 3

ALL_DISTRICTS = [
    "Boston", "New York", "Philadelphia", "Cleveland", "Richmond",
    "Atlanta", "Chicago", "St. Louis", "Minneapolis", "Kansas City",
    "Dallas", "San Francisco",
]

# Regex patterns for extracting publication codes from archive page hrefs
_SUMMARY_RE = re.compile(r"beigebook(\d{6})-summary\.htm", re.IGNORECASE)
_MAIN_RE = re.compile(r"beigebook(\d{6})\.htm", re.IGNORECASE)
_PDF_RE = re.compile(
    r"/monetarypolicy/(?:beigebook/)?files/[Bb]eige[Bb]ook_(\d{8})\.pdf",
    re.IGNORECASE,
)
_YEAR_PAGE_RE = re.compile(r"beigebook(\d{4})\.htm", re.IGNORECASE)

# Month name → number for date parsing
_MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}
_MONTH_PATTERN = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(\d{1,2})",
    re.IGNORECASE,
)

# Legacy district section header patterns (line-break-separated).
# PDF layout varies by era and extraction tool:
#   2024+: "Federal Reserve Bank of\n{DistrictName}\nSummary..."
#   2019-:  "\n{DistrictName}\nFederal Reserve Bank of\n"
# Both place the district name on its own line adjacent to "Federal Reserve Bank of".

# Pattern A (2024+): district name on line AFTER "Federal Reserve Bank of"
_FRB_SECTION_RE_A = re.compile(
    r"Federal Reserve Bank of\n"
    r"(Boston|New York|Philadelphia|Cleveland|Richmond|Atlanta|Chicago|"
    r"St\.?\s*Louis|Minneapolis|Kansas City|Dallas|San Francisco)\n",
    re.IGNORECASE,
)

# Pattern B (2019 and earlier): district name on line BEFORE "Federal Reserve Bank of"
_FRB_SECTION_RE_B = re.compile(
    r"\n(Boston|New York|Philadelphia|Cleveland|Richmond|Atlanta|Chicago|"
    r"St\.?\s*Louis|Minneapolis|Kansas City|Dallas|San Francisco)\n"
    r"Federal Reserve Bank of\n",
    re.IGNORECASE,
)


class Publication(TypedDict):
    """Discovered Beige Book publication."""
    publication_date: datetime
    yyyy_nn: str          # opaque 6-digit code, e.g. "202601"
    pdf_url: str          # absolute URL to official PDF


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _get_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    return s


def _request_with_retry(session: requests.Session, url: str) -> requests.Response:
    """GET with exponential backoff retry."""
    for attempt in range(MAX_RETRIES):
        try:
            time.sleep(REQUEST_DELAY)
            resp = session.get(url, timeout=60)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            wait = 2 ** (attempt + 1)
            logger.warning("Request failed (%s), retrying in %ds: %s", e, wait, url)
            time.sleep(wait)
    raise requests.RequestException(f"Failed after {MAX_RETRIES} retries: {url}")


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _read_cache(cache: Path) -> str | None:
    """Read cached text file. Returns None if not found."""
    if cache.exists():
        return cache.read_text(encoding="utf-8")
    return None


def _write_cache(cache: Path, text: str) -> None:
    """Write text to cache file, creating parent dirs."""
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(text, encoding="utf-8")


def clear_cache() -> None:
    """Remove all cached Beige Book files. Use before refetch with new scraper."""
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Beige Book cache cleared: %s", CACHE_DIR)


# ---------------------------------------------------------------------------
# PDF URL construction
# ---------------------------------------------------------------------------

def _pdf_url(yyyymmdd: str) -> str:
    """Build official Beige Book PDF URL from date string."""
    return f"{BASE_URL}/monetarypolicy/files/BeigeBook_{yyyymmdd}.pdf"


# ---------------------------------------------------------------------------
# PDF download and text extraction
# ---------------------------------------------------------------------------

def _download_pdf(session: requests.Session, pdf_url: str, pub_date: datetime) -> Path:
    """Download PDF to cache. Returns local path. Skips if already cached."""
    pdf_dir = CACHE_DIR / "pdf"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    date_str = pub_date.strftime("%Y%m%d")
    pdf_path = pdf_dir / f"BeigeBook_{date_str}.pdf"

    if pdf_path.exists() and pdf_path.stat().st_size > 1000:
        return pdf_path

    logger.info("Downloading PDF: %s", pdf_url)
    resp = _request_with_retry(session, pdf_url)
    pdf_path.write_bytes(resp.content)
    return pdf_path


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract all text from a Beige Book PDF using PyMuPDF.

    PyMuPDF handles multi-column layouts natively, which is critical for
    COVID-era publications (2020-2022) that use 2-column format.

    Returns concatenated text from all pages.
    Raises ValueError if extracted text is too short (<5000 chars).
    """
    doc = fitz.open(pdf_path)
    pages_text = [page.get_text() for page in doc]
    doc.close()

    full_text = "\n".join(pages_text)

    if len(full_text) < 5000:
        raise ValueError(
            f"PDF text extraction too short ({len(full_text)} chars) from "
            f"{pdf_path.name}. File may be corrupt or scanned."
        )

    return full_text


# ---------------------------------------------------------------------------
# PDF section splitting
# ---------------------------------------------------------------------------

def _build_primary_pattern(district: str) -> re.Pattern:
    """Strict pattern: 'Federal Reserve Bank of X' with district escaped."""
    escaped = re.escape(district)
    return re.compile(
        rf"Federal Reserve Bank of\s+{escaped}\b", re.IGNORECASE,
    )


def _build_fallback_pattern(district: str) -> re.Pattern:
    """Standalone line pattern for districts without 'Federal Reserve Bank of' prefix.

    Requires district name on its own line (preceded and followed by newlines).
    Used when PyMuPDF text lacks the full header prefix (e.g. St. Louis in some
    COVID-era PDFs).
    """
    escaped = re.escape(district)
    return re.compile(rf"\n\s*{escaped}\s*\n", re.IGNORECASE)


def split_pdf_into_sections(full_text: str) -> dict[str, str]:
    """Split Beige Book PDF text into national summary + 12 district sections.

    Strategy:
      1. Find district headers via primary pattern ("Federal Reserve Bank of X")
      2. For districts not found, retry with fallback pattern (standalone line)
      3. Use LAST occurrence of each district (skip ToC entries)
      4. Validate each section has >= 500 chars

    Returns:
        {"national_summary": "...", "Boston": "...", ..., "San Francisco": "..."}

    Raises:
        ValueError: if any district not found or any section < 500 chars.
    """
    district_positions: dict[str, tuple[int, str]] = {}

    for district in ALL_DISTRICTS:
        # Try primary pattern first
        primary = _build_primary_pattern(district)
        matches = list(primary.finditer(full_text))
        if matches:
            district_positions[district] = (matches[-1].start(), "primary")
            continue

        # Also try legacy patterns (line-break-separated headers)
        for pattern in (_FRB_SECTION_RE_A, _FRB_SECTION_RE_B):
            legacy_matches = []
            for m in pattern.finditer(full_text):
                raw_name = m.group(1).strip()
                normalized = raw_name.lower().replace(".", "").replace("  ", " ")
                if normalized == district.lower().replace(".", ""):
                    legacy_matches.append(m)
            if legacy_matches:
                district_positions[district] = (legacy_matches[-1].start(), "legacy")
                break

        if district in district_positions:
            continue

        # Fallback: standalone line
        fallback = _build_fallback_pattern(district)
        fb_matches = list(fallback.finditer(full_text))
        if fb_matches:
            district_positions[district] = (fb_matches[-1].start(), "fallback")

    missing = [d for d in ALL_DISTRICTS if d not in district_positions]
    if missing:
        found_primary = [d for d, (_, s) in district_positions.items() if s == "primary"]
        found_legacy = [d for d, (_, s) in district_positions.items() if s == "legacy"]
        found_fallback = [d for d, (_, s) in district_positions.items() if s == "fallback"]
        raise ValueError(
            f"Districts not found in PDF text: {missing}. "
            f"Text length: {len(full_text)} chars. "
            f"Found via primary: {found_primary}. "
            f"Found via legacy: {found_legacy}. "
            f"Found via fallback: {found_fallback}."
        )

    # Sort districts by position to define section boundaries
    sorted_districts = sorted(district_positions.items(), key=lambda x: x[1][0])
    first_district_offset = sorted_districts[0][1][0]

    sections: dict[str, str] = {}

    # National summary = everything before first district
    sections["national_summary"] = full_text[:first_district_offset].strip()

    # Each district = text from its position to next district's position (or end)
    for i, (district, (start, _)) in enumerate(sorted_districts):
        end = sorted_districts[i + 1][1][0] if i + 1 < len(sorted_districts) else len(full_text)
        sections[district] = full_text[start:end].strip()

    # Validate minimum content length
    for name, content in sections.items():
        if len(content) < 500:
            raise ValueError(
                f"Section '{name}' too short: {len(content)} chars (minimum 500)"
            )

    return sections


# ---------------------------------------------------------------------------
# Publication discovery — extract from archive pages
# ---------------------------------------------------------------------------

def _parse_date_from_context(text: str, year: int) -> datetime | None:
    """Parse 'January 14' style date text with known year."""
    m = _MONTH_PATTERN.search(text)
    if not m:
        return None
    month_name = m.group(1).lower()
    day = int(m.group(2))
    month = _MONTH_MAP.get(month_name)
    if month is None:
        return None
    try:
        return datetime(year, month, day)
    except ValueError:
        return None


def _extract_publications_from_year_page(
    html: str, year_hint: int,
) -> list[Publication]:
    """Extract publications from a single year page.

    Discovers PDF URLs from archive page links. Falls back to constructing
    PDF URL from publication date if only HTML links are present.
    """
    soup = BeautifulSoup(html, "html.parser")

    # First pass: collect all yyyy_nn codes and their dates from HTML links
    raw_pubs: dict[str, dict] = {}  # keyed by yyyy_nn

    for a in soup.find_all("a", href=True):
        href = a["href"]

        # Try -summary format (2024+)
        m = _SUMMARY_RE.search(href)
        if m:
            yyyy_nn = m.group(1)
            if yyyy_nn not in raw_pubs:
                entry_year = int(yyyy_nn[:4])
                context = ""
                parent = a.parent
                if parent:
                    context = parent.get_text(strip=True)
                    if parent.parent:
                        context += " " + parent.parent.get_text(strip=True)
                pub_date = _parse_date_from_context(context, entry_year)
                if pub_date is None:
                    pub_date = datetime(entry_year, 1, 15)
                raw_pubs[yyyy_nn] = {"publication_date": pub_date, "yyyy_nn": yyyy_nn}
            continue

        # Try main page format (pre-2024)
        m = _MAIN_RE.search(href)
        if m:
            yyyy_nn = m.group(1)
            if len(yyyy_nn) == 6 and yyyy_nn[4:] != "00" and yyyy_nn not in raw_pubs:
                entry_year = int(yyyy_nn[:4])
                context = ""
                parent = a.parent
                if parent:
                    context = parent.get_text(strip=True)
                    if parent.parent:
                        context += " " + parent.parent.get_text(strip=True)
                pub_date = _parse_date_from_context(context, entry_year)
                if pub_date is None:
                    pub_date = datetime(entry_year, 1, 15)
                raw_pubs[yyyy_nn] = {"publication_date": pub_date, "yyyy_nn": yyyy_nn}
            continue

        # Try PDF link — get exact date and PDF URL
        m = _PDF_RE.search(href)
        if m:
            yyyymmdd = m.group(1)
            try:
                pdf_date = datetime.strptime(yyyymmdd, "%Y%m%d")
            except ValueError:
                continue
            abs_url = href if href.startswith("http") else BASE_URL + href

            # Try to match this PDF to an existing publication.
            # yyyy_nn is opaque (ordinal-in-year, NOT calendar month), so
            # yyyymmdd[:6] may not match any yyyy_nn. Instead, find the
            # closest publication by date within the same year.
            matched_key = None
            yyyy_nn_candidate = yyyymmdd[:6]
            if yyyy_nn_candidate in raw_pubs:
                matched_key = yyyy_nn_candidate
            else:
                # Find nearest existing pub in same year (within 30 days)
                for key, info in raw_pubs.items():
                    if info["publication_date"].year == pdf_date.year:
                        delta = abs((info["publication_date"] - pdf_date).days)
                        if delta <= 30 and "pdf_url" not in info:
                            matched_key = key
                            break

            if matched_key is not None:
                raw_pubs[matched_key]["publication_date"] = pdf_date
                raw_pubs[matched_key]["pdf_url"] = abs_url
            else:
                # PDF-only discovery (no matching HTML link found)
                raw_pubs[yyyymmdd] = {
                    "publication_date": pdf_date,
                    "yyyy_nn": yyyy_nn_candidate,
                    "pdf_url": abs_url,
                }

    # Build Publication list, constructing PDF URL from date if not discovered
    result: list[Publication] = []
    for info in raw_pubs.values():
        pub_date = info["publication_date"]
        pdf_url = info.get("pdf_url")
        if pdf_url is None:
            # Construct from date — the standard Fed pattern
            pdf_url = _pdf_url(pub_date.strftime("%Y%m%d"))
        result.append(Publication(
            publication_date=pub_date,
            yyyy_nn=info["yyyy_nn"],
            pdf_url=pdf_url,
        ))

    return result


def discover_publications(
    session: requests.Session,
    start_year: int = MIN_SUPPORTED_YEAR,
    end_date: datetime | None = None,
) -> list[Publication]:
    """Discover all Beige Book publications from Fed archive.

    Steps:
      1. Fetch current index page -> extract publications for current year
      2. Fetch archive index -> find year page URLs
      3. Fetch each year page -> extract publications + PDF URLs
      4. Merge, deduplicate by yyyy_nn, filter by date range

    Raises:
        RuntimeError: if start_year < MIN_SUPPORTED_YEAR

    Returns sorted list of Publication dicts.
    """
    if start_year < MIN_SUPPORTED_YEAR:
        raise RuntimeError(
            f"start_year={start_year} below MIN_SUPPORTED_YEAR={MIN_SUPPORTED_YEAR}. "
            f"PDF format is consistent from 2011 onward."
        )
    if end_date is None:
        end_date = datetime.now()

    all_pubs: dict[str, Publication] = {}

    # --- Current index page ---
    current_cache = CACHE_DIR / "_current_index.html"
    current_cache.parent.mkdir(parents=True, exist_ok=True)
    cached = _read_cache(current_cache)
    if cached is None:
        try:
            resp = _request_with_retry(session, CURRENT_URL)
            _write_cache(current_cache, resp.text)
            cached = resp.text
        except Exception as e:
            logger.warning("Failed to fetch current index: %s", e)
            cached = ""

    if cached:
        for pub in _extract_publications_from_year_page(cached, end_date.year):
            all_pubs[pub["yyyy_nn"]] = pub

    # --- Archive index -> year page links ---
    archive_cache = CACHE_DIR / "_archive_index.html"
    archive_cache.parent.mkdir(parents=True, exist_ok=True)
    archive_html = _read_cache(archive_cache)
    if archive_html is None:
        try:
            resp = _request_with_retry(session, ARCHIVE_URL)
            _write_cache(archive_cache, resp.text)
            archive_html = resp.text
        except Exception as e:
            logger.warning("Failed to fetch archive index: %s", e)
            archive_html = ""

    year_urls: list[tuple[int, str]] = []
    if archive_html:
        soup = BeautifulSoup(archive_html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            m = _YEAR_PAGE_RE.search(href)
            if m:
                yr = int(m.group(1))
                if yr >= start_year and yr <= end_date.year:
                    url = href if href.startswith("http") else BASE_URL + href
                    year_urls.append((yr, url))

    # Fetch each year page
    for yr, year_url in sorted(year_urls):
        year_cache = CACHE_DIR / f"_year_{yr}.html"
        year_html = _read_cache(year_cache)
        if year_html is None:
            try:
                resp = _request_with_retry(session, year_url)
                _write_cache(year_cache, resp.text)
                year_html = resp.text
            except Exception as e:
                logger.warning("Failed to fetch year page %d: %s", yr, e)
                continue

        for pub in _extract_publications_from_year_page(year_html, yr):
            all_pubs[pub["yyyy_nn"]] = pub

    # Filter by date range
    result = [
        p for p in all_pubs.values()
        if p["publication_date"].year >= start_year
        and p["publication_date"] <= end_date
    ]
    result.sort(key=lambda p: p["publication_date"])

    logger.info("Discovered %d publications (%d-%s)", len(result), start_year, end_date.date())
    return result


# ---------------------------------------------------------------------------
# Fetch + parse + cache a single publication
# ---------------------------------------------------------------------------

def _fetch_and_parse_publication(
    session: requests.Session, pub: Publication,
) -> list[BeigeBookDocument]:
    """Download PDF, extract text, split into sections, return documents.

    Caches both the raw PDF and the extracted text per section.
    Returns list of BeigeBookDocument (1 national + up to 12 districts).
    """
    pub_date = pub["publication_date"]
    pdf_url = pub["pdf_url"]
    date_str = pub_date.strftime("%Y%m%d")

    # Check if all text sections are already cached
    text_dir = CACHE_DIR / "text"
    national_cache = text_dir / f"{date_str}_national_summary.txt"
    if national_cache.exists():
        # Try to reconstruct from cached text files
        docs = _load_from_text_cache(pub_date, pdf_url, text_dir, date_str)
        if docs:
            return docs

    # Download PDF
    pdf_path = _download_pdf(session, pdf_url, pub_date)

    # Extract text
    full_text = extract_text_from_pdf(pdf_path)

    # Split into sections
    sections = split_pdf_into_sections(full_text)

    # Cache text sections and build documents
    text_dir.mkdir(parents=True, exist_ok=True)
    docs: list[BeigeBookDocument] = []

    for section_name, text in sections.items():
        if section_name == "national_summary":
            fname = f"{date_str}_national_summary.txt"
            section_type = "national_summary"
            district = None
        else:
            slug = re.sub(r"[^a-z0-9]+", "_", section_name.lower().strip())[:60]
            fname = f"{date_str}_{slug}.txt"
            section_type = "district_report"
            district = section_name

        fpath = text_dir / fname
        if not fpath.exists():
            _write_cache(fpath, text)

        docs.append(BeigeBookDocument(
            publication_date=pub_date,
            section_type=section_type,
            district=district,
            url=pdf_url,
            raw_text=text,
            source_file=fpath,
        ))

    return docs


def _load_from_text_cache(
    pub_date: datetime, pdf_url: str, text_dir: Path, date_str: str,
) -> list[BeigeBookDocument]:
    """Try to reconstruct BeigeBookDocuments from cached text files."""
    docs: list[BeigeBookDocument] = []

    # National summary
    national_path = text_dir / f"{date_str}_national_summary.txt"
    national_text = _read_cache(national_path)
    if national_text is None:
        return []  # cache incomplete
    docs.append(BeigeBookDocument(
        publication_date=pub_date,
        section_type="national_summary",
        district=None,
        url=pdf_url,
        raw_text=national_text,
        source_file=national_path,
    ))

    # Districts
    for district in ALL_DISTRICTS:
        slug = re.sub(r"[^a-z0-9]+", "_", district.lower().strip())[:60]
        fpath = text_dir / f"{date_str}_{slug}.txt"
        text = _read_cache(fpath)
        if text is None:
            return []  # cache incomplete — re-download
        docs.append(BeigeBookDocument(
            publication_date=pub_date,
            section_type="district_report",
            district=district,
            url=pdf_url,
            raw_text=text,
            source_file=fpath,
        ))

    return docs


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def fetch_all_beige_books(
    start_year: int = MIN_SUPPORTED_YEAR,
    end_date: datetime | None = None,
) -> list[BeigeBookDocument]:
    """Fetch all Beige Book publications: national + district sections.

    PDF-based: downloads official PDFs, extracts text, splits into sections.
    Single code path for all years 2011-present.

    Args:
        start_year: Earliest year to fetch (default 2011).
        end_date: Latest date (default: now).

    Returns:
        List of BeigeBookDocument (national + district sections).
    """
    if end_date is None:
        end_date = datetime.now()

    session = _get_session()

    publications = discover_publications(session, start_year=start_year, end_date=end_date)
    logger.info("Found %d Beige Book publications (%d-%s)",
                len(publications), start_year, end_date.date())

    all_docs: list[BeigeBookDocument] = []

    for i, pub in enumerate(publications):
        logger.info("Processing [%d/%d] %s (yyyy_nn=%s)...",
                     i + 1, len(publications), pub["publication_date"].date(),
                     pub["yyyy_nn"])

        try:
            docs = _fetch_and_parse_publication(session, pub)
            all_docs.extend(docs)
            n_national = sum(1 for d in docs if d.section_type == "national_summary")
            n_districts = sum(1 for d in docs if d.section_type == "district_report")
            logger.info("  %s: national=%d, districts=%d",
                         pub["publication_date"].date(), n_national, n_districts)
        except Exception as e:
            logger.warning("Failed to process %s (yyyy_nn=%s): %s",
                           pub["publication_date"].date(), pub["yyyy_nn"], e)

    logger.info("Total Beige Book sections fetched: %d", len(all_docs))
    return sorted(all_docs, key=lambda d: d.publication_date)
