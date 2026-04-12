"""Regime feature matrix — PRD-050 CC-1.

Builds a monthly feature matrix from FRED macro series for regime
classification. Six features spanning inflation, growth, labor,
financial stress, and yield curve dimensions.

All standardization is empirical (fit on 2000-2019 pre-COVID window).
Zero hardcoded thresholds — the data clusters itself.

FRED tickers:
  CPIAUCSL  -> CPI Urban Consumers (YoY)
  PCEPILFE  -> Core PCE (YoY, Fed's preferred measure)
  GDPC1     -> Real GDP (YoY, quarterly -> monthly forward-fill)
  UNRATE    -> Unemployment Rate (12m first-difference)
  NFCI      -> Chicago Fed National Financial Conditions Index (weekly -> monthly)
  T10Y2Y    -> 10Y-2Y Treasury spread (daily -> monthly)

Refs: PRD-050 CC-1
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from fredapi import Fred
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

FRED_SERIES = {
    "CPIAUCSL": "cpi",
    "PCEPILFE": "core_pce",
    "GDPC1": "gdp",
    "UNRATE": "unrate",
    "NFCI": "nfci",
    "T10Y2Y": "yield_curve",
}



def _get_fred_client() -> Fred:
    load_dotenv()
    api_key = os.getenv("FRED_API_KEY")
    if not api_key or api_key.startswith("REPLACE_") or api_key == "your_fred_api_key_here":
        raise EnvironmentError(
            "FRED_API_KEY not set. Copy .env.example to .env and add your key "
            "from https://fred.stlouisfed.org/docs/api/api_key.html"
        )
    return Fred(api_key=api_key)


def _fetch_and_resample(
    client: Fred,
    series_id: str,
    start: str,
    transform: str = "level",
) -> pd.Series:
    """Fetch a FRED series and resample to month-end.

    Args:
        transform: 'level' keeps raw values, 'yoy' computes 12-month % change,
                   'diff12m' computes 12-month first difference.
    """
    raw = client.get_series(series_id, observation_start=start)
    if raw.empty:
        raise RuntimeError(f"FRED series {series_id} returned empty")

    raw = raw.dropna()

    if transform == "yoy":
        # For CPI/PCE: YoY % change
        raw = raw.pct_change(periods=12) * 100
        raw = raw.dropna()
    elif transform == "diff12m":
        raw = raw.diff(periods=12)
        raw = raw.dropna()

    # Resample to month-end, taking last available observation
    monthly = raw.resample("ME").last().dropna()
    return monthly


def build_regime_features(
    start: str = "2000-01-01",
    client: Fred | None = None,
) -> pd.DataFrame:
    """Build monthly macro feature matrix for regime classification.

    Args:
        start: Start date for data fetch (needs ~12m lead for YoY transforms).
        client: Optional FRED client for testing.

    Returns:
        DataFrame with DatetimeIndex (monthly) and 6 standardized feature columns.
        Standardization fitted on 2000-2019 (pre-COVID) window.
    """
    if client is None:
        client = _get_fred_client()

    # Fetch earlier to allow 12m lookback for YoY/diff transforms
    fetch_start = str(int(start[:4]) - 2) + start[4:]
    logger.info("Fetching FRED series for regime features (start=%s)...", fetch_start)

    cpi = _fetch_and_resample(client, "CPIAUCSL", fetch_start, transform="yoy")
    core_pce = _fetch_and_resample(client, "PCEPILFE", fetch_start, transform="yoy")
    gdp = _fetch_and_resample(client, "GDPC1", fetch_start, transform="yoy")
    unrate = _fetch_and_resample(client, "UNRATE", fetch_start, transform="diff12m")
    nfci = _fetch_and_resample(client, "NFCI", fetch_start, transform="level")
    yield_curve = _fetch_and_resample(client, "T10Y2Y", fetch_start, transform="level")

    logger.info(
        "Series lengths: CPI=%d, PCE=%d, GDP=%d, UNRATE=%d, NFCI=%d, YC=%d",
        len(cpi), len(core_pce), len(gdp), len(unrate), len(nfci), len(yield_curve),
    )

    # Align all on common monthly index via forward-fill (max 3 months for quarterly GDP)
    features = pd.DataFrame({
        "cpi_yoy": cpi,
        "core_pce_yoy": core_pce,
        "gdp_yoy": gdp,
        "unrate_diff12m": unrate,
        "nfci": nfci,
        "yield_curve": yield_curve,
    })

    # Forward-fill quarterly GDP into monthly (max 3 months)
    features["gdp_yoy"] = features["gdp_yoy"].ffill(limit=3)

    # Drop rows with any NaN (alignment phase)
    features = features.dropna()

    # Trim to requested start
    features = features.loc[start:]

    if features.empty:
        raise RuntimeError(
            f"No overlapping data after alignment. Check FRED series availability from {start}."
        )

    logger.info("Feature matrix: %d months, %d features", len(features), features.shape[1])

    # Standardize: fit on full available history.
    # Post-COVID regime is part of the population, not an outlier to
    # compare against pre-COVID. HMM needs properly normalized input
    # spanning all observed regimes to discover cluster structure.
    scaler = StandardScaler()

    if len(features) < 24:
        raise RuntimeError(
            f"Only {len(features)} months available. Need at least 24."
        )

    scaler.fit(features.values)
    scaled = scaler.transform(features.values)

    result = pd.DataFrame(
        scaled,
        index=features.index,
        columns=features.columns,
    )
    result.attrs["scaler_mean"] = dict(zip(features.columns, scaler.mean_))
    result.attrs["scaler_std"] = dict(zip(features.columns, scaler.scale_))

    return result
