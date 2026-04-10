"""Concept dictionary validation — overlap and completeness checks."""

from __future__ import annotations


def validate_no_overlap(concepts: dict[str, list[str]]) -> list[str]:
    """Returns words appearing in multiple concepts (should be empty)."""
    raise NotImplementedError("TODO: PRD-102")


def validate_no_empty(concepts: dict[str, list[str]]) -> list[str]:
    """Returns concept names with empty word lists."""
    raise NotImplementedError("TODO: PRD-102")
