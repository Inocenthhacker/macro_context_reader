"""FOMC Document Scraper — PRD-101 CC-1.

Scrapes statements, minutes, press conference transcripts, and speeches
from federalreserve.gov. Caches raw documents on disk to avoid redundant
network requests.

Rate limiting: 1s between requests, retry with exponential backoff.

Refs: PRD-101 CC-1
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Literal

import requests
from bs4 import BeautifulSoup

from macro_context_reader.rhetoric.schemas import FOMCDocument

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]  # src/macro_context_reader/rhetoric/ -> repo root
CACHE_DIR = _REPO_ROOT / "data" / "rhetoric" / "raw"
BASE_URL = "https://www.federalreserve.gov"
CALENDAR_URL = f"{BASE_URL}/monetarypolicy/fomccalendars.htm"
SPEECHES_URL = f"{BASE_URL}/newsevents/speeches.htm"
USER_AGENT = "MacroContextReader/1.0 (academic research)"
REQUEST_DELAY = 1.0
MAX_RETRIES = 3


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


def _cache_path(doc_type: str, date: datetime, title: str, ext: str = "txt") -> Path:
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower().strip())[:80]
    date_str = date.strftime("%Y%m%d")
    path = CACHE_DIR / doc_type / f"{date_str}_{slug}.{ext}"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load_or_fetch(
    session: requests.Session,
    url: str,
    cache: Path,
) -> str:
    """Return cached text if available, otherwise fetch and cache."""
    if cache.exists():
        return cache.read_text(encoding="utf-8")
    resp = _request_with_retry(session, url)
    text = resp.text
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(text, encoding="utf-8")
    return text


def _extract_text_from_html(html: str) -> str:
    """Extract readable text from Fed HTML page (generic fallback)."""
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


def extract_statement_text(html: str) -> str:
    """Extract clean text from a FOMC statement/press release page.

    Targets div#article which contains the actual statement content
    on federalreserve.gov press release pages.

    Returns:
        Clean text with lines > 20 chars (filters nav artifacts).

    Raises:
        ValueError: if content div not found or text too short.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()

    content = soup.find("div", id="article")
    if content is None:
        content = soup.find("div", class_="col-xs-12 col-sm-8")
    if content is None:
        raise ValueError("Cannot locate statement content div in HTML")

    raw = content.get_text(separator="\n", strip=True)
    lines = [line for line in raw.split("\n") if len(line) > 20]
    text = "\n".join(lines)

    if len(text) < 500:
        raise ValueError(
            f"Extracted text too short ({len(text)} chars). "
            "HTML structure may have changed."
        )

    return text


def fetch_fomc_statements(start_year: int = 2015) -> list[FOMCDocument]:
    """Scrape FOMC meeting statements from federalreserve.gov.

    Parses the FOMC calendar page structure: each div.fomc-meeting contains
    links for a specific meeting. The meeting statement link has text "HTML"
    and href matching /pressreleases/monetary{YYYYMMDD}a.htm.

    Strategy documents ("Statement on Longer-Run Goals") are explicitly
    excluded — they share the same URL pattern but are not meeting statements.
    """
    session = _get_session()
    docs: list[FOMCDocument] = []

    calendar_cache = CACHE_DIR / "_calendar.html"
    html = _load_or_fetch(session, CALENDAR_URL, calendar_cache)
    soup = BeautifulSoup(html, "html.parser")

    # Each div.fomc-meeting = one FOMC meeting
    panels = soup.find_all("div", class_="fomc-meeting")
    logger.info("Found %d fomc-meeting panels in calendar", len(panels))

    for panel in panels:
        for link in panel.find_all("a", href=True):
            href = link["href"]
            link_text = link.get_text(strip=True)

            # Skip strategy documents explicitly
            if "Longer-Run Goals" in link_text or "reaffirm" in link_text.lower():
                logger.debug("Skipping strategy doc: %s", link_text[:60])
                continue

            # Meeting statement = link with text "HTML" pointing to pressreleases/monetary
            if link_text != "HTML":
                continue
            if "/pressreleases/monetary" not in href:
                continue

            date_match = re.search(r"(\d{8})", href)
            if not date_match:
                continue
            try:
                date = datetime.strptime(date_match.group(1), "%Y%m%d")
            except ValueError:
                continue

            if date.year < start_year:
                continue

            url = BASE_URL + href
            cache = _cache_path("statement", date, f"statement_{date_match.group(1)}")
            try:
                raw_html = _load_or_fetch(session, url, cache)
                raw_text = extract_statement_text(raw_html)
                docs.append(FOMCDocument(
                    date=date,
                    doc_type="statement",
                    url=url,
                    title=f"FOMC Statement {date.strftime('%Y-%m-%d')}",
                    raw_text=raw_text,
                    source_file=cache,
                ))
                logger.info("  meeting statement %s (%d chars)", date.date(), len(raw_text))
            except ValueError as e:
                logger.warning("Content extraction failed for %s: %s", url, e)
            except Exception as e:
                logger.warning("Failed to fetch statement %s: %s", url, e)

    logger.info("Fetched %d FOMC meeting statements (start_year=%d)", len(docs), start_year)
    return sorted(docs, key=lambda d: d.date)


def fetch_fomc_minutes(start_year: int = 2015) -> list[FOMCDocument]:
    """Scrape FOMC minutes from federalreserve.gov."""
    session = _get_session()
    docs: list[FOMCDocument] = []

    html = _load_or_fetch(session, CALENDAR_URL, CACHE_DIR / "_calendar.html")
    soup = BeautifulSoup(html, "html.parser")

    for link in soup.find_all("a", href=True):
        href = link["href"]
        text = link.get_text(strip=True).lower()
        if "minute" not in text:
            continue
        if not href.startswith("/"):
            continue

        url = BASE_URL + href
        date_match = re.search(r"(\d{8})", href)
        if not date_match:
            continue
        try:
            date = datetime.strptime(date_match.group(1), "%Y%m%d")
        except ValueError:
            continue

        if date.year < start_year:
            continue

        ext = "pdf" if href.endswith(".pdf") else "html"
        cache = _cache_path("minutes", date, f"minutes_{date_match.group(1)}", ext)
        try:
            if ext == "pdf":
                # PDF handling via pdfplumber
                if not cache.exists():
                    resp = _request_with_retry(session, url)
                    cache.write_bytes(resp.content)
                try:
                    import pdfplumber
                    with pdfplumber.open(cache) as pdf:
                        raw_text = "\n".join(
                            page.extract_text() or "" for page in pdf.pages
                        )
                except ImportError:
                    logger.warning("pdfplumber not installed, skipping PDF: %s", url)
                    continue
            else:
                raw_html = _load_or_fetch(session, url, cache)
                raw_text = _extract_text_from_html(raw_html)

            if len(raw_text) < 200:
                continue
            docs.append(FOMCDocument(
                date=date,
                doc_type="minutes",
                url=url,
                title=f"FOMC Minutes {date.strftime('%Y-%m-%d')}",
                raw_text=raw_text,
                source_file=cache,
            ))
        except Exception as e:
            logger.warning("Failed to fetch minutes %s: %s", url, e)

    logger.info("Fetched %d FOMC minutes (start_year=%d)", len(docs), start_year)
    return sorted(docs, key=lambda d: d.date)


def fetch_press_conferences(start_year: int = 2015) -> list[FOMCDocument]:
    """Scrape press conference transcripts from federalreserve.gov."""
    session = _get_session()
    docs: list[FOMCDocument] = []

    html = _load_or_fetch(session, CALENDAR_URL, CACHE_DIR / "_calendar.html")
    soup = BeautifulSoup(html, "html.parser")

    for link in soup.find_all("a", href=True):
        href = link["href"]
        text = link.get_text(strip=True).lower()
        if "press conference" not in text and "transcript" not in text:
            continue
        if not href.startswith("/"):
            continue

        url = BASE_URL + href
        date_match = re.search(r"(\d{8})", href)
        if not date_match:
            continue
        try:
            date = datetime.strptime(date_match.group(1), "%Y%m%d")
        except ValueError:
            continue

        if date.year < start_year:
            continue

        cache = _cache_path("press_conference", date, f"presser_{date_match.group(1)}")
        try:
            raw_html = _load_or_fetch(session, url, cache)
            raw_text = _extract_text_from_html(raw_html)
            if len(raw_text) < 200:
                continue
            docs.append(FOMCDocument(
                date=date,
                doc_type="press_conference",
                url=url,
                title=f"Press Conference {date.strftime('%Y-%m-%d')}",
                raw_text=raw_text,
                source_file=cache,
            ))
        except Exception as e:
            logger.warning("Failed to fetch presser %s: %s", url, e)

    logger.info("Fetched %d press conferences (start_year=%d)", len(docs), start_year)
    return sorted(docs, key=lambda d: d.date)


def fetch_speeches(
    start_year: int = 2015, max_per_year: int = 120
) -> list[FOMCDocument]:
    """Scrape Fed speeches from federalreserve.gov/newsevents/speeches.htm."""
    session = _get_session()
    docs: list[FOMCDocument] = []

    html = _load_or_fetch(session, SPEECHES_URL, CACHE_DIR / "_speeches.html")
    soup = BeautifulSoup(html, "html.parser")

    for link in soup.find_all("a", href=True):
        href = link["href"]
        if "/newsevents/speech/" not in href and "/speech/" not in href:
            continue
        if not href.startswith("/"):
            continue

        url = BASE_URL + href
        date_match = re.search(r"(\d{8})", href)
        if not date_match:
            continue
        try:
            date = datetime.strptime(date_match.group(1), "%Y%m%d")
        except ValueError:
            continue

        if date.year < start_year:
            continue

        title = link.get_text(strip=True)[:120] or f"Speech {date.strftime('%Y-%m-%d')}"
        cache = _cache_path("speech", date, title)
        try:
            raw_html = _load_or_fetch(session, url, cache)
            raw_text = _extract_text_from_html(raw_html)
            if len(raw_text) < 100:
                continue
            docs.append(FOMCDocument(
                date=date,
                doc_type="speech",
                url=url,
                title=title,
                raw_text=raw_text,
                source_file=cache,
            ))
        except Exception as e:
            logger.warning("Failed to fetch speech %s: %s", url, e)

    logger.info("Fetched %d speeches (start_year=%d)", len(docs), start_year)
    return sorted(docs, key=lambda d: d.date)[:max_per_year * (datetime.now().year - start_year + 1)]
