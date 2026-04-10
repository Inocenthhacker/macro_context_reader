"""Concept dictionary registry — load/save YAML-backed concept lists."""

from __future__ import annotations

CONCEPT_DICTIONARY_PATH = "data/concept_dictionaries/"


def load_dictionary(version: str = "v2_expanded") -> dict[str, list[str]]:
    """Loads concept dictionary from YAML — decoupled from code."""
    raise NotImplementedError("TODO: PRD-102")


def save_dictionary(concepts: dict[str, list[str]], version: str) -> None:
    """Saves concept dictionary to YAML under CONCEPT_DICTIONARY_PATH."""
    raise NotImplementedError("TODO: PRD-102")
