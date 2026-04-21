"""PRD-300 / CC-1.5.5 — tests for master alignment table."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from macro_context_reader.divergence.alignment import (
    SCORE_COLS,
    aggregate_minutes_per_meeting,
    align_cleveland_fed_to_meeting,
    align_fedwatch_to_meeting,
    align_real_rate_to_meeting,
    build_master_alignment_table,
    get_minutes_lag_per_meeting,
)


# --- synthetic fixtures ---


def _synth_minutes(dates, htm_scores, pdf_scores):
    """Build a synthetic df_nlp with paired HTML+PDF minutes rows."""
    rows = []
    for d, htm, pdf in zip(dates, htm_scores, pdf_scores):
        if htm is not None:
            rows.append({
                "date": pd.Timestamp(d),
                "doc_type": "minutes",
                "doc_url": f"https://example.com/fomcminutes{pd.Timestamp(d).strftime('%Y%m%d')}.htm",
                "ensemble_net": htm,
                "fomc_roberta_net": htm,
                "llama_deepinfra_net": htm,
            })
        if pdf is not None:
            rows.append({
                "date": pd.Timestamp(d),
                "doc_type": "minutes",
                "doc_url": f"https://example.com/fomcminutes{pd.Timestamp(d).strftime('%Y%m%d')}.pdf",
                "ensemble_net": pdf,
                "fomc_roberta_net": pdf,
                "llama_deepinfra_net": pdf,
            })
    return pd.DataFrame(rows)


# ============================================================
# TestAggregateMinutes
# ============================================================


class TestAggregateMinutes:
    def test_correlation_computation(self):
        dates = ["2022-01-26", "2022-03-16", "2022-05-04", "2022-06-15", "2022-07-27"]
        htm = [0.1, 0.2, 0.3, 0.4, 0.5]
        pdf = [0.11, 0.19, 0.31, 0.39, 0.51]
        df = _synth_minutes(dates, htm, pdf)
        _, diag = aggregate_minutes_per_meeting(df, correlation_threshold=0.85)
        assert diag["correlation_html_pdf"] > 0.99
        assert diag["n_meetings_with_both"] == 5

    def test_average_when_corr_above_threshold(self):
        dates = ["2022-01-26", "2022-03-16", "2022-05-04", "2022-06-15"]
        htm = [0.1, 0.2, 0.3, 0.4]
        pdf = [0.2, 0.3, 0.4, 0.5]
        df = _synth_minutes(dates, htm, pdf)
        result, diag = aggregate_minutes_per_meeting(df, correlation_threshold=0.85)
        assert diag["strategy_used"] == "averaged"
        np.testing.assert_allclose(result["ensemble_net"].values, [0.15, 0.25, 0.35, 0.45])

    def test_fallback_when_corr_below_threshold(self):
        dates = ["2022-01-26", "2022-03-16", "2022-05-04", "2022-06-15"]
        htm = [0.1, 0.2, 0.3, 0.4]
        pdf = [0.5, -0.1, 0.6, -0.3]
        df = _synth_minutes(dates, htm, pdf)
        result, diag = aggregate_minutes_per_meeting(df, correlation_threshold=0.85)
        assert diag["strategy_used"] == "html_fallback"
        np.testing.assert_allclose(result["ensemble_net"].values, htm)

    def test_handles_meetings_with_only_one_format(self):
        # Four meetings with both formats (enables correlation above threshold)
        # + one HTML-only + one PDF-only. Averaged mode should carry all through.
        dates = [
            "2022-01-26", "2022-03-16", "2022-05-04", "2022-06-15",
            "2022-07-27", "2022-09-21",
        ]
        htm = [0.1, 0.2, 0.3, 0.4, 0.5, None]
        pdf = [0.11, 0.19, 0.31, 0.39, None, 0.61]
        df = _synth_minutes(dates, htm, pdf)
        result, diag = aggregate_minutes_per_meeting(df, correlation_threshold=0.85)
        assert diag["strategy_used"] == "averaged"
        assert diag["n_meetings_html_only"] == 1
        assert diag["n_meetings_pdf_only"] == 1
        assert not result["ensemble_net"].isna().any()
        # HTML-only meeting uses HTML score; PDF-only uses PDF score (via skipna mean)
        assert result.loc[pd.Timestamp("2022-07-27"), "ensemble_net"] == pytest.approx(0.5)
        assert result.loc[pd.Timestamp("2022-09-21"), "ensemble_net"] == pytest.approx(0.61)

    def test_diagnostic_dict_schema(self):
        df = _synth_minutes(["2022-01-26", "2022-03-16"], [0.1, 0.2], [0.11, 0.19])
        _, diag = aggregate_minutes_per_meeting(df)
        expected = {
            "correlation_html_pdf",
            "n_meetings_with_both",
            "n_meetings_html_only",
            "n_meetings_pdf_only",
            "strategy_used",
            "per_meeting_discrepancy",
        }
        assert set(diag.keys()) == expected


# ============================================================
# TestMinutesLag
# ============================================================


class TestMinutesLag:
    def _aggregated(self):
        return pd.DataFrame(
            {
                "ensemble_net": [0.1, 0.2, 0.3, 0.4],
                "fomc_roberta_net": [0.1, 0.2, 0.3, 0.4],
                "llama_deepinfra_net": [0.1, 0.2, 0.3, 0.4],
            },
            index=pd.DatetimeIndex(
                ["2022-01-26", "2022-03-16", "2022-05-04", "2022-06-15"],
                name="meeting_date",
            ),
        )

    def test_first_meeting_has_nan_lag(self):
        agg = self._aggregated()
        fomc = pd.to_datetime(["2022-01-26", "2022-03-16", "2022-05-04"])
        result = get_minutes_lag_per_meeting(agg, list(fomc))
        first = result.iloc[0]
        for c in SCORE_COLS:
            assert pd.isna(first[f"minutes_lag_{c}"])
        assert pd.isna(first["minutes_lag_source_date"])

    def test_subsequent_meetings_reference_previous(self):
        agg = self._aggregated()
        fomc = pd.to_datetime(["2022-01-26", "2022-03-16", "2022-05-04", "2022-06-15"])
        result = get_minutes_lag_per_meeting(agg, list(fomc))
        assert result.loc[pd.Timestamp("2022-03-16"), "minutes_lag_ensemble_net"] == 0.1
        assert result.loc[pd.Timestamp("2022-05-04"), "minutes_lag_ensemble_net"] == 0.2
        assert result.loc[pd.Timestamp("2022-06-15"), "minutes_lag_ensemble_net"] == 0.3

    def test_source_date_correctness(self):
        agg = self._aggregated()
        fomc = pd.to_datetime(["2022-03-16", "2022-05-04"])
        result = get_minutes_lag_per_meeting(agg, list(fomc))
        assert result.loc[pd.Timestamp("2022-03-16"), "minutes_lag_source_date"] == pd.Timestamp("2022-01-26")
        assert result.loc[pd.Timestamp("2022-05-04"), "minutes_lag_source_date"] == pd.Timestamp("2022-03-16")


# ============================================================
# TestRealRateAlignment
# ============================================================


class TestRealRateAlignment:
    def _daily(self, start="2022-01-01", end="2022-03-31"):
        dates = pd.date_range(start, end, freq="B")
        return pd.DataFrame(
            {"date": dates, "real_rate_differential": np.linspace(1.0, 2.0, len(dates))}
        )

    def test_uses_t_minus_1_business_day(self):
        df = self._daily()
        wed = pd.Timestamp("2022-03-16")
        tue = pd.Timestamp("2022-03-15")
        expected_val = float(df.set_index("date").loc[tue, "real_rate_differential"])
        result = align_real_rate_to_meeting(df, [wed])
        assert result.loc[wed, "real_rate_diff_source_date"] == tue
        assert result.loc[wed, "real_rate_diff_5y"] == pytest.approx(expected_val)

    def test_walks_back_on_weekend_fomc(self):
        df = self._daily()
        monday = pd.Timestamp("2022-03-14")
        result = align_real_rate_to_meeting(df, [monday])
        src = result.loc[monday, "real_rate_diff_source_date"]
        assert src.weekday() < 5
        assert src < monday

    def test_returns_nan_when_no_data_in_window(self):
        df = pd.DataFrame({
            "date": [pd.Timestamp("2022-01-03")],
            "real_rate_differential": [1.0],
        })
        result = align_real_rate_to_meeting(df, [pd.Timestamp("2022-03-16")])
        assert pd.isna(result.iloc[0]["real_rate_diff_5y"])
        assert pd.isna(result.iloc[0]["real_rate_diff_source_date"])

    def test_source_date_column_present(self):
        df = self._daily()
        result = align_real_rate_to_meeting(df, [pd.Timestamp("2022-03-16")])
        assert "real_rate_diff_5y" in result.columns
        assert "real_rate_diff_source_date" in result.columns


# ============================================================
# TestClevelandAlignment
# ============================================================


class TestClevelandAlignment:
    def _cleveland(self):
        return pd.DataFrame({
            "publication_date": pd.to_datetime([
                "2022-01-01", "2022-02-01", "2022-03-01", "2022-03-16",
            ]),
            "national_score": [1.0, 2.0, 3.0, 4.0],
            "consensus_score": [1.1, 2.1, 3.1, 4.1],
            "national_consensus_divergence": [-0.1, -0.1, -0.1, -0.1],
        })

    def test_uses_strictly_prior_publication_date(self):
        df = self._cleveland()
        T = pd.Timestamp("2022-03-16")
        result = align_cleveland_fed_to_meeting(df, [T])
        # pub on 2022-03-16 must NOT be used (strict <)
        assert result.loc[T, "cleveland_source_date"] == pd.Timestamp("2022-03-01")
        assert result.loc[T, "cleveland_national_score"] == 3.0

    def test_forward_fills_from_most_recent(self):
        df = self._cleveland()
        T = pd.Timestamp("2022-04-10")
        result = align_cleveland_fed_to_meeting(df, [T])
        assert result.loc[T, "cleveland_source_date"] == pd.Timestamp("2022-03-16")
        assert result.loc[T, "cleveland_national_score"] == 4.0

    def test_handles_early_2021_edge(self):
        df = self._cleveland()
        T = pd.Timestamp("2021-06-01")
        result = align_cleveland_fed_to_meeting(df, [T])
        assert pd.isna(result.loc[T, "cleveland_national_score"])
        assert pd.isna(result.loc[T, "cleveland_source_date"])


# ============================================================
# TestFedWatchAlignment
# ============================================================


class TestFedWatchAlignment:
    def _fw(self):
        idx = pd.DatetimeIndex(
            ["2022-01-26", "2022-03-16", "2022-05-04"], name="meeting_date"
        )
        return pd.DataFrame(
            {
                "market_implied_change_bps": [1.0, 2.0, 3.0],
                "actual_change_bps": [0.0, 25.0, 50.0],
                "surprise_bps": [-1.0, 23.0, 47.0],
                "surprise_zscore": [-0.5, 1.0, 2.0],
            },
            index=idx,
        )

    def test_direct_join(self):
        df_fw = self._fw()
        T = pd.Timestamp("2022-03-16")
        result = align_fedwatch_to_meeting(df_fw, [T])
        assert result.loc[T, "fedwatch_implied_change_bps"] == 2.0
        assert result.loc[T, "fedwatch_surprise_bps"] == 23.0
        assert "fedwatch_surprise_zscore" in result.columns

    def test_missing_fedwatch_flags_nan(self):
        df_fw = self._fw()
        T_unknown = pd.Timestamp("2023-07-26")
        result = align_fedwatch_to_meeting(df_fw, [T_unknown])
        assert pd.isna(result.loc[T_unknown, "fedwatch_implied_change_bps"])


# ============================================================
# TestMasterAlignmentIntegration
# ============================================================


REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_INPUTS = [
    REPO_ROOT / "data/rhetoric/fomc_scores.parquet",
    REPO_ROOT / "data/market_pricing/fedwatch_surprise.parquet",
    REPO_ROOT / "data/market_pricing/real_rate_differential.parquet",
    REPO_ROOT / "data/economic_sentiment/cleveland_fed_indices.parquet",
]
REAL_INPUTS_EXIST = all(p.exists() for p in REAL_INPUTS)


EXPECTED_COLUMNS = [
    "statement_ensemble_net",
    "statement_fomc_roberta_net",
    "statement_llama_deepinfra_net",
    "minutes_lag_ensemble_net",
    "minutes_lag_fomc_roberta_net",
    "minutes_lag_llama_deepinfra_net",
    "minutes_lag_source_date",
    "fedwatch_implied_change_bps",
    "fedwatch_actual_change_bps",
    "fedwatch_surprise_bps",
    "fedwatch_surprise_zscore",
    "real_rate_diff_5y",
    "real_rate_diff_source_date",
    "cleveland_national_score",
    "cleveland_consensus_score",
    "cleveland_divergence",
    "cleveland_source_date",
]


@pytest.mark.skipif(not REAL_INPUTS_EXIST, reason="Real input parquets not available")
class TestMasterAlignmentIntegration:
    @pytest.fixture(scope="class")
    def master(self, tmp_path_factory):
        out = tmp_path_factory.mktemp("align") / "calibration_features.parquet"
        df, diag = build_master_alignment_table(
            nlp_path=REPO_ROOT / "data/rhetoric/fomc_scores.parquet",
            fedwatch_path=REPO_ROOT / "data/market_pricing/fedwatch_surprise.parquet",
            rrd_path=REPO_ROOT / "data/market_pricing/real_rate_differential.parquet",
            cleveland_path=REPO_ROOT / "data/economic_sentiment/cleveland_fed_indices.parquet",
            output_path=out,
        )
        return df, diag

    def test_full_pipeline_from_real_parquets(self, master):
        df, _ = master
        assert len(df) == 42
        assert set(EXPECTED_COLUMNS).issubset(df.columns)
        assert isinstance(df.index, pd.DatetimeIndex)
        assert df.index.is_monotonic_increasing
        for c in ["statement_ensemble_net", "statement_fomc_roberta_net", "statement_llama_deepinfra_net"]:
            assert df[c].isna().sum() == 0
        hiking_start = df.loc[pd.Timestamp("2022-03-16"), "statement_ensemble_net"]
        cutting_start = df.loc[pd.Timestamp("2024-09-18"), "statement_ensemble_net"]
        assert hiking_start > 0, "2022-03-16 (hiking start) statement should be hawkish"
        # 2024-09-18 statement language is near-neutral (action dovish, words balanced);
        # the meaningful check is relative monotonicity: cutting meeting less hawkish
        # than hiking meeting.
        assert cutting_start < hiking_start, (
            f"2024-09-18 statement ({cutting_start:.3f}) should be less hawkish "
            f"than 2022-03-16 hiking start ({hiking_start:.3f})"
        )
        # Sanity: minutes_lag is populated (not NaN) for meetings past the first.
        assert pd.notna(df.loc[pd.Timestamp("2024-09-18"), "minutes_lag_ensemble_net"])
        assert pd.notna(df.loc[pd.Timestamp("2024-09-18"), "minutes_lag_source_date"])

    def test_no_lookahead_bias(self, master):
        df, _ = master
        for T in df.index:
            src_m = df.loc[T, "minutes_lag_source_date"]
            if pd.notna(src_m):
                assert src_m < T, f"minutes_lag source {src_m} not strictly before {T}"
            src_c = df.loc[T, "cleveland_source_date"]
            if pd.notna(src_c):
                assert src_c < T, f"cleveland source {src_c} not strictly before {T}"
            src_r = df.loc[T, "real_rate_diff_source_date"]
            if pd.notna(src_r):
                assert src_r < T, f"real_rate source {src_r} not strictly before {T}"

    def test_schema_matches_specification(self, master):
        df, _ = master
        assert list(df.columns) == EXPECTED_COLUMNS
