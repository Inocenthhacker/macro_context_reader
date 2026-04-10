"""FOMC document ingestion — minutes, statements, speeches. Secondary source."""

from __future__ import annotations


def fetch_document(doc_type: str, date: str) -> str:
    """Fetch a single FOMC document by type and date.

    doc_type: 'minutes' | 'statement' | 'speech'. Secondary source.
    """
    raise NotImplementedError("TODO: PRD-102")
