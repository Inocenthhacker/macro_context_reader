"""Master alignment table — join 4 features on canonical FOMC dates.

PRD-300 / CC-1.5.5. Produces the calibration input used by CC-2.

Methodology (per central-bank event-study literature):
- Minutes HTML + PDF scored separately, then aggregated by correlation-gated
  averaging (avg when HTML/PDF corr ≥ threshold, else HTML-only fallback).
- Statement = current meeting; minutes-lag = previous meeting (strict < T)
  to avoid look-ahead bias (minutes for meeting T are released ~3 weeks later).
- Real rate differential sampled at T-1 business day (pre-announcement; see
  Aruoba & Drechsel 2024 on FOMC-day contamination).
- Cleveland Fed sentiment forward-filled from strictly prior publication_date.
- FedWatch joined directly (already per-meeting).
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from macro_context_reader.utils.canonical_fomc_dates import FOMC_MEETING_DATES

logger = logging.getLogger(__name__)

SCORE_COLS = ["ensemble_net", "fomc_roberta_net", "llama_deepinfra_net"]


def aggregate_minutes_per_meeting(
    df_nlp: pd.DataFrame,
    correlation_threshold: float = 0.85,
) -> tuple[pd.DataFrame, dict]:
    """Aggregate HTML + PDF minutes per meeting via correlation-gated averaging.

    Returns (per-meeting aggregated scores indexed on meeting date, diagnostic dict).
    """
    minutes = df_nlp[df_nlp["doc_type"] == "minutes"].copy()
    minutes["date"] = pd.to_datetime(minutes["date"]).dt.normalize()
    minutes["format"] = minutes["doc_url"].str.extract(r"\.(htm|pdf)$", expand=False)

    pivoted = minutes.pivot_table(
        index="date",
        columns="format",
        values=SCORE_COLS,
        aggfunc="first",
    )

    has_htm = ("ensemble_net", "htm") in pivoted.columns
    has_pdf = ("ensemble_net", "pdf") in pivoted.columns

    if has_htm and has_pdf:
        both_valid = pivoted[("ensemble_net", "htm")].notna() & pivoted[("ensemble_net", "pdf")].notna()
        n_both = int(both_valid.sum())
        if n_both >= 2:
            corr = float(
                pivoted.loc[both_valid, ("ensemble_net", "htm")]
                .corr(pivoted.loc[both_valid, ("ensemble_net", "pdf")])
            )
        else:
            corr = float("nan")
        n_htm_only = int((pivoted[("ensemble_net", "htm")].notna() & pivoted[("ensemble_net", "pdf")].isna()).sum())
        n_pdf_only = int((pivoted[("ensemble_net", "htm")].isna() & pivoted[("ensemble_net", "pdf")].notna()).sum())
        discrepancy = (
            pivoted[("ensemble_net", "htm")] - pivoted[("ensemble_net", "pdf")]
        ).abs()
    else:
        corr = float("nan")
        n_both = 0
        n_htm_only = int(pivoted[("ensemble_net", "htm")].notna().sum()) if has_htm else 0
        n_pdf_only = int(pivoted[("ensemble_net", "pdf")].notna().sum()) if has_pdf else 0
        discrepancy = pd.Series(dtype=float)

    use_average = (not pd.isna(corr)) and (corr >= correlation_threshold)
    strategy = "averaged" if use_average else "html_fallback"
    if not use_average:
        logger.warning(
            "Minutes HTML/PDF correlation=%s below threshold=%.2f; falling back to HTML-only",
            f"{corr:.3f}" if not pd.isna(corr) else "n/a",
            correlation_threshold,
        )

    result = pd.DataFrame(index=pivoted.index)
    for col in SCORE_COLS:
        htm_key = (col, "htm")
        pdf_key = (col, "pdf")
        if use_average and htm_key in pivoted.columns and pdf_key in pivoted.columns:
            result[col] = pivoted[[htm_key, pdf_key]].mean(axis=1, skipna=True)
        elif htm_key in pivoted.columns:
            result[col] = pivoted[htm_key]
        elif pdf_key in pivoted.columns:
            result[col] = pivoted[pdf_key]
        else:
            result[col] = float("nan")

    result = result.sort_index()
    result.index.name = "meeting_date"

    diag = {
        "correlation_html_pdf": corr,
        "n_meetings_with_both": n_both,
        "n_meetings_html_only": n_htm_only,
        "n_meetings_pdf_only": n_pdf_only,
        "strategy_used": strategy,
        "per_meeting_discrepancy": discrepancy,
    }
    return result, diag


def get_minutes_lag_per_meeting(
    minutes_aggregated: pd.DataFrame,
    canonical_fomc_dates: list,
) -> pd.DataFrame:
    """For each FOMC date T, return minutes scores from the most recent prior meeting.

    Strict inequality (< T) — avoids look-ahead bias since minutes for meeting T
    are published ~3 weeks after T.
    """
    ma = minutes_aggregated.sort_index()
    rows = []
    for raw_t in canonical_fomc_dates:
        T = pd.Timestamp(raw_t).normalize()
        prior = ma[ma.index < T]
        row = {"meeting_date": T}
        if len(prior) == 0:
            for c in SCORE_COLS:
                row[f"minutes_lag_{c}"] = float("nan")
            row["minutes_lag_source_date"] = pd.NaT
        else:
            last = prior.iloc[-1]
            for c in SCORE_COLS:
                row[f"minutes_lag_{c}"] = float(last[c]) if pd.notna(last[c]) else float("nan")
            row["minutes_lag_source_date"] = prior.index[-1]
        rows.append(row)
    return pd.DataFrame(rows).set_index("meeting_date")


def align_real_rate_to_meeting(
    df_rrd: pd.DataFrame,
    fomc_dates: list,
    lookback_business_days: int = 1,
) -> pd.DataFrame:
    """Sample real_rate_differential at T - lookback_business_days; walk back on gaps.

    Pre-announcement sampling avoids contamination from the meeting outcome itself.
    Walks back up to 5 additional business days if the initial target is missing/NaN.
    """
    rrd = df_rrd.copy()
    rrd["date"] = pd.to_datetime(rrd["date"]).dt.normalize()
    rrd = rrd.set_index("date").sort_index()
    series = rrd["real_rate_differential"]

    rows = []
    max_additional_walks = 5
    for raw_t in fomc_dates:
        T = pd.Timestamp(raw_t).normalize()
        target = T - pd.offsets.BusinessDay(lookback_business_days)
        val = series.get(target, float("nan"))
        walks = 0
        while pd.isna(val) and walks < max_additional_walks:
            target = target - pd.offsets.BusinessDay(1)
            val = series.get(target, float("nan"))
            walks += 1
        if pd.isna(val):
            rows.append({
                "meeting_date": T,
                "real_rate_diff_5y": float("nan"),
                "real_rate_diff_source_date": pd.NaT,
            })
        else:
            rows.append({
                "meeting_date": T,
                "real_rate_diff_5y": float(val),
                "real_rate_diff_source_date": target,
            })
    return pd.DataFrame(rows).set_index("meeting_date")


def align_cleveland_fed_to_meeting(
    df_cf: pd.DataFrame,
    fomc_dates: list,
) -> pd.DataFrame:
    """Forward-fill latest Cleveland Fed sentiment with publication_date strictly before T."""
    cf = df_cf.copy()
    cf["publication_date"] = pd.to_datetime(cf["publication_date"]).dt.normalize()
    cf = cf.set_index("publication_date").sort_index()

    rows = []
    for raw_t in fomc_dates:
        T = pd.Timestamp(raw_t).normalize()
        prior = cf[cf.index < T]
        if len(prior) == 0:
            rows.append({
                "meeting_date": T,
                "cleveland_national_score": float("nan"),
                "cleveland_consensus_score": float("nan"),
                "cleveland_divergence": float("nan"),
                "cleveland_source_date": pd.NaT,
            })
        else:
            last = prior.iloc[-1]
            rows.append({
                "meeting_date": T,
                "cleveland_national_score": float(last["national_score"]) if pd.notna(last.get("national_score")) else float("nan"),
                "cleveland_consensus_score": float(last["consensus_score"]) if pd.notna(last.get("consensus_score")) else float("nan"),
                "cleveland_divergence": float(last["national_consensus_divergence"]) if pd.notna(last.get("national_consensus_divergence")) else float("nan"),
                "cleveland_source_date": prior.index[-1],
            })
    return pd.DataFrame(rows).set_index("meeting_date")


def align_fedwatch_to_meeting(
    df_fw: pd.DataFrame,
    fomc_dates: list,
) -> pd.DataFrame:
    """FedWatch is already per-meeting — direct join on canonical FOMC date."""
    fw = df_fw.copy()
    if not isinstance(fw.index, pd.DatetimeIndex):
        fw.index = pd.to_datetime(fw.index)
    fw.index = fw.index.normalize()

    target = pd.DatetimeIndex([pd.Timestamp(d).normalize() for d in fomc_dates], name="meeting_date")
    out = fw.reindex(target)
    out = out.rename(columns={
        "market_implied_change_bps": "fedwatch_implied_change_bps",
        "actual_change_bps": "fedwatch_actual_change_bps",
        "surprise_bps": "fedwatch_surprise_bps",
        "surprise_zscore": "fedwatch_surprise_zscore",
    })
    out.index.name = "meeting_date"
    return out[[
        "fedwatch_implied_change_bps",
        "fedwatch_actual_change_bps",
        "fedwatch_surprise_bps",
        "fedwatch_surprise_zscore",
    ]]


def build_master_alignment_table(
    nlp_path: Path = Path("data/rhetoric/fomc_scores.parquet"),
    fedwatch_path: Path = Path("data/market_pricing/fedwatch_surprise.parquet"),
    rrd_path: Path = Path("data/market_pricing/real_rate_differential.parquet"),
    cleveland_path: Path = Path("data/economic_sentiment/cleveland_fed_indices.parquet"),
    output_path: Path = Path("data/divergence/calibration_features.parquet"),
    correlation_threshold: float = 0.85,
) -> tuple[pd.DataFrame, dict]:
    """Build and persist the master alignment table.

    Output index: canonical FOMC meeting dates that have statement NLP scores (2021+).
    """
    nlp_path = Path(nlp_path)
    fedwatch_path = Path(fedwatch_path)
    rrd_path = Path(rrd_path)
    cleveland_path = Path(cleveland_path)
    output_path = Path(output_path)

    df_nlp = pd.read_parquet(nlp_path)
    df_fw = pd.read_parquet(fedwatch_path)
    df_rrd = pd.read_parquet(rrd_path)
    df_cf = pd.read_parquet(cleveland_path)

    df_nlp = df_nlp.copy()
    df_nlp["date"] = pd.to_datetime(df_nlp["date"]).dt.normalize()

    stmt_full = df_nlp[df_nlp["doc_type"] == "statement"][["date"] + SCORE_COLS].copy()
    stmt_dates = set(stmt_full["date"].unique())

    fomc_cutoff = pd.Timestamp("2021-01-01")
    fomc_dates = sorted(
        d for d in FOMC_MEETING_DATES
        if d >= fomc_cutoff and d in stmt_dates
    )
    logger.info("Master alignment: %d FOMC meetings with NLP statement data", len(fomc_dates))

    minutes_agg, minutes_diag = aggregate_minutes_per_meeting(
        df_nlp, correlation_threshold=correlation_threshold
    )

    stmt = stmt_full.set_index("date").sort_index()
    stmt = stmt.rename(columns={c: f"statement_{c}" for c in SCORE_COLS})

    minutes_lag_df = get_minutes_lag_per_meeting(minutes_agg, fomc_dates)
    fw_df = align_fedwatch_to_meeting(df_fw, fomc_dates)
    rr_df = align_real_rate_to_meeting(df_rrd, fomc_dates)
    cf_df = align_cleveland_fed_to_meeting(df_cf, fomc_dates)

    idx = pd.DatetimeIndex(fomc_dates, name="meeting_date")
    master = pd.DataFrame(index=idx)

    for c in ["statement_ensemble_net", "statement_fomc_roberta_net", "statement_llama_deepinfra_net"]:
        master[c] = stmt[c].reindex(idx)
    for c in ["minutes_lag_ensemble_net", "minutes_lag_fomc_roberta_net", "minutes_lag_llama_deepinfra_net", "minutes_lag_source_date"]:
        master[c] = minutes_lag_df[c].reindex(idx)
    for c in ["fedwatch_implied_change_bps", "fedwatch_actual_change_bps", "fedwatch_surprise_bps", "fedwatch_surprise_zscore"]:
        master[c] = fw_df[c].reindex(idx)
    for c in ["real_rate_diff_5y", "real_rate_diff_source_date"]:
        master[c] = rr_df[c].reindex(idx)
    for c in ["cleveland_national_score", "cleveland_consensus_score", "cleveland_divergence", "cleveland_source_date"]:
        master[c] = cf_df[c].reindex(idx)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    master.to_parquet(output_path)

    per_meeting_disc = minutes_diag["per_meeting_discrepancy"]
    diagnostics = {
        "n_rows": int(len(master)),
        "n_columns": int(master.shape[1]),
        "date_range_start": str(master.index.min().date()) if len(master) else None,
        "date_range_end": str(master.index.max().date()) if len(master) else None,
        "minutes_correlation_html_pdf": minutes_diag["correlation_html_pdf"],
        "minutes_aggregation_strategy": minutes_diag["strategy_used"],
        "minutes_n_meetings_both_formats": minutes_diag["n_meetings_with_both"],
        "minutes_n_meetings_html_only": minutes_diag["n_meetings_html_only"],
        "minutes_n_meetings_pdf_only": minutes_diag["n_meetings_pdf_only"],
        "minutes_discrepancy_mean": float(per_meeting_disc.mean()) if len(per_meeting_disc) else float("nan"),
        "minutes_discrepancy_max": float(per_meeting_disc.max()) if len(per_meeting_disc) else float("nan"),
        "null_counts_per_column": {k: int(v) for k, v in master.isna().sum().to_dict().items()},
        "output_path": str(output_path),
    }
    return master, diagnostics
