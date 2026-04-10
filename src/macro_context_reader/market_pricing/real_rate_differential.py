"""Real Rate Differential composite — US 5Y real minus EU 5Y real.

Combină trei surse ingerate de CC-2b/CC-3/CC-5:
- us_rates.py: DFII5 (US 5Y TIPS real yield, daily)
- eu_rates.py: ECB AAA 5Y nominal yield (daily)
- eu_inflation.py: ECB SPF longer-term HICP forecast (quarterly)

Alinierea temporală:
- us_rates ⋈ eu_rates: inner join pe date (ambele daily business days)
- eu_inflation: forward-fill quarterly → daily cu limită 95 zile

Formula:
  eu_5y_real = eu_5y_nominal_aaa - eu_inflation_expectations_5y
  real_rate_differential = us_5y_real - eu_5y_real

Refs: PRD-200 CC-6, DEC-001, DEC-002, DEC-004
"""

from __future__ import annotations

import warnings
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from macro_context_reader.market_pricing.schemas import RealRateDifferentialRow

DEFAULT_START_DATE = datetime(2015, 1, 1)
DEFAULT_OUTPUT_PATH = Path("data/market_pricing/real_rate_differential.parquet")
DEFAULT_FFILL_LIMIT_DAYS = 95


def compute_real_rate_differential(
    start: datetime = DEFAULT_START_DATE,
    end: Optional[datetime] = None,
    us_rates_df: Optional[pd.DataFrame] = None,
    eu_rates_df: Optional[pd.DataFrame] = None,
    eu_inflation_df: Optional[pd.DataFrame] = None,
    forward_fill_limit_days: int = DEFAULT_FFILL_LIMIT_DAYS,
) -> pd.DataFrame:
    """Compute composite real rate differential (US 5Y real - EU 5Y real).

    Args:
        start: Data de început (default 2015-01-01)
        end: Data de final (default = present)
        us_rates_df: DataFrame us_rates (dacă None, fetch-uiește)
        eu_rates_df: DataFrame eu_rates (dacă None, fetch-uiește)
        eu_inflation_df: DataFrame eu_inflation (dacă None, fetch-uiește)
        forward_fill_limit_days: Limita forward-fill pentru SPF quarterly→daily

    Returns:
        DataFrame cu coloanele:
        - date, us_5y_real, eu_5y_nominal_aaa, eu_inflation_expectations_5y,
          eu_5y_real, real_rate_differential
        Frecvență zilnică (business days), sortat ascending.

    Raises:
        ValueError: dacă sursele sunt goale sau incompatibile
    """
    # Fetch upstream data if not provided
    us_df = _ensure_us_rates(us_rates_df, start, end)
    eu_df = _ensure_eu_rates(eu_rates_df, start, end)
    infl_df = _ensure_eu_inflation(eu_inflation_df, start, end)

    # Inner join US ⋈ EU on date (both daily business days)
    merged = pd.merge(
        us_df[["date", "us_5y_real"]],
        eu_df[["date", "eu_5y_nominal_aaa"]],
        on="date",
        how="inner",
    )

    if merged.empty:
        raise ValueError("Inner join US ⋈ EU produced empty result — no overlapping dates")

    # Forward-fill SPF quarterly → daily
    merged = _align_inflation(merged, infl_df, forward_fill_limit_days)

    # Compute derived columns
    merged["eu_5y_real"] = (
        merged["eu_5y_nominal_aaa"] - merged["eu_inflation_expectations_5y"]
    )
    merged["real_rate_differential"] = (
        merged["us_5y_real"] - merged["eu_5y_real"]
    )

    # Select final columns in schema order
    result = merged[[
        "date",
        "us_5y_real",
        "eu_5y_nominal_aaa",
        "eu_inflation_expectations_5y",
        "eu_5y_real",
        "real_rate_differential",
    ]].copy()

    result = result.sort_values("date").reset_index(drop=True)

    _validate_rows(result)

    return result


def _ensure_us_rates(
    df: Optional[pd.DataFrame], start: datetime, end: Optional[datetime]
) -> pd.DataFrame:
    if df is not None:
        return df
    from macro_context_reader.market_pricing.us_rates import fetch_us_rates
    return fetch_us_rates(start=start, end=end)


def _ensure_eu_rates(
    df: Optional[pd.DataFrame], start: datetime, end: Optional[datetime]
) -> pd.DataFrame:
    if df is not None:
        return df
    from macro_context_reader.market_pricing.eu_rates import fetch_eu_rates
    return fetch_eu_rates(start=start, end=end)


def _ensure_eu_inflation(
    df: Optional[pd.DataFrame], start: datetime, end: Optional[datetime]
) -> pd.DataFrame:
    if df is not None:
        return df
    from macro_context_reader.market_pricing.eu_inflation import fetch_eu_inflation_5y
    return fetch_eu_inflation_5y(start=start, end=end)


def _align_inflation(
    daily_df: pd.DataFrame,
    inflation_df: pd.DataFrame,
    ffill_limit: int,
) -> pd.DataFrame:
    """Aliniază SPF quarterly cu daily index prin forward-fill.

    Args:
        daily_df: DataFrame daily cu coloana 'date'
        inflation_df: DataFrame quarterly cu coloanele 'date', 'eu_inflation_expectations_5y'
        ffill_limit: Numărul maxim de zile pentru forward-fill

    Returns:
        daily_df cu coloana 'eu_inflation_expectations_5y' adăugată
    """
    # Check SPF coverage vs daily range
    daily_min = daily_df["date"].min()
    daily_max = daily_df["date"].max()
    spf_min = inflation_df["date"].min()
    spf_max = inflation_df["date"].max()

    if spf_min > daily_min:
        warnings.warn(
            f"SPF starts at {spf_min.date()} but daily data starts at {daily_min.date()}. "
            f"Rows before first SPF observation will be dropped after forward-fill.",
            stacklevel=3,
        )

    if spf_max < daily_max:
        gap_days = (daily_max - spf_max).days
        if gap_days > ffill_limit:
            warnings.warn(
                f"SPF latest observation is {spf_max.date()}, daily data extends to "
                f"{daily_max.date()} ({gap_days} days gap > {ffill_limit} day limit). "
                f"Trailing rows will be dropped.",
                stacklevel=3,
            )

    # merge_asof: for each daily date, pick the most recent SPF observation
    # This correctly handles SPF dates that fall on weekends/holidays
    # and SPF dates that predate the daily range.
    daily_sorted = daily_df.sort_values("date").copy()
    infl_sorted = inflation_df[["date", "eu_inflation_expectations_5y"]].sort_values("date")

    daily_sorted = pd.merge_asof(
        daily_sorted,
        infl_sorted,
        on="date",
        direction="backward",
    )

    # Enforce forward-fill limit: drop rows where the SPF observation is
    # more than ffill_limit calendar days old.
    # To compute staleness, we need the original SPF dates.
    spf_dates_series = infl_sorted.set_index("eu_inflation_expectations_5y")["date"]
    # Build a mapping: for each daily row, find which SPF date was used
    spf_date_map = pd.merge_asof(
        daily_sorted[["date"]],
        infl_sorted.rename(columns={"date": "spf_date"}),
        left_on="date",
        right_on="spf_date",
        direction="backward",
    )
    staleness = (spf_date_map["date"] - spf_date_map["spf_date"]).dt.days
    stale_mask = staleness > ffill_limit

    # NaN out stale values
    daily_sorted.loc[stale_mask, "eu_inflation_expectations_5y"] = float("nan")

    # Drop rows where forward-fill limit was exceeded (NaN remains)
    before_count = len(daily_sorted)
    daily_sorted = daily_sorted.dropna(subset=["eu_inflation_expectations_5y"])
    dropped = before_count - len(daily_sorted)
    if dropped > 0:
        warnings.warn(
            f"Dropped {dropped} rows where SPF forward-fill limit ({ffill_limit} days) was exceeded.",
            stacklevel=3,
        )

    return daily_sorted


def _validate_rows(df: pd.DataFrame) -> None:
    """Validează fiecare rând prin RealRateDifferentialRow Pydantic model."""
    for row in df.to_dict(orient="records"):
        RealRateDifferentialRow.model_validate(row)


def save_real_rate_differential_parquet(
    df: pd.DataFrame,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> Path:
    """Salvează DataFrame-ul în format Parquet.

    Returns:
        Path-ul fișierului scris

    Raises:
        ValueError: dacă lipsesc coloane obligatorii
    """
    required_cols = {
        "date",
        "us_5y_real",
        "eu_5y_nominal_aaa",
        "eu_inflation_expectations_5y",
        "eu_5y_real",
        "real_rate_differential",
    }
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame-ul lipsește coloanele: {missing}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)
    return output_path


def run_real_rate_differential_pipeline(
    start: datetime = DEFAULT_START_DATE,
    end: Optional[datetime] = None,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> Path:
    """Pipeline complet: fetch all sources + compute + validate + save."""
    df = compute_real_rate_differential(start=start, end=end)
    return save_real_rate_differential_parquet(df, output_path=output_path)
