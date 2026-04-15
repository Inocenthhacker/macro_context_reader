"""Side-by-side comparison of decomposition methods.

For backtesting (CC-7): given a signal, run both HP filter and EMD,
return aligned DataFrame for visual inspection and downstream analysis.

NOTE: This is the simplified comparison interface. Full backtesting against
USMPD intraday returns is implemented in CC-7.
"""
from __future__ import annotations

import pandas as pd

from .emd import emd_decompose
from .hp_filter import hp_decompose


def compare_methods(series: pd.Series) -> pd.DataFrame:
    """Run HP filter + EMD on same signal, return side-by-side DataFrame.

    Parameters
    ----------
    series : pd.Series
        Input time series with DatetimeIndex

    Returns
    -------
    pd.DataFrame with columns: original, hp_deep, hp_surface, emd_deep, emd_surface
    """
    hp = hp_decompose(series)
    emd = emd_decompose(series)

    return pd.DataFrame({
        "original": series,
        "hp_deep": hp.deep_current,
        "hp_surface": hp.surface_wave,
        "emd_deep": emd.deep_current,
        "emd_surface": emd.surface_wave,
    })


def compare_metadata(series: pd.Series) -> dict:
    """Return method metadata for diagnostics."""
    hp = hp_decompose(series)
    emd = emd_decompose(series)

    return {
        "hp_filter": hp.metadata,
        "emd": emd.metadata,
    }
