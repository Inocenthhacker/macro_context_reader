"""Beige Book scraper — PRD-102 CC-1, CC-1-FIX2, CC-1-FIX4, CC-1-FIX5, CC-1-FIX6.

URL suffix is NOT the calendar month — it's an opaque code extracted from
archive pages. Discovery-based: all URLs are extracted from Fed HTML, never
constructed from dates.

Architecture:
  1. discover_publications() scrapes archive + current index → year pages
     → extracts {yyyy_nn, publication_date, summary_href} per publication
  2. Two URL schemes detected empirically per publication:
     a. FRAGMENTED (2024+): separate -summary.htm and per-district .htm files
     b. MONOLITHIC (2017-2023): single beigebook{yyyy_nn}.htm with all districts
        delimited by header tags — parsed via parse_monolithic_beige_book()
  3. Detection uses has_summary flag from discovery (archive page link format)

Scope: 2017+ only. Pre-2017 Beige Books use a different URL structure
(monolithic HTML in /beigebook/ subfolder) and are not supported.

Cache: data/economic_sentiment/raw/beige_book/{YYYYMMDD}_{section}.txt
Text extracted from HTML BEFORE caching.
Rate limiting: 2s between requests.

Refs: PRD-102 CC-1, CC-1-FIX2, CC-1-FIX4, CC-1-FIX5, CC-1-FIX6
"""

from __future__ import annotations

import logging
import re
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import TypedDict

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

# Pre-2017 uses different URL structure (monolithic HTML in /beigebook/ subfolder)
MIN_SUPPORTED_YEAR = 2017

USER_AGENT = "MacroContextReader/1.0 (academic research)"
REQUEST_DELAY = 2.0
MAX_RETRIES = 3

ALL_DISTRICTS = [
    "Boston", "New York", "Philadelphia", "Cleveland", "Richmond",
    "Atlanta", "Chicago", "St. Louis", "Minneapolis", "Kansas City",
    "Dallas", "San Francisco",
]

# URL slug for each district (empirically validated, CC-1-FIX3)
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

# Regex patterns for extracting publication codes from hrefs
_SUMMARY_RE = re.compile(r"beigebook(\d{6})-summary\.htm", re.IGNORECASE)
_MAIN_RE = re.compile(r"beigebook(\d{6})\.htm", re.IGNORECASE)
_PDF_RE = re.compile(r"BeigeBook_(\d{8})\.pdf", re.IGNORECASE)
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


class Publication(TypedDict):
    """Discovered Beige Book publication."""
    publication_date: datetime
    yyyy_nn: str          # opaque 6-digit code, e.g. "202601"
    has_summary: bool     # True if -summary.htm format (2024+)


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
# Monolithic HTML parsing (2017-2023 era)
# ---------------------------------------------------------------------------

def detect_url_scheme(yyyy_nn: str, session: requests.Session) -> str:
    """Detect whether a publication uses fragmented or monolithic URL scheme.

    Performs HEAD requests to determine empirically which URL format exists.
    Some years (e.g. 2019-2023) have both -summary.htm AND main .htm pages,
    but only 2024+ has per-district URLs. We check for a district URL (boston)
    as the definitive fragmented indicator.

    Returns:
        "fragmented": separate per-district URLs exist (2024+)
        "monolithic": single HTML file contains all districts (2017-2023)

    Raises:
        RuntimeError: if neither URL format returns HTTP 200
    """
    # Check for per-district URL as the definitive fragmented indicator.
    # -summary.htm alone is NOT sufficient: 2019-2023 have -summary.htm
    # but no per-district URLs.
    district_url = f"{BB_BASE}/beigebook{yyyy_nn}-boston.htm"
    try:
        time.sleep(REQUEST_DELAY)
        resp = session.head(district_url, timeout=10, allow_redirects=True)
        if resp.status_code == 200:
            return "fragmented"
    except Exception:
        pass

    monolithic_url = f"{BB_BASE}/beigebook{yyyy_nn}.htm"
    try:
        time.sleep(REQUEST_DELAY)
        resp = session.head(monolithic_url, timeout=10, allow_redirects=True)
        if resp.status_code == 200:
            return "monolithic"
    except Exception:
        pass

    raise RuntimeError(
        f"Neither fragmented nor monolithic URL exists for {yyyy_nn}"
    )


def parse_monolithic_beige_book(html: str) -> dict[str, str]:
    """Parse a monolithic Beige Book HTML page into national + district sections.

    Monolithic format (2017-2023) has two zones:
      1. "Highlights by Federal Reserve District" — short bullet per district
         with <strong>DistrictName</strong> headers. IGNORED (too short).
      2. Full district sections delimited by <h4>Federal Reserve Bank of X</h4>
         headers, each containing sub-sections (Summary, Employment, Prices, etc.)
         marked with <strong> tags.

    Strategy:
      - Find all <h4> tags whose text matches "Federal Reserve Bank of {name}"
      - National summary = all <p> content before the first such <h4>
      - District i = all <p> content between h4[i] and h4[i+1] (or end of article)
      - Some headers have duplication ("Federal Reserve Bank of Federal Reserve
        Bank of New York") — handled by taking the last regex match.

    Returns:
        Dict mapping section names to extracted text:
        {"national_summary": "...", "Boston": "...", "New York": "...", ...}

    Raises:
        ValueError: if content container not found, <10 district h4 headers
            found, or any district has <500 chars of extracted text.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Remove noise
    for tag in soup(["script", "style", "nav", "header", "footer", "aside",
                     "meta", "link"]):
        tag.decompose()

    # Find main content container
    content = soup.find("div", id="article")
    if content is None:
        content = soup.find(
            "div", class_=lambda c: c and "col-xs-12" in c and "col-sm-8" in c,
        )
    if content is None:
        content = soup.find("main")
    if content is None:
        raise ValueError("Cannot locate main content in monolithic Beige Book HTML")

    # --- Step 1: Find <h4> headers matching "Federal Reserve Bank of X" ---
    _FRB_RE = re.compile(r"Federal Reserve Bank of (.+?)$", re.IGNORECASE)

    district_headers: list[tuple[BeautifulSoup, str]] = []  # (h4_element, district_name)
    for h4 in content.find_all("h4"):
        text = h4.get_text(strip=True)
        # Some pages duplicate: "Federal Reserve Bank of Federal Reserve Bank of New York"
        # Strip all "Federal Reserve Bank of" prefixes to get the bare district name.
        if "Federal Reserve Bank of" not in text:
            continue
        raw_name = text
        while "Federal Reserve Bank of" in raw_name:
            raw_name = raw_name.split("Federal Reserve Bank of", 1)[1].strip()

        # Match to canonical district name
        matched = None
        for known in ALL_DISTRICTS:
            if raw_name.lower().replace(".", "") == known.lower().replace(".", ""):
                matched = known
                break
        if matched is not None:
            district_headers.append((h4, matched))

    if len(district_headers) < 10:
        raise ValueError(
            f"Only {len(district_headers)}/12 district <h4> headers found in "
            f"monolithic HTML. Found: {[d for _, d in district_headers]}. "
            f"Page structure may have changed."
        )

    # --- Step 2: Build a flat ordered list of all <p> and <h4> elements ---
    # Walking descendants once is cheaper than repeated find_next_sibling chains
    # which break on nested structures.
    ordered_elements: list = []
    h4_set = {id(h4) for h4, _ in district_headers}
    for elem in content.descendants:
        if elem.name == "p":
            ordered_elements.append(("p", elem))
        elif elem.name == "h4" and id(elem) in h4_set:
            ordered_elements.append(("h4", elem))

    # Map h4 element id → district name for quick lookup
    h4_to_district = {id(h4): name for h4, name in district_headers}

    # --- Step 3: Partition <p> elements between h4 boundaries ---
    sections: dict[str, list[str]] = {"national_summary": []}
    current_section = "national_summary"

    for tag_type, elem in ordered_elements:
        if tag_type == "h4":
            current_section = h4_to_district[id(elem)]
            if current_section not in sections:
                sections[current_section] = []
        else:  # "p"
            para_text = elem.get_text(" ", strip=True)
            if len(para_text) > 20:
                sections[current_section].append(para_text)

    # --- Step 4: Merge and validate ---
    result: dict[str, str] = {}
    for section_name, paragraphs in sections.items():
        joined = "\n".join(paragraphs).strip()
        if joined:
            result[section_name] = joined

    for district in ALL_DISTRICTS:
        text_len = len(result.get(district, ""))
        if text_len < 500:
            raise ValueError(
                f"District '{district}' extracted with insufficient text: "
                f"{text_len} chars (minimum 500). "
                f"Sections found: {list(result.keys())}. "
                f"Page structure may have changed."
            )

    return result


# ---------------------------------------------------------------------------
# URL construction from discovered yyyy_nn (NOT from calendar dates)
# ---------------------------------------------------------------------------

def _summary_url(yyyy_nn: str) -> str:
    """Build national summary URL from discovered code."""
    return f"{BB_BASE}/beigebook{yyyy_nn}-summary.htm"


def _district_url(yyyy_nn: str, district: str) -> str:
    """Build district report URL from discovered code."""
    slug = DISTRICT_URL_SLUGS.get(district)
    if slug is None:
        raise ValueError(f"Unknown district: {district}")
    return f"{BB_BASE}/beigebook{yyyy_nn}-{slug}.htm"


def _main_page_url(yyyy_nn: str) -> str:
    """Build main page URL for older format (pre -summary)."""
    return f"{BB_BASE}/beigebook{yyyy_nn}.htm"


# ---------------------------------------------------------------------------
# Publication discovery — extract URLs from archive, never construct
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
    """Extract all publications from a single year page.

    Parses links matching beigebook{NNNNNN}-summary.htm (2024+ format)
    or beigebook{NNNNNN}.htm (older format). Extracts publication date
    from nearby text context.

    Args:
        html: Raw HTML of the year page.
        year_hint: Default year for date parsing. Overridden by yyyy_nn[:4]
            when available (handles current index page having multiple years).
    """
    soup = BeautifulSoup(html, "html.parser")
    pubs: dict[str, Publication] = {}  # keyed by yyyy_nn

    for a in soup.find_all("a", href=True):
        href = a["href"]

        # Try -summary format first (2024+)
        m = _SUMMARY_RE.search(href)
        if m:
            yyyy_nn = m.group(1)
            if yyyy_nn in pubs:
                continue
            # Use yyyy_nn's own year, not the page-level hint
            entry_year = int(yyyy_nn[:4])
            context = ""
            parent = a.parent
            if parent:
                context = parent.get_text(strip=True)
                if parent.parent:
                    context += " " + parent.parent.get_text(strip=True)
            pub_date = _parse_date_from_context(context, entry_year)
            if pub_date is None:
                pub_date = datetime(entry_year, 1, 15)  # fallback
            pubs[yyyy_nn] = Publication(
                publication_date=pub_date,
                yyyy_nn=yyyy_nn,
                has_summary=True,
            )
            continue

        # Try main page format (pre-2024)
        m = _MAIN_RE.search(href)
        if m:
            yyyy_nn = m.group(1)
            # Skip if it's a year page link (e.g. beigebook2020.htm)
            if len(yyyy_nn) == 6 and yyyy_nn[4:] != "00":
                if yyyy_nn in pubs:
                    continue
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
                pubs[yyyy_nn] = Publication(
                    publication_date=pub_date,
                    yyyy_nn=yyyy_nn,
                    has_summary=False,
                )
            continue

        # Try PDF link — extract date from YYYYMMDD
        m = _PDF_RE.search(href)
        if m:
            yyyymmdd = m.group(1)
            yyyy_nn_candidate = yyyymmdd[:6]
            # Only use PDF to set a better date on an already-discovered pub
            if yyyy_nn_candidate in pubs:
                try:
                    better_date = datetime.strptime(yyyymmdd, "%Y%m%d")
                    pubs[yyyy_nn_candidate]["publication_date"] = better_date
                except ValueError:
                    pass

    return list(pubs.values())


def discover_publications(
    session: requests.Session,
    start_year: int = MIN_SUPPORTED_YEAR,
    end_date: datetime | None = None,
) -> list[Publication]:
    """Discover all Beige Book publications from Fed archive.

    Steps:
      1. Fetch current index page → extract publications for current year
      2. Fetch archive index → find year page URLs
      3. Fetch each year page → extract publications
      4. Merge, deduplicate by yyyy_nn, filter by date range

    Raises:
        RuntimeError: if start_year < MIN_SUPPORTED_YEAR

    Returns sorted list of Publication dicts.
    """
    if start_year < MIN_SUPPORTED_YEAR:
        raise RuntimeError(
            f"start_year={start_year} below MIN_SUPPORTED_YEAR={MIN_SUPPORTED_YEAR}. "
            f"Pre-2017 Beige Books use a different URL structure (monolithic HTML in "
            f"/beigebook/ subfolder) and are not supported by this scraper. "
            f"To include pre-2017 data, implement a separate parser for the legacy URL scheme."
        )
    if end_date is None:
        end_date = datetime.now()

    all_pubs: dict[str, Publication] = {}

    # --- Current index page (has current + next year schedule) ---
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
        current_year = end_date.year
        for pub in _extract_publications_from_year_page(cached, current_year):
            all_pubs[pub["yyyy_nn"]] = pub

    # --- Archive index → year page links ---
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
            # Prefer year-page data over current-index (more specific)
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
# Fetch individual sections
# ---------------------------------------------------------------------------

def fetch_beige_book_national(
    session: requests.Session, pub: Publication,
) -> BeigeBookDocument | None:
    """Fetch national summary for one Beige Book publication.

    Uses discovered yyyy_nn code. Tries -summary format first (2024+),
    then falls back to main page (pre-2024).
    """
    pub_date = pub["publication_date"]
    yyyy_nn = pub["yyyy_nn"]

    cache = _cache_path(pub_date, "national_summary")
    cached = _read_cache(cache)
    if cached is not None:
        url = _summary_url(yyyy_nn) if pub["has_summary"] else _main_page_url(yyyy_nn)
        return BeigeBookDocument(
            publication_date=pub_date,
            section_type="national_summary",
            district=None,
            url=url,
            raw_text=cached,
            source_file=cache,
        )

    # Try -summary URL first
    if pub["has_summary"]:
        url = _summary_url(yyyy_nn)
    else:
        url = _main_page_url(yyyy_nn)

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
        logger.warning("Failed national summary %s (yyyy_nn=%s): %s",
                       pub_date.date(), yyyy_nn, e)
        return None


def fetch_beige_book_districts(
    session: requests.Session, pub: Publication,
) -> list[BeigeBookDocument]:
    """Fetch all 12 district reports for one Beige Book publication.

    For fragmented publications (has_summary=True, 2024+): fetches 12
    separate district URLs.
    For monolithic publications (has_summary=False, 2017-2023): skips here;
    districts are extracted by fetch_monolithic_all() instead.
    """
    if not pub["has_summary"]:
        logger.debug("Skipping fragmented district fetch for %s (monolithic format)",
                     pub["yyyy_nn"])
        return []

    pub_date = pub["publication_date"]
    yyyy_nn = pub["yyyy_nn"]
    docs: list[BeigeBookDocument] = []

    for district, slug in DISTRICT_URL_SLUGS.items():
        cache = _cache_path(pub_date, slug)
        cached = _read_cache(cache)

        if cached is not None:
            docs.append(BeigeBookDocument(
                publication_date=pub_date,
                section_type="district_report",
                district=district,
                url=_district_url(yyyy_nn, district),
                raw_text=cached,
                source_file=cache,
            ))
            continue

        url = _district_url(yyyy_nn, district)
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
            logger.warning("Failed %s for %s (yyyy_nn=%s): %s",
                           district, pub_date.date(), yyyy_nn, e)

    return docs


def fetch_monolithic_all(
    session: requests.Session, pub: Publication,
) -> list[BeigeBookDocument]:
    """Fetch national + district sections from a monolithic Beige Book page.

    For 2017-2023 publications where all content is on a single HTML page.
    Fetches once, parses into sections via parse_monolithic_beige_book(),
    caches each section as individual .txt files (same format as fragmented).

    Returns list of BeigeBookDocument (national_summary + up to 12 districts).
    """
    pub_date = pub["publication_date"]
    yyyy_nn = pub["yyyy_nn"]
    mono_url = _main_page_url(yyyy_nn)

    # Check if all sections are already cached
    national_cache = _cache_path(pub_date, "national_summary")
    all_cached = _read_cache(national_cache) is not None
    if all_cached:
        district_caches = {
            d: _cache_path(pub_date, slug)
            for d, slug in DISTRICT_URL_SLUGS.items()
        }
        all_cached = all(
            _read_cache(c) is not None for c in district_caches.values()
        )

    if all_cached:
        # Reconstruct from cache
        docs: list[BeigeBookDocument] = []
        cached_national = _read_cache(national_cache)
        if cached_national:
            docs.append(BeigeBookDocument(
                publication_date=pub_date,
                section_type="national_summary",
                district=None,
                url=mono_url,
                raw_text=cached_national,
                source_file=national_cache,
            ))
        for district, slug in DISTRICT_URL_SLUGS.items():
            cache = _cache_path(pub_date, slug)
            cached_text = _read_cache(cache)
            if cached_text:
                docs.append(BeigeBookDocument(
                    publication_date=pub_date,
                    section_type="district_report",
                    district=district,
                    url=mono_url,
                    raw_text=cached_text,
                    source_file=cache,
                ))
        return docs

    # Fetch and parse the monolithic HTML
    try:
        resp = _request_with_retry(session, mono_url)
    except Exception as e:
        logger.warning("Failed to fetch monolithic page %s (yyyy_nn=%s): %s",
                       pub_date.date(), yyyy_nn, e)
        return []

    try:
        sections = parse_monolithic_beige_book(resp.text)
    except ValueError as e:
        logger.warning("Failed to parse monolithic %s (yyyy_nn=%s): %s",
                       pub_date.date(), yyyy_nn, e)
        return []

    # Cache each section and build documents
    docs = []

    # National summary
    if "national_summary" in sections:
        cache = _cache_path(pub_date, "national_summary")
        _write_cache(cache, sections["national_summary"])
        docs.append(BeigeBookDocument(
            publication_date=pub_date,
            section_type="national_summary",
            district=None,
            url=mono_url,
            raw_text=sections["national_summary"],
            source_file=cache,
        ))

    # Districts
    for district, slug in DISTRICT_URL_SLUGS.items():
        if district in sections:
            cache = _cache_path(pub_date, slug)
            _write_cache(cache, sections[district])
            docs.append(BeigeBookDocument(
                publication_date=pub_date,
                section_type="district_report",
                district=district,
                url=mono_url,
                raw_text=sections[district],
                source_file=cache,
            ))

    return docs


# ---------------------------------------------------------------------------
# PDF splitting (for pre-2011 archive)
# ---------------------------------------------------------------------------

def _split_pdf_into_sections(full_text: str) -> dict[str, str]:
    """Split a full Beige Book PDF text into national + district sections."""
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
        end = header_positions[i + 1][0] if i + 1 < len(header_positions) else len(full_text)
        text = full_text[pos:end].strip()
        if len(text) > 100:
            sections[district] = text

    return sections


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def fetch_all_beige_books(
    start_year: int = MIN_SUPPORTED_YEAR,
    end_date: datetime | None = None,
) -> list[BeigeBookDocument]:
    """Fetch all Beige Book publications: national + district sections.

    Discovery-based: extracts yyyy_nn codes from Fed archive pages, then
    fetches each section. Never constructs URLs from calendar dates.

    Args:
        start_year: Earliest year to fetch (default 2017).
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
        era = "fragmented" if pub["has_summary"] else "monolithic"
        logger.info("Fetching [%d/%d] %s (yyyy_nn=%s, era=%s)...",
                     i + 1, len(publications), pub["publication_date"].date(),
                     pub["yyyy_nn"], era)

        if pub["has_summary"]:
            # Fragmented era (2024+): separate national + district requests
            national = fetch_beige_book_national(session, pub)
            if national is not None:
                all_docs.append(national)
            districts = fetch_beige_book_districts(session, pub)
            all_docs.extend(districts)
            logger.info("  %s: national=%s, districts=%d",
                         pub["publication_date"].date(),
                         "OK" if national else "FAILED",
                         len(districts))
        else:
            # Monolithic era (2017-2023): single page with all sections
            mono_docs = fetch_monolithic_all(session, pub)
            all_docs.extend(mono_docs)
            n_national = sum(1 for d in mono_docs if d.section_type == "national_summary")
            n_districts = sum(1 for d in mono_docs if d.section_type == "district_report")
            logger.info("  %s: monolithic national=%d, districts=%d",
                         pub["publication_date"].date(), n_national, n_districts)

    logger.info("Total Beige Book sections fetched: %d", len(all_docs))
    return sorted(all_docs, key=lambda d: d.publication_date)
