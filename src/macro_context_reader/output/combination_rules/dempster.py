"""Dempster's rule of combination — standard baseline."""

from __future__ import annotations


def combine_dempster(
    bba_list: list[dict[str, float]],
) -> dict[str, float]:
    """
    Regula Dempster de combinare (standard, baseline).

    K = masa conflictuală → normalizată (ignorată).
    Risc cunoscut: contraintuitiv la K ridicat (Zadeh 1979).
    Folosit ca baseline pentru comparație empirică — nu neapărat ca producție.

    Args:
        bba_list: lista de BBA-uri de la cele 4 straturi

    Returns:
        BBA combinat + K (conflict measure) ca cheie separată:
        {"hawkish": float, "dovish": float, ..., "conflict_K": float}
    """
    raise NotImplementedError("TODO: PRD-500")
