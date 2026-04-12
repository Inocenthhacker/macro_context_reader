"""Beige Book scraper — PRD-102 CC-1.

Two sources:
  - Minneapolis Fed archive (1970-2010): PDF-based historical archive
    https://www.minneapolisfed.org/region-and-community/regional-economic-indicators/beige-book-archive
  - Federal Reserve Board (1996-present): HTML per section
    https://www.federalreserve.gov/monetarypolicy/beige-book-default.htm

Cache: data/economic_sentiment/raw/beige_book/{YYYYMMDD}_{section}.txt
Rate limiting: 2s between requests.

Refs: PRD-102 CC-1
"""

from __future__ import annotations

import logging
import re
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
BEIGE_BOOK_URL = f"{BASE_URL}/monetarypolicy/beige-book-default.htm"
MPLS_ARCHIVE_URL = "https://www.minneapolisfed.org/region-and-community/regional-economic-indicators/beige-book-archive"
USER_AGENT = "MacroContextReader/1.0 (academic research)"
REQUEST_DELAY = 2.0
MAX_RETRIES = 3

ALL_DISTRICTS = [
    "Boston", "New York", "Philadelphia", "Cleveland", "Richmond",
    "Atlanta", "Chicago", "St. Louis", "Minneapolis", "Kansas City",
    "Dallas", "San Francisco",
]

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


def _cache_path(pub_date: datetime, section: str) -> Path:
    """Generate cache file path."""
    slug = re.sub(r"[^a-z0-9]+", "_", section.lower().strip())[:60]
    date_str = pub_date.strftime("%Y%m%d")
    path = CACHE_DIR / f"{date_str}_{slug}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load_or_fetch(session: requests.Session, url: str, cache: Path) -> str:
    """Return cached text or fetch and cache."""
    if cache.exists():
        return cache.read_text(encoding="utf-8")
    resp = _request_with_retry(session, url)
    text = resp.text
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(text, encoding="utf-8")
    return text


def _extract_text_from_html(html: str) -> str:
    """Extract readable text from a Fed HTML page."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()
    content = (
        soup.find("div", id="article")
        or soup.find("div", class_="col-xs-12 col-sm-8")
        or soup.find("article")
        or soup.find("main")
        or soup
    )
    return content.get_text(separator="\n", strip=True)


def _extract_pdf_text(pdf_path: Path) -> str:
    """Extract text from a cached PDF using pdfplumber."""
    try:
        import pdfplumber
    except ImportError:
        raise ImportError("pdfplumber is required for PDF Beige Books: pip install pdfplumber")

    with pdfplumber.open(pdf_path) as pdf:
        pages = []
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
    return "\n".join(pages)


def _split_pdf_into_sections(full_text: str) -> dict[str, str]:
    """Split a full Beige Book PDF text into national + district sections.

    Returns dict: {"national_summary": text, "Boston": text, ...}
    """
    sections: dict[str, str] = {}

    # Find all district headers and their positions
    header_positions: list[tuple[int, str]] = []
    for match in DISTRICT_HEADER_PATTERN.finditer(full_text):
        header_text = match.group(0).lower()
        for ordinal, district in _ORDINAL_DISTRICTS.items():
            if ordinal in header_text or district.lower() in header_text:
                header_positions.append((match.start(), district))
                break

    if not header_positions:
        # No district headers found -> treat entire text as national summary
        sections["national_summary"] = full_text
        return sections

    # Everything before first district header = national summary
    first_pos = header_positions[0][0]
    national = full_text[:first_pos].strip()
    if len(national) > 50:
        sections["national_summary"] = national

    # Split between district headers
    for i, (pos, district) in enumerate(header_positions):
        if i + 1 < len(header_positions):
            end = header_positions[i + 1][0]
        else:
            end = len(full_text)
        text = full_text[pos:end].strip()
        if len(text) > 100:
            sections[district] = text

    return sections


def fetch_beige_book_index_fed(
    session: requests.Session, start_year: int = 1996,
) -> list[dict]:
    """Fetch index of Beige Book publications from federalreserve.gov.

    Returns list of {date: datetime, url: str} for each publication.
    """
    cache = CACHE_DIR / "_fed_index.html"
    html = _load_or_fetch(session, BEIGE_BOOK_URL, cache)
    soup = BeautifulSoup(html, "html.parser")

    entries: list[dict] = []
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if "/monetarypolicy/beigebook" not in href:
            continue
        # Extract date from URL patterns like beigebook202401 or beige-book-20240131
        date_match = re.search(r"(\d{6,8})", href)
        if not date_match:
            continue
        date_str = date_match.group(1)
        try:
            if len(date_str) == 6:
                pub_date = datetime.strptime(date_str, "%Y%m")
            else:
                pub_date = datetime.strptime(date_str, "%Y%m%d")
        except ValueError:
            continue
        if pub_date.year < start_year:
            continue

        url = href if href.startswith("http") else BASE_URL + href
        entries.append({"date": pub_date, "url": url})

    # Deduplicate by date
    seen: set[str] = set()
    unique: list[dict] = []
    for e in entries:
        key = e["date"].strftime("%Y%m%d")
        if key not in seen:
            seen.add(key)
            unique.append(e)

    return sorted(unique, key=lambda e: e["date"])


def _fetch_fed_publication(
    session: requests.Session, pub_date: datetime, index_url: str,
) -> list[BeigeBookDocument]:
    """Fetch national summary + district reports for one Fed publication.

    Post-2011 format: main page links to individual district pages.
    """
    docs: list[BeigeBookDocument] = []

    cache = _cache_path(pub_date, "index")
    html = _load_or_fetch(session, index_url, cache)
    soup = BeautifulSoup(html, "html.parser")

    # Try to find individual section links
    section_links: list[tuple[str, str | None]] = []  # (url, district_or_none)

    for link in soup.find_all("a", href=True):
        href = link["href"]
        text = link.get_text(strip=True).lower()

        # National summary link
        if any(kw in text for kw in ["overall", "summary", "national"]):
            url = href if href.startswith("http") else BASE_URL + href
            section_links.append((url, None))
            continue

        # District links
        for district in ALL_DISTRICTS:
            if district.lower() in text:
                url = href if href.startswith("http") else BASE_URL + href
                section_links.append((url, district))
                break

    if section_links:
        # Modern format: fetch each section separately
        for url, district in section_links:
            section_type = "national_summary" if district is None else "district_report"
            section_name = district or "national_summary"
            cache_f = _cache_path(pub_date, section_name)
            try:
                section_html = _load_or_fetch(session, url, cache_f)
                raw_text = _extract_text_from_html(section_html)
                if len(raw_text) < 100:
                    continue
                docs.append(BeigeBookDocument(
                    publication_date=pub_date,
                    section_type=section_type,
                    district=district,
                    url=url,
                    raw_text=raw_text,
                    source_file=cache_f,
                ))
            except Exception as e:
                logger.warning("Failed to fetch %s %s: %s", section_name, pub_date.date(), e)
    else:
        # Older format or single-page: extract text and try to split
        full_text = _extract_text_from_html(html)
        if len(full_text) > 500:
            sections = _split_pdf_into_sections(full_text)
            for section_name, text in sections.items():
                if section_name == "national_summary":
                    docs.append(BeigeBookDocument(
                        publication_date=pub_date,
                        section_type="national_summary",
                        district=None,
                        url=index_url,
                        raw_text=text,
                        source_file=cache,
                    ))
                else:
                    docs.append(BeigeBookDocument(
                        publication_date=pub_date,
                        section_type="district_report",
                        district=section_name,
                        url=index_url,
                        raw_text=text,
                        source_file=cache,
                    ))

    return docs


def fetch_beige_book_index_mpls(
    session: requests.Session, start_year: int = 1970, end_year: int = 2010,
) -> list[dict]:
    """Fetch index from Minneapolis Fed archive (1970-2010 PDFs).

    Returns list of {date: datetime, url: str, format: 'pdf'}.
    """
    cache = CACHE_DIR / "_mpls_index.html"
    try:
        html = _load_or_fetch(session, MPLS_ARCHIVE_URL, cache)
    except Exception as e:
        logger.warning("Minneapolis archive unavailable: %s", e)
        return []

    soup = BeautifulSoup(html, "html.parser")
    entries: list[dict] = []

    for link in soup.find_all("a", href=True):
        href = link["href"]
        if ".pdf" not in href.lower():
            continue
        date_match = re.search(r"(\d{4})[-_]?(\d{2})", href)
        if not date_match:
            continue
        try:
            year = int(date_match.group(1))
            month = int(date_match.group(2))
            pub_date = datetime(year, month, 1)
        except (ValueError, IndexError):
            continue

        if pub_date.year < start_year or pub_date.year > end_year:
            continue

        url = href if href.startswith("http") else f"https://www.minneapolisfed.org{href}"
        entries.append({"date": pub_date, "url": url, "format": "pdf"})

    return sorted(entries, key=lambda e: e["date"])


def _fetch_mpls_publication(
    session: requests.Session, pub_date: datetime, pdf_url: str,
) -> list[BeigeBookDocument]:
    """Fetch and split a Minneapolis archive PDF into sections."""
    cache_pdf = _cache_path(pub_date, "full_pdf")
    cache_pdf = cache_pdf.with_suffix(".pdf")

    if not cache_pdf.exists():
        resp = _request_with_retry(session, pdf_url)
        cache_pdf.parent.mkdir(parents=True, exist_ok=True)
        cache_pdf.write_bytes(resp.content)

    try:
        full_text = _extract_pdf_text(cache_pdf)
    except Exception as e:
        logger.warning("PDF extraction failed for %s: %s", pub_date.date(), e)
        return []

    if len(full_text) < 200:
        logger.warning("PDF text too short (%d chars) for %s", len(full_text), pub_date.date())
        return []

    sections = _split_pdf_into_sections(full_text)
    docs: list[BeigeBookDocument] = []
    for section_name, text in sections.items():
        if section_name == "national_summary":
            docs.append(BeigeBookDocument(
                publication_date=pub_date,
                section_type="national_summary",
                district=None,
                url=pdf_url,
                raw_text=text,
                source_file=cache_pdf,
            ))
        else:
            docs.append(BeigeBookDocument(
                publication_date=pub_date,
                section_type="district_report",
                district=section_name,
                url=pdf_url,
                raw_text=text,
                source_file=cache_pdf,
            ))

    return docs


def fetch_all_beige_books(
    start_year: int = 1970,
    end_date: datetime | None = None,
) -> list[BeigeBookDocument]:
    """Fetch all Beige Book publications: national + district sections.

    Merges Minneapolis archive (1970-2010) and Fed Board (1996-present).
    Fed Board takes precedence for overlapping years.

    Args:
        start_year: Earliest year to fetch.
        end_date: Latest date (default: now).

    Returns:
        List of BeigeBookDocument (national + district sections).
    """
    if end_date is None:
        end_date = datetime.now()

    session = _get_session()
    all_docs: list[BeigeBookDocument] = []
    processed_dates: set[str] = set()

    # 1. Fed Board (1996-present) — preferred source
    logger.info("Fetching Fed Board Beige Book index...")
    fed_index = fetch_beige_book_index_fed(session, start_year=max(start_year, 1996))
    fed_index = [e for e in fed_index if e["date"] <= end_date]
    logger.info("Fed Board: %d publications found", len(fed_index))

    for entry in fed_index:
        date_key = entry["date"].strftime("%Y%m")
        if date_key in processed_dates:
            continue
        try:
            docs = _fetch_fed_publication(session, entry["date"], entry["url"])
            all_docs.extend(docs)
            processed_dates.add(date_key)
            logger.info("  %s: %d sections", entry["date"].date(), len(docs))
        except Exception as e:
            logger.warning("Failed %s: %s", entry["date"].date(), e)

    # 2. Minneapolis archive (1970-2010) — fills gaps
    if start_year < 1996:
        logger.info("Fetching Minneapolis Fed archive index...")
        mpls_index = fetch_beige_book_index_mpls(
            session, start_year=start_year, end_year=min(1995, end_date.year),
        )
        logger.info("Minneapolis archive: %d PDFs found", len(mpls_index))

        for entry in mpls_index:
            date_key = entry["date"].strftime("%Y%m")
            if date_key in processed_dates:
                continue
            try:
                docs = _fetch_mpls_publication(session, entry["date"], entry["url"])
                all_docs.extend(docs)
                processed_dates.add(date_key)
                logger.info("  %s: %d sections", entry["date"].date(), len(docs))
            except Exception as e:
                logger.warning("Failed %s: %s", entry["date"].date(), e)

    logger.info("Total Beige Book sections fetched: %d", len(all_docs))
    return sorted(all_docs, key=lambda d: d.publication_date)
