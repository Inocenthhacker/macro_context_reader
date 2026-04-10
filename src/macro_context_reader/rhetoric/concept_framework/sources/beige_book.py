"""Beige Book ingestion — 12 Federal Reserve districts, 1970-2025."""

from __future__ import annotations


def fetch_edition(edition_date: str) -> dict[str, str]:
    """Returns {district_name: raw_text} for one Beige Book edition.

    TODO: scraping federalreserve.gov vs. pre-downloaded corpus — TBD.
    """
    raise NotImplementedError("TODO: PRD-102")


def list_available_editions() -> list[str]:
    """Returns sorted list of available edition dates."""
    raise NotImplementedError("TODO: PRD-102")
