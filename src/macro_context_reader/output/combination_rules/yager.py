"""Yager's rule of combination — conservator la conflict ridicat."""

from __future__ import annotations


def combine_yager(
    bba_list: list[dict[str, float]],
) -> dict[str, float]:
    """
    Yager's rule of combination.

    Masa conflictuală K → alocată la Θ (ignoranță totală), nu normalizată.
    Mai conservator decât Dempster — păstrează conflictul vizibil în output.
    Preferabil când sursele pot fi în dezacord fundamental (ex: NLP hawkish
    vs FedWatch dovish = scenariul exact de interes pentru noi).

    Args:
        bba_list: lista de BBA-uri de la cele 4 straturi

    Returns:
        BBA combinat — m(Θ) va fi mai mare decât la Dempster în caz de conflict
    """
    raise NotImplementedError("TODO: PRD-500")
