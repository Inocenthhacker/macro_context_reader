"""Custom FedWatch probability calculator -- CME Group methodology.

Implements the CME FedWatch Tool methodology (Arthur Lobao, CME Group 2023)
directly on our ZQ continuous futures chain cache. Zero dependency on pyfedwatch.

Core formula for meeting month with N days before meeting, M days after:
  EFFR(Avg) = 100 - futures_price
  EFFR(Start) = ((N+M) * EFFR_avg - M * EFFR_end) / N
  Expected change = EFFR(End) - EFFR(Start)
  Decompose into P(floor*25bps) and P((floor+1)*25bps)

Chain propagation: when consecutive months have FOMC meetings, backward-chain
from the nearest forward anchor month (no FOMC) through intermediate meetings.

PRD-300 / CC-1.5.2b-IMPL-2
"""
from __future__ import annotations

import calendar
import logging
import math
import os

import numpy as np
import pandas as pd
from dotenv import load_dotenv

from ...utils.canonical_fomc_dates import FOMC_MEETING_DATES
from .zq_futures import FRONT_MONTHS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------


def implied_avg_effr(chain_close: float) -> float:
    """Convert ZQ futures settlement price to implied average EFFR (pct points).

    Example: close = 94.87 -> implied rate = 5.13%.
    """
    return 100.0 - chain_close


def days_before_after_meeting(meeting_date: pd.Timestamp) -> tuple[int, int]:
    """Days (N, M) in meeting month split by meeting day.

    N = meeting_date.day  (days 1..D at pre-meeting rate, inclusive)
    M = days_in_month - D (days D+1..end at post-meeting rate)
    """
    meeting_date = pd.Timestamp(meeting_date)
    day = meeting_date.day
    days_in_month = calendar.monthrange(meeting_date.year, meeting_date.month)[1]
    return (day, days_in_month - day)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fomc_months_set() -> set[tuple[int, int]]:
    """Set of (year, month) pairs containing at least one canonical FOMC meeting."""
    return {(d.year, d.month) for d in FOMC_MEETING_DATES}


def _month_offset(from_date: pd.Timestamp, to_year: int, to_month: int) -> int:
    """Number of months from *from_date*'s month to (*to_year*, *to_month*)."""
    return (to_year - from_date.year) * 12 + (to_month - from_date.month)


def _get_chain_close(
    chains: dict[int, pd.DataFrame], offset: int, watch_date: pd.Timestamp
) -> float:
    """Most recent close price for ``chains[offset]`` on or before *watch_date*."""
    if offset < 0 or offset >= FRONT_MONTHS:
        raise ValueError(f"Chain offset {offset} out of range [0, {FRONT_MONTHS})")
    chain = chains[offset]
    available = chain.loc[:watch_date]
    if len(available) == 0:
        raise ValueError(
            f"No data for chain offset {offset} on or before {watch_date.date()}"
        )
    return float(available.iloc[-1]["close"])


# ---------------------------------------------------------------------------
# Core CME methodology
# ---------------------------------------------------------------------------


def compute_meeting_probability(
    watch_date,
    meeting_date,
    chains: dict[int, pd.DataFrame],
) -> dict:
    """Compute FOMC rate-change probability using the CME FedWatch methodology.

    Steps:
      1. Identify meeting month and forward anchor (first no-FOMC month after).
      2. Build month chain from meeting month to anchor (inclusive).
      3. Read EFFR(Avg) for each month from ZQ chains at *watch_date*.
      4. Backward-chain from anchor: propagate EFFR(End)/EFFR(Start) through
         intermediate FOMC months until the target meeting month.
      5. Decompose expected change into binary 25 bps probability buckets.

    Returns dict with keys: meeting_date, watch_date, effr_start, effr_end,
    expected_change_bps, implied_move_25bps, prob_lower, prob_upper,
    lower_move_bps, upper_move_bps, market_implied_change_bps.
    """
    watch_date = pd.Timestamp(watch_date).normalize()
    meeting_date = pd.Timestamp(meeting_date).normalize()

    fomc_months = _fomc_months_set()

    # Reject months with multiple FOMC meetings (March 2020 emergency)
    meetings_in_target_month = [
        d
        for d in FOMC_MEETING_DATES
        if d.year == meeting_date.year and d.month == meeting_date.month
    ]
    if len(meetings_in_target_month) > 1:
        raise ValueError(
            f"Multiple FOMC meetings in {meeting_date.strftime('%Y-%m')}: "
            f"{[d.date() for d in meetings_in_target_month]}. "
            "CME methodology not applicable for multi-meeting months."
        )

    # ---- find forward anchor: first month after meeting with no FOMC -------
    base = pd.Timestamp(year=meeting_date.year, month=meeting_date.month, day=1)
    anchor_ts = None
    for delta in range(1, FRONT_MONTHS):
        candidate = base + pd.DateOffset(months=delta)
        if (candidate.year, candidate.month) not in fomc_months:
            anchor_ts = candidate
            break
    if anchor_ts is None:
        raise ValueError(
            f"No forward anchor month within {FRONT_MONTHS} months of "
            f"{meeting_date.date()}"
        )

    # ---- build month chain [meeting_month, ..., anchor_month] --------------
    months_chain: list[dict] = []
    cur = base
    while cur <= anchor_ts:
        offset = _month_offset(watch_date, cur.year, cur.month)
        if offset < 0 or offset >= FRONT_MONTHS:
            raise ValueError(
                f"Chain offset {offset} for {cur.year}-{cur.month:02d} "
                f"out of range at watch_date {watch_date.date()}"
            )
        is_anchor = cur.year == anchor_ts.year and cur.month == anchor_ts.month
        has_fomc = (cur.year, cur.month) in fomc_months and not is_anchor
        months_chain.append(
            {
                "year": cur.year,
                "month": cur.month,
                "chain_offset": offset,
                "has_fomc": has_fomc,
                "is_anchor": is_anchor,
            }
        )
        cur = cur + pd.DateOffset(months=1)

    # ---- read EFFR(Avg) for every month in the chain ----------------------
    for m in months_chain:
        close = _get_chain_close(chains, m["chain_offset"], watch_date)
        m["effr_avg"] = implied_avg_effr(close)

    # ---- anchor: constant rate (no meeting) --------------------------------
    anchor = months_chain[-1]
    anchor["effr_start"] = anchor["effr_avg"]
    anchor["effr_end"] = anchor["effr_avg"]

    # ---- backward-chain from anchor to meeting month -----------------------
    for i in range(len(months_chain) - 2, -1, -1):
        m = months_chain[i]
        m_next = months_chain[i + 1]

        # Rate continuity: end of this month = start of next month
        m["effr_end"] = m_next["effr_start"]

        if m["has_fomc"]:
            # Solve for EFFR(Start): avg = (N*start + M*end) / T
            mtgs = [
                d
                for d in FOMC_MEETING_DATES
                if d.year == m["year"] and d.month == m["month"]
            ]
            if len(mtgs) != 1:
                raise ValueError(
                    f"Expected 1 FOMC meeting in {m['year']}-{m['month']:02d}, "
                    f"found {len(mtgs)}"
                )
            n, big_m = days_before_after_meeting(mtgs[0])
            total = n + big_m
            if n == 0:
                raise ValueError(f"N=0 for meeting {mtgs[0].date()}")
            m["effr_start"] = (total * m["effr_avg"] - big_m * m["effr_end"]) / n
        else:
            # No meeting: rate constant through the month
            m["effr_start"] = m["effr_end"]

    # ---- extract target meeting results ------------------------------------
    target = months_chain[0]
    effr_start = target["effr_start"]
    effr_end = target["effr_end"]

    expected_change = effr_end - effr_start
    expected_change_bps = expected_change * 100.0

    # ---- decompose into 25 bps probability buckets -------------------------
    num_moves = expected_change / 0.25
    floor_moves = math.floor(num_moves)
    remainder = num_moves - floor_moves

    prob_upper = remainder  # P((floor+1) * 25bps)
    prob_lower = 1.0 - remainder  # P(floor     * 25bps)

    lower_move_bps = floor_moves * 25.0
    upper_move_bps = (floor_moves + 1) * 25.0

    market_implied_change_bps = prob_lower * lower_move_bps + prob_upper * upper_move_bps

    return {
        "meeting_date": meeting_date,
        "watch_date": watch_date,
        "effr_start": effr_start,
        "effr_end": effr_end,
        "expected_change_bps": expected_change_bps,
        "implied_move_25bps": num_moves,
        "prob_lower": prob_lower,
        "prob_upper": prob_upper,
        "lower_move_bps": lower_move_bps,
        "upper_move_bps": upper_move_bps,
        "market_implied_change_bps": market_implied_change_bps,
    }


# ---------------------------------------------------------------------------
# Batch computation
# ---------------------------------------------------------------------------


def compute_all_meetings(
    start_date: str,
    end_date: str,
    chains: dict[int, pd.DataFrame],
) -> pd.DataFrame:
    """Compute rate-change probabilities for all FOMC meetings in range.

    For each meeting, *watch_date* = T-1 business day.  Meetings that cannot
    be computed (before chain data, multi-meeting months, chain offset overflow)
    are silently skipped with a log warning.
    """
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)

    meetings = FOMC_MEETING_DATES[
        (FOMC_MEETING_DATES >= start) & (FOMC_MEETING_DATES <= end)
    ]

    results: list[dict] = []
    for meeting_date in meetings:
        watch_date = meeting_date - pd.offsets.BDay(1)

        if watch_date < pd.Timestamp("2010-06-07"):
            logger.debug("Skip %s: before chain data start", meeting_date.date())
            continue

        try:
            result = compute_meeting_probability(watch_date, meeting_date, chains)
            results.append(result)
        except (ValueError, KeyError) as exc:
            logger.warning("Skip %s: %s", meeting_date.date(), exc)
            continue

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results).set_index("meeting_date")
    df.index = pd.DatetimeIndex(df.index)
    return df.sort_index()


# ---------------------------------------------------------------------------
# Actual Fed rate decisions from FRED
# ---------------------------------------------------------------------------


def _get_fred_client():
    """Initialise FRED client from .env; fail loudly if key is missing."""
    load_dotenv()
    from fredapi import Fred

    key = os.environ.get("FRED_API_KEY")
    if not key or key.startswith("REPLACE_") or key == "your_fred_api_key_here":
        raise ValueError(
            "FRED_API_KEY not configured. "
            "Add to .env or shell environment."
        )
    return Fred(api_key=key)


def fetch_actual_fed_rate_decisions() -> pd.DataFrame:
    """Fetch actual FOMC rate decisions from FRED DFEDTARU (upper target).

    For each canonical FOMC meeting (2010-present), compares the target rate
    before and after the meeting to determine the actual change in basis points.
    """
    fred = _get_fred_client()

    import time

    # Fetch in 4-year chunks with retry to work around FRED 500 errors
    chunks = []
    start_year = 2009
    end_year = pd.Timestamp.today().year
    for chunk_start in range(start_year, end_year + 1, 4):
        chunk_end = min(chunk_start + 3, end_year)
        for attempt in range(3):
            try:
                s = fred.get_series(
                    "DFEDTARU",
                    observation_start=f"{chunk_start}-01-01",
                    observation_end=f"{chunk_end}-12-31",
                )
                if s is not None and len(s) > 0:
                    chunks.append(s)
                break
            except Exception as exc:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                else:
                    logger.warning(
                        "FRED fetch failed for %d-%d after 3 attempts: %s",
                        chunk_start, chunk_end, exc,
                    )
    if not chunks:
        raise RuntimeError("Could not fetch any DFEDTARU data from FRED")
    upper = pd.concat(chunks).sort_index()
    upper = upper[~upper.index.duplicated(keep="last")]
    upper = upper.dropna()

    # Forward-fill to daily for reliable lookups on any calendar day
    full_idx = pd.date_range(upper.index.min(), upper.index.max(), freq="D")
    upper = upper.reindex(full_idx).ffill()

    results: list[dict] = []
    for meeting_date in FOMC_MEETING_DATES:
        if meeting_date < pd.Timestamp("2010-06-01"):
            continue
        if meeting_date > upper.index.max():
            continue

        # Rate before: value the day before meeting (unambiguously old rate)
        before_date = meeting_date - pd.Timedelta(days=1)
        before_slice = upper.loc[:before_date]
        if len(before_slice) == 0:
            continue
        rate_before = float(before_slice.iloc[-1])

        # Rate after: value 3-7 calendar days later (new rate effective)
        after_start = meeting_date + pd.Timedelta(days=3)
        after_end = meeting_date + pd.Timedelta(days=10)
        after_slice = upper.loc[after_start:after_end]
        rate_after = float(after_slice.iloc[-1]) if len(after_slice) > 0 else rate_before

        results.append(
            {
                "meeting_date": meeting_date,
                "rate_before_pct": rate_before,
                "rate_after_pct": rate_after,
                "actual_change_bps": (rate_after - rate_before) * 100.0,
            }
        )

    df = pd.DataFrame(results).set_index("meeting_date")
    df.index = pd.DatetimeIndex(df.index)
    return df


# ---------------------------------------------------------------------------
# Surprise computation
# ---------------------------------------------------------------------------


def compute_surprise(
    probabilities_df: pd.DataFrame,
    actual_rates_df: pd.DataFrame,
) -> pd.DataFrame:
    """Join probability output with actual decisions to produce surprise series.

    surprise_bps     = actual_change_bps - market_implied_change_bps
    surprise_zscore  = surprise_bps / expanding_std(surprise_bps)
                       (expanding window avoids look-ahead bias)
    """
    merged = probabilities_df[["market_implied_change_bps"]].join(
        actual_rates_df[["actual_change_bps"]], how="inner"
    )

    merged["surprise_bps"] = (
        merged["actual_change_bps"] - merged["market_implied_change_bps"]
    )

    # Expanding z-score (min 2 observations for a valid std)
    exp_std = merged["surprise_bps"].expanding(min_periods=2).std()
    merged["surprise_zscore"] = merged["surprise_bps"] / exp_std
    merged["surprise_zscore"] = merged["surprise_zscore"].fillna(0.0)

    return merged[
        [
            "market_implied_change_bps",
            "actual_change_bps",
            "surprise_bps",
            "surprise_zscore",
        ]
    ]
