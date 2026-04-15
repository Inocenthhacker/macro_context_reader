"""EMD decomposition for time-series signals.

Empirical Mode Decomposition extracts Intrinsic Mode Functions (IMFs).
- IMFs[0..-2] = oscillatory components at increasing time scales (surface waves)
- IMFs[-1] = monotonic trend = deep current

References
----------
Huang et al. (1998). The empirical mode decomposition and the Hilbert spectrum
    for nonlinear and non-stationary time series analysis.
    Proceedings of the Royal Society A, 454(1971), 903-995.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from PyEMD import EMD

from .schemas import DecompositionResult


DEFAULT_MAX_IMF = 10


def emd_decompose(
    series: pd.Series,
    max_imf: int = DEFAULT_MAX_IMF,
) -> DecompositionResult:
    """Decompose time series via EMD into deep current (last IMF) + surface wave.

    Parameters
    ----------
    series : pd.Series
        Input time series with DatetimeIndex
    max_imf : int
        Maximum number of IMFs to extract. Default 10.

    Returns
    -------
    DecompositionResult with method="emd"
    - deep_current = last IMF (slowest oscillation = trend)
    - surface_wave = sum of all other IMFs
    - residual = original - (deep_current + surface_wave); should be ~0

    Raises
    ------
    ValueError
        If series < 30 obs, contains NaN, or has non-DatetimeIndex
    """
    if not isinstance(series.index, pd.DatetimeIndex):
        raise ValueError("Series must have DatetimeIndex")

    if len(series) < 30:
        raise ValueError(f"Series too short for EMD: {len(series)} obs, need >= 30")

    if series.isna().any():
        raise ValueError("Input series contains NaN values; clean before EMD")

    emd = EMD()
    imfs = emd.emd(series.values, max_imf=max_imf)

    if imfs.shape[0] < 2:
        deep_current = pd.Series(imfs[0], index=series.index)
        surface_wave = pd.Series(np.zeros(len(series)), index=series.index)
    else:
        deep_current = pd.Series(imfs[-1], index=series.index)
        surface_wave = pd.Series(imfs[:-1].sum(axis=0), index=series.index)

    residual = series - (deep_current + surface_wave)

    return DecompositionResult(
        method="emd",
        deep_current=deep_current,
        surface_wave=surface_wave,
        residual=residual,
        metadata={
            "n_imfs": int(imfs.shape[0]),
            "max_imf": max_imf,
            "n_obs": len(series),
            "residual_max_abs": float(residual.abs().max()),
        },
    )
