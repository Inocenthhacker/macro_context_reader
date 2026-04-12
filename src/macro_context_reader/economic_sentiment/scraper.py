"""Beige Book scraper — PRD-102 CC-1, CC-1-FIX2.

Validated URL patterns (empirically confirmed 2026-04-12):
  - Archive index: {BASE}/monetarypolicy/beige-book-archive.htm
  - Current index: {BASE}/monetarypolicy/publications/beige-book-default.htm
  - National summary: {BASE}/monetarypolicy/beigebook{YYYYMM}-summary.htm
  - District report:  {BASE}/monetarypolicy/beigebook{YYYYMM}-{slug}.htm
  - Full PDF:         {BASE}/monetarypolicy/files/BeigeBook_{YYYYMMDD}.pdf

Cache: data/economic_sentiment/raw/beige_book/{YYYYMMDD}_{section}.html
Text is extracted from HTML BEFORE caching (cache stores clean text, not raw HTML).
Rate limiting: 2s between requests.

Refs: PRD-102 CC-1, PRD-102/CC-1-FIX2
"""

from __future__ import annotations

import logging
import re
import shutil
import time
from datetime import datetime
from pathlib import Path

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

USER_AGENT = "MacroContextReader/1.0 (academic research)"
REQUEST_DELAY = 2.0
MAX_RETRIES = 3

ALL_DISTRICTS = [
    "Boston", "New York", "Philadelphia", "Cleveland", "Richmond",
    "Atlanta", "Chicago", "St. Louis", "Minneapolis", "Kansas City",
    "Dallas", "San Francisco",
]

# URL slug for each district (empirically validated)
DISTRICT_URL_SLUGS: dict[str, str] = {
    "Boston": "boston",
    "New York": "new-york",
    "Philadelphia": "philadelphia",
    "Cleveland": "cleveland",
    "Richmond": "richmond",
    "Atlanta": "atlanta",
    "Chicago": "chicago",
    "St. Louis": "st-louis",
    "Minneapolis": "minneapolis",
    "Kansas City": "kansas-city",
    "Dallas": "dallas",
    "San Francisco": "san-francisco",
}

# Regex to extract YYYYMM from beigebook URLs
_DATE_HTML_RE = re.compile(r"beigebook(\d{6})", re.IGNORECASE)
_DATE_PDF_RE = re.compile(r"BeigeBook_(\d{8})", re.IGNORECASE)

# Ordinal prefixes used in pre-2011 PDF district sections
_ORDINAL_DISTRICTS = {
    "first": "Boston",
    "second": "New York",
    "third": "Philadelphia",
    "fourth": "Cleveland",
    "fifth": "Richmond",
    "sixth": "Atlanta",
    "seventh": "Chicago",
    "eighth": "St. Louis",
    "ninth": "Minneapolis",
    "tenth": "Kansas City",
    "eleventh": "Dallas",
    "twelfth": "San Francisco",
}

DISTRICT_HEADER_PATTERN = re.compile(
    r"(?:First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth|Eleventh|Twelfth)\s+District"
    r".*?(?:Boston|New York|Philadelphia|Cleveland|Richmond|Atlanta|Chicago|"
    r"St\.?\s*Louis|Minneapolis|Kansas City|Dallas|San Francisco)",
    re.IGNORECASE,
)


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
            resp = session.get(url, timeout=30)
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

def _cache_path(pub_date: datetime, section: str, ext: str = "txt") -> Path:
    """Generate cache file path. Creates parent dirs."""
    slug = re.sub(r"[^a-z0-9]+", "_", section.lower().strip())[:60]
    date_str = pub_date.strftime("%Y%m%d")
    path = CACHE_DIR / f"{date_str}_{slug}.{ext}"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


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
# HTML content extraction
# ---------------------------------------------------------------------------

def extract_beige_book_content(html: str) -> str:
    """Extract clean text from a Beige Book HTML page.

    Targets div#article (Fed Board standard). Falls back to col-xs-12 col-sm-8,
    then main element. Raises ValueError if content cannot be located or is
    too short (< 500 chars after cleaning).
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "meta", "link"]):
        tag.decompose()

    content = soup.find("div", id="article")
    if content is None:
        content = soup.find(
            "div", class_=lambda c: c and "col-xs-12" in c and "col-sm-8" in c,
        )
    if content is None:
        content = soup.find("main")
    if content is None:
        raise ValueError(
            "Cannot locate Beige Book content in HTML "
            "(tried div#article, col-xs-12 col-sm-8, main)"
        )

    raw = content.get_text(separator="\n", strip=True)
    lines = [line for line in raw.split("\n") if len(line) > 20]
    clean = "\n".join(lines)

    if len(clean) < 500:
        raise ValueError(
            f"Extracted content too short ({len(clean)} chars) -- "
            "HTML structure may have changed"
        )
    return clean


# ---------------------------------------------------------------------------
# URL construction
# ---------------------------------------------------------------------------

def _build_url(pub_date: datetime, doc_type: str, district: str | None = None) -> str:
    """Build Beige Book URL from validated patterns.

    Args:
        pub_date: Publication date (only year+month used for YYYYMM).
        doc_type: "national_summary" or "district_report".
        district: District name (required for district_report).

    Returns:
        Full URL string.
    """
    yyyymm = pub_date.strftime("%Y%m")
    if doc_type == "national_summary":
        return f"{BB_BASE}/beigebook{yyyymm}-summary.htm"
    elif doc_type == "district_report":
        if district is None:
            raise ValueError("district required for district_report")
        slug = DISTRICT_URL_SLUGS.get(district)
        if slug is None:
            raise ValueError(f"Unknown district: {district}")
        return f"{BB_BASE}/beigebook{yyyymm}-{slug}.htm"
    else:
        raise ValueError(f"Unknown doc_type: {doc_type}")


# ---------------------------------------------------------------------------
# Archive index — discover publication dates
# ---------------------------------------------------------------------------

def fetch_archive_dates(
    session: requests.Session,
    start_year: int = 2011,
    end_date: datetime | None = None,
) -> list[datetime]:
    """Fetch all Beige Book publication dates from the Fed archive page.

    Parses both archive and current-publications pages, merges and deduplicates.
    Returns sorted list of publication dates (day=15 for YYYYMM-only URLs).
    """
    dates: set[str] = set()  # YYYYMM strings for dedup

    for index_url, cache_name in [
        (ARCHIVE_URL, "_archive_index.html"),
        (CURRENT_URL, "_current_index.html"),
    ]:
        cache = _cache_path(datetime(2000, 1, 1), cache_name, ext="html")
        cached = _read_cache(cache)
        if cached is None:
            try:
                resp = _request_with_retry(session, index_url)
                _write_cache(cache, resp.text)
                cached = resp.text
            except Exception as e:
                logger.warning("Failed to fetch index %s: %s", index_url, e)
                continue

        soup = BeautifulSoup(cached, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            m = _DATE_HTML_RE.search(href)
            if m:
                dates.add(m.group(1))  # YYYYMM
                continue
            m = _DATE_PDF_RE.search(href)
            if m:
                yyyymmdd = m.group(1)
                dates.add(yyyymmdd[:6])  # extract YYYYMM

    # Convert to datetime, filter by range
    result: list[datetime] = []
    for yyyymm in dates:
        try:
            year = int(yyyymm[:4])
            month = int(yyyymm[4:6])
            dt = datetime(year, month, 15)  # day=15 as approximation
        except (ValueError, IndexError):
            continue
        if dt.year < start_year:
            continue
        if end_date is not None and dt > end_date:
            continue
        result.append(dt)

    return sorted(result)


# ---------------------------------------------------------------------------
# Fetch individual sections
# ---------------------------------------------------------------------------

def fetch_beige_book_national(
    session: requests.Session, pub_date: datetime,
) -> BeigeBookDocument | None:
    """Fetch national summary for one Beige Book publication.

    Returns BeigeBookDocument with clean extracted text, or None on failure.
    Cache stores extracted text (not raw HTML).
    """
    cache = _cache_path(pub_date, "national_summary")
    cached = _read_cache(cache)
    if cached is not None:
        return BeigeBookDocument(
            publication_date=pub_date,
            section_type="national_summary",
            district=None,
            url=_build_url(pub_date, "national_summary"),
            raw_text=cached,
            source_file=cache,
        )

    url = _build_url(pub_date, "national_summary")
    try:
        resp = _request_with_retry(session, url)
        text = extract_beige_book_content(resp.text)
        _write_cache(cache, text)
        return BeigeBookDocument(
            publication_date=pub_date,
            section_type="national_summary",
            district=None,
            url=url,
            raw_text=text,
            source_file=cache,
        )
    except Exception as e:
        logger.warning("Failed national summary %s: %s", pub_date.date(), e)
        return None


def fetch_beige_book_districts(
    session: requests.Session, pub_date: datetime,
) -> list[BeigeBookDocument]:
    """Fetch all 12 district reports for one Beige Book publication.

    Cache stores extracted text (not raw HTML). Skips districts that fail.
    """
    docs: list[BeigeBookDocument] = []

    for district, slug in DISTRICT_URL_SLUGS.items():
        cache = _cache_path(pub_date, slug)
        cached = _read_cache(cache)

        if cached is not None:
            docs.append(BeigeBookDocument(
                publication_date=pub_date,
                section_type="district_report",
                district=district,
                url=_build_url(pub_date, "district_report", district),
                raw_text=cached,
                source_file=cache,
            ))
            continue

        url = _build_url(pub_date, "district_report", district)
        try:
            resp = _request_with_retry(session, url)
            text = extract_beige_book_content(resp.text)
            _write_cache(cache, text)
            docs.append(BeigeBookDocument(
                publication_date=pub_date,
                section_type="district_report",
                district=district,
                url=url,
                raw_text=text,
                source_file=cache,
            ))
        except Exception as e:
            logger.warning("Failed %s for %s: %s", district, pub_date.date(), e)

    return docs


# ---------------------------------------------------------------------------
# PDF splitting (for pre-2011 archive)
# ---------------------------------------------------------------------------

def _split_pdf_into_sections(full_text: str) -> dict[str, str]:
    """Split a full Beige Book PDF text into national + district sections.

    Returns dict: {"national_summary": text, "Boston": text, ...}
    """
    sections: dict[str, str] = {}

    header_positions: list[tuple[int, str]] = []
    for match in DISTRICT_HEADER_PATTERN.finditer(full_text):
        header_text = match.group(0).lower()
        for ordinal, district in _ORDINAL_DISTRICTS.items():
            if ordinal in header_text or district.lower() in header_text:
                header_positions.append((match.start(), district))
                break

    if not header_positions:
        sections["national_summary"] = full_text
        return sections

    first_pos = header_positions[0][0]
    national = full_text[:first_pos].strip()
    if len(national) > 50:
        sections["national_summary"] = national

    for i, (pos, district) in enumerate(header_positions):
        if i + 1 < len(header_positions):
            end = header_positions[i + 1][0]
        else:
            end = len(full_text)
        text = full_text[pos:end].strip()
        if len(text) > 100:
            sections[district] = text

    return sections


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def fetch_all_beige_books(
    start_year: int = 2011,
    end_date: datetime | None = None,
) -> list[BeigeBookDocument]:
    """Fetch all Beige Book publications: national + district sections.

    Uses Fed archive to discover publication dates, then fetches each
    section individually via validated URL patterns. Caches extracted
    text (not raw HTML).

    Args:
        start_year: Earliest year to fetch (default 2011, when per-section
            HTML pages became available).
        end_date: Latest date (default: now).

    Returns:
        List of BeigeBookDocument (national + district sections).
    """
    if end_date is None:
        end_date = datetime.now()

    session = _get_session()

    # Discover publication dates from archive
    pub_dates = fetch_archive_dates(session, start_year=start_year, end_date=end_date)
    logger.info("Found %d Beige Book publications (%d-%s)",
                len(pub_dates), start_year, end_date.date())

    all_docs: list[BeigeBookDocument] = []

    for i, pub_date in enumerate(pub_dates):
        logger.info("Fetching [%d/%d] %s...", i + 1, len(pub_dates), pub_date.date())

        # National summary
        national = fetch_beige_book_national(session, pub_date)
        if national is not None:
            all_docs.append(national)

        # District reports
        districts = fetch_beige_book_districts(session, pub_date)
        all_docs.extend(districts)

        logger.info("  %s: national=%s, districts=%d",
                     pub_date.date(),
                     "OK" if national else "FAILED",
                     len(districts))

    logger.info("Total Beige Book sections fetched: %d", len(all_docs))
    return sorted(all_docs, key=lambda d: d.publication_date)
