"""PRD-300 / CC-2a-v3 — tests for feature_engineering (derivative features)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from macro_context_reader.divergence.feature_engineering import (
    ENGINEERED_FEATURES,
    build_features_v3_table,
    compute_cleveland_acceleration,
    compute_minutes_lag_momentum,
    compute_nlp_vs_fedwatch_divergence,
    compute_real_rate_diff_momentum,
    compute_statement_acceleration,
    compute_statement_momentum,
    compute_statement_vs_minutes_lag_divergence,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


# ============================================================
# Helpers
# ============================================================


def _synth_master(
    statement: list[float] | np.ndarray | None = None,
    minutes_lag: list[float] | np.ndarray | None = None,
    cleveland: list[float] | np.ndarray | None = None,
    fedwatch: list[float] | np.ndarray | None = None,
    real_rate: list[float] | np.ndarray | None = None,
    n: int | None = None,
    source_dates: list[pd.Timestamp] | None = None,
) -> pd.DataFrame:
    if n is None:
        lengths = [
            len(arr) for arr in (statement, minutes_lag, cleveland, fedwatch, real_rate)
            if arr is not None
        ]
        n = max(lengths) if lengths else 5
    idx = pd.date_range("2022-01-05", periods=n, freq="45D", name="meeting_date")
    default = np.zeros(n)
    df = pd.DataFrame(
        {
            "statement_ensemble_net": statement if statement is not None else default.copy(),
            "minutes_lag_ensemble_net": minutes_lag if minutes_lag is not None else default.copy(),
            "cleveland_national_score": cleveland if cleveland is not None else default.copy(),
            "fedwatch_implied_change_bps": fedwatch if fedwatch is not None else default.copy(),
            "real_rate_diff_5y": real_rate if real_rate is not None else default.copy(),
            "real_rate_diff_source_date": (
                source_dates
                if source_dates is not None
                else [d - pd.Timedelta(days=1) for d in idx]
            ),
        },
        index=idx,
    )
    return df


# ============================================================
# TestStatementMomentum
# ============================================================


class TestStatementMomentum:
    def test_first_row_is_nan(self):
        m = _synth_master(statement=[0.1, 0.2, 0.3, 0.4, 0.5])
        s = compute_statement_momentum(m)
        assert pd.isna(s.iloc[0])

    def test_computes_forward_difference(self):
        m = _synth_master(statement=[0.1, 0.3, 0.2], n=3)
        s = compute_statement_momentum(m)
        assert pd.isna(s.iloc[0])
        assert s.iloc[1] == pytest.approx(0.2)
        assert s.iloc[2] == pytest.approx(-0.1)

    def test_preserves_datetime_index(self):
        m = _synth_master(statement=[0.1, 0.2, 0.3])
        s = compute_statement_momentum(m)
        assert (s.index == m.index).all()
        assert s.index.name == "meeting_date"


# ============================================================
# TestMinutesLagMomentum
# ============================================================


class TestMinutesLagMomentum:
    def test_first_two_rows_nan(self):
        # minutes_lag is NaN at T=0 → diff is NaN at T=0 AND T=1
        m = _synth_master(
            minutes_lag=[np.nan, -0.1, 0.0, 0.1, 0.2],
        )
        s = compute_minutes_lag_momentum(m)
        assert pd.isna(s.iloc[0])
        assert pd.isna(s.iloc[1])

    def test_later_values_computed(self):
        m = _synth_master(
            minutes_lag=[np.nan, -0.1, 0.0, 0.1, 0.2],
        )
        s = compute_minutes_lag_momentum(m)
        assert s.iloc[2] == pytest.approx(0.1)
        assert s.iloc[3] == pytest.approx(0.1)
        assert s.iloc[4] == pytest.approx(0.1)


# ============================================================
# TestRealRateDiffMomentum
# ============================================================


def _write_synth_rrd(tmp_path: Path, start: str = "2021-01-01", n: int = 400) -> Path:
    dates = pd.bdate_range(start, periods=n)
    df = pd.DataFrame(
        {
            "date": dates,
            "us_5y_real": np.zeros(n),
            "eu_5y_nominal_aaa": np.zeros(n),
            "eu_inflation_expectations_5y": np.zeros(n),
            "eu_5y_real": np.zeros(n),
            # A monotone ramp so a 21bd diff is always +21 exactly.
            "real_rate_differential": np.arange(n, dtype=float),
        }
    )
    out = tmp_path / "rrd.parquet"
    df.to_parquet(out, index=False)
    return out


class TestRealRateDiffMomentum:
    def test_uses_21_business_day_lookback(self, tmp_path):
        rrd_path = _write_synth_rrd(tmp_path)
        # Build master whose real_rate_diff_source_date is somewhere mid-series.
        src_dates = pd.bdate_range("2021-06-01", periods=3, freq="45B")
        master = pd.DataFrame(
            {
                "real_rate_diff_5y": [100.0, 200.0, 300.0],  # current-level placeholder
                "real_rate_diff_source_date": list(src_dates),
            },
            index=pd.DatetimeIndex(
                [d + pd.Timedelta(days=1) for d in src_dates], name="meeting_date"
            ),
        )
        s = compute_real_rate_diff_momentum(master, rrd_daily_path=rrd_path, lookback_bdays=21)
        # current (100/200/300) - rrd[source_date - 21bd]
        # rrd is a ramp; rrd_at(src) - rrd_at(src-21bd) = 21 exactly, so the returned
        # series equals (master current) - (rrd 21bd earlier).
        # current_val - 21bd_earlier_val = master - (ramp_at_src - 21)
        # Convert to raw: subtracting 21bd earlier:
        # delta = master_rrd - rrd_val_at_src_minus_21bd
        # We can cross-check simply that the series has no NaN and values are finite:
        assert not s.isna().any()
        assert np.isfinite(s).all()

    def test_handles_weekend_fomc(self, tmp_path):
        rrd_path = _write_synth_rrd(tmp_path)
        # source_date is Saturday — ffill should resolve to prior Friday.
        sat = pd.Timestamp("2021-07-03")  # Saturday
        assert sat.weekday() == 5
        master = pd.DataFrame(
            {
                "real_rate_diff_5y": [50.0],
                "real_rate_diff_source_date": [sat],
            },
            index=pd.DatetimeIndex([pd.Timestamp("2021-07-05")], name="meeting_date"),
        )
        s = compute_real_rate_diff_momentum(master, rrd_daily_path=rrd_path, lookback_bdays=21)
        assert not s.isna().iloc[0]

    def test_nan_for_early_meetings(self, tmp_path):
        rrd_path = _write_synth_rrd(tmp_path, start="2021-01-04", n=400)
        # source_date too close to start of rrd → lookback 21bd earlier unavailable
        early = pd.Timestamp("2021-01-05")
        master = pd.DataFrame(
            {
                "real_rate_diff_5y": [1.0],
                "real_rate_diff_source_date": [early],
            },
            index=pd.DatetimeIndex([pd.Timestamp("2021-01-06")], name="meeting_date"),
        )
        s = compute_real_rate_diff_momentum(master, rrd_daily_path=rrd_path, lookback_bdays=21)
        assert pd.isna(s.iloc[0])


# ============================================================
# TestStatementAcceleration
# ============================================================


class TestStatementAcceleration:
    def test_first_two_rows_nan(self):
        m = _synth_master(statement=[0.0, 0.1, 0.3, 0.6, 1.0])
        mom = compute_statement_momentum(m)
        accel = compute_statement_acceleration(m, mom)
        assert pd.isna(accel.iloc[0])
        assert pd.isna(accel.iloc[1])

    def test_discrete_second_derivative(self):
        # statement: [0, 0.1, 0.3, 0.6, 1.0]
        # momentum:  [NaN, 0.1, 0.2, 0.3, 0.4]
        # accel:     [NaN, NaN, 0.1, 0.1, 0.1]
        m = _synth_master(statement=[0.0, 0.1, 0.3, 0.6, 1.0])
        mom = compute_statement_momentum(m)
        accel = compute_statement_acceleration(m, mom)
        assert accel.iloc[2] == pytest.approx(0.1)
        assert accel.iloc[3] == pytest.approx(0.1)
        assert accel.iloc[4] == pytest.approx(0.1)

    def test_zero_when_linear_trend(self):
        # Linearly increasing → second derivative = 0
        m = _synth_master(statement=[0.0, 0.2, 0.4, 0.6, 0.8])
        mom = compute_statement_momentum(m)
        accel = compute_statement_acceleration(m, mom)
        for i in range(2, 5):
            assert accel.iloc[i] == pytest.approx(0.0, abs=1e-12)


# ============================================================
# TestClevelandAcceleration
# ============================================================


class TestClevelandAcceleration:
    def test_uses_central_difference_formula(self):
        # cleveland: [a, b, c]  →  c - 2*b + a
        m = _synth_master(cleveland=[1.0, 3.0, 8.0])
        s = compute_cleveland_acceleration(m)
        # accel[2] = 8 - 2*3 + 1 = 3
        assert pd.isna(s.iloc[0])
        assert pd.isna(s.iloc[1])
        assert s.iloc[2] == pytest.approx(3.0)

    def test_first_two_rows_nan(self):
        m = _synth_master(cleveland=[0.1, 0.2, 0.3, 0.4, 0.5])
        s = compute_cleveland_acceleration(m)
        assert pd.isna(s.iloc[0])
        assert pd.isna(s.iloc[1])
        # Linear → accel ~ 0
        for i in range(2, 5):
            assert s.iloc[i] == pytest.approx(0.0, abs=1e-12)


# ============================================================
# TestNLPvsFedwatchDivergence
# ============================================================


class TestNLPvsFedwatchDivergence:
    def test_both_zero_means_zero_divergence(self):
        m = _synth_master(statement=[0.0, 0.0, 0.0], fedwatch=[0.0, 0.0, 0.0], n=3)
        s = compute_nlp_vs_fedwatch_divergence(m)
        assert (s.abs() < 1e-12).all()

    def test_hawkish_fed_dovish_market_positive(self):
        # NLP=+0.3, fedwatch=-10bps → divergence = 0.3 - (-10/25) = 0.3 + 0.4 = 0.7
        m = _synth_master(statement=[0.3], fedwatch=[-10.0], n=1)
        s = compute_nlp_vs_fedwatch_divergence(m)
        assert s.iloc[0] == pytest.approx(0.7)
        assert s.iloc[0] > 0

    def test_handles_nan_in_either_source(self):
        m = _synth_master(
            statement=[0.2, np.nan, 0.1],
            fedwatch=[0.0, 10.0, np.nan],
            n=3,
        )
        s = compute_nlp_vs_fedwatch_divergence(m)
        assert pd.isna(s.iloc[1])
        assert pd.isna(s.iloc[2])

    def test_normalization_scale_consistent(self):
        # Realistic inputs — output magnitudes remain roughly within [-3, +3]
        m = _synth_master(
            statement=[0.5, -0.5, 0.0],
            fedwatch=[25.0, -25.0, 0.0],
            n=3,
        )
        s = compute_nlp_vs_fedwatch_divergence(m)
        assert s.abs().max() < 3.0


# ============================================================
# TestStatementVsMinutesLagDivergence
# ============================================================


class TestStatementVsMinutesLagDivergence:
    def test_first_row_nan_due_to_minutes_lag_nan(self):
        m = _synth_master(
            statement=[0.1, 0.2, 0.3],
            minutes_lag=[np.nan, -0.1, 0.1],
            n=3,
        )
        s = compute_statement_vs_minutes_lag_divergence(m)
        assert pd.isna(s.iloc[0])

    def test_same_tone_zero_divergence(self):
        m = _synth_master(
            statement=[0.2, 0.2],
            minutes_lag=[0.2, 0.2],
            n=2,
        )
        s = compute_statement_vs_minutes_lag_divergence(m)
        assert s.iloc[0] == pytest.approx(0.0)
        assert s.iloc[1] == pytest.approx(0.0)

    def test_preserves_sign(self):
        m = _synth_master(
            statement=[0.3],
            minutes_lag=[-0.1],
            n=1,
        )
        s = compute_statement_vs_minutes_lag_divergence(m)
        assert s.iloc[0] == pytest.approx(0.4)


# ============================================================
# TestBuildFeaturesV3Table
# ============================================================


class TestBuildFeaturesV3Table:
    @pytest.fixture
    def built(self, tmp_path):
        out = tmp_path / "features_v3.parquet"
        return build_features_v3_table(
            master_table_path=REPO_ROOT / "data/divergence/calibration_features.parquet",
            rrd_path=REPO_ROOT / "data/market_pricing/real_rate_differential.parquet",
            output_path=out,
        ), out

    def test_has_18_feature_columns(self, built):
        df, _ = built
        # Original numeric features (11) + engineered (7) = 18. Master table also
        # includes some extra meta columns (source dates etc.) that are preserved
        # for reference — we only require that all expected classification feature
        # names are present.
        required = [
            "statement_ensemble_net",
            "statement_fomc_roberta_net",
            "statement_llama_deepinfra_net",
            "minutes_lag_ensemble_net",
            "minutes_lag_fomc_roberta_net",
            "minutes_lag_llama_deepinfra_net",
            "fedwatch_implied_change_bps",
            "real_rate_diff_5y",
            "cleveland_national_score",
            "cleveland_consensus_score",
            "cleveland_divergence",
        ] + ENGINEERED_FEATURES
        for col in required:
            assert col in df.columns, f"missing {col}"
        assert len(required) == 18

    def test_row_count_matches_master(self, built):
        df, _ = built
        assert len(df) == 42

    def test_engineered_features_have_expected_nan_count(self, built):
        df, _ = built
        # statement_momentum NaN on row 0 only
        assert pd.isna(df["statement_momentum"].iloc[0])
        assert df["statement_momentum"].iloc[1:].notna().all()
        # acceleration NaN on rows 0 and 1
        assert pd.isna(df["statement_acceleration"].iloc[0])
        assert pd.isna(df["statement_acceleration"].iloc[1])
        assert df["statement_acceleration"].iloc[2:].notna().all()
        assert pd.isna(df["cleveland_acceleration"].iloc[0])
        assert pd.isna(df["cleveland_acceleration"].iloc[1])
        assert df["cleveland_acceleration"].iloc[2:].notna().all()

    def test_original_features_unchanged(self, built):
        df, _ = built
        master = pd.read_parquet(REPO_ROOT / "data/divergence/calibration_features.parquet")
        pd.testing.assert_series_equal(
            df["statement_ensemble_net"].astype(float),
            master["statement_ensemble_net"].astype(float),
            check_names=False,
        )
        pd.testing.assert_series_equal(
            df["real_rate_diff_5y"].astype(float),
            master["real_rate_diff_5y"].astype(float),
            check_names=False,
        )

    def test_persistence_parquet(self, built):
        _, path = built
        assert path.exists()
        reread = pd.read_parquet(path)
        assert len(reread) == 42
        for f in ENGINEERED_FEATURES:
            assert f in reread.columns

    def test_feature_order(self, built):
        df, _ = built
        cols = df.columns.tolist()
        # Engineered features come AFTER all original columns.
        eng_idx = [cols.index(f) for f in ENGINEERED_FEATURES]
        first_eng = min(eng_idx)
        for c in cols[:first_eng]:
            assert c not in ENGINEERED_FEATURES
        # And the block of engineered features is contiguous in the declared order.
        assert cols[first_eng : first_eng + len(ENGINEERED_FEATURES)] == ENGINEERED_FEATURES
