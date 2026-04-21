"""PRD-300 / CC-2a-v2 — tests for classification target construction."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from macro_context_reader.divergence.targets_v2 import (
    REGIME_THRESHOLD_PCT,
    REGIME_WINDOW_DAYS,
    SURPRISE_THRESHOLD_BPS,
    build_targets_v2_table,
    compute_target_regime_class,
    compute_target_surprise_class,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def _master_with_surprise(values, dates=None):
    if dates is None:
        dates = pd.date_range("2021-01-27", periods=len(values), freq="MS")
    idx = pd.DatetimeIndex(dates, name="meeting_date")
    return pd.DataFrame({"fedwatch_surprise_bps": values}, index=idx)


def _synthetic_eurusd(start="2020-12-01", end="2026-06-30", start_px=1.10, end_px=1.10):
    dates = pd.bdate_range(start, end)
    prices = np.linspace(start_px, end_px, len(dates))
    df = pd.DataFrame({"eurusd_close": prices}, index=pd.DatetimeIndex(dates))
    df.index.name = "date"
    return df


# ============================================================
# TestComputeTargetSurpriseClass
# ============================================================


class TestComputeTargetSurpriseClass:
    def test_above_threshold_positive(self):
        m = _master_with_surprise([5.0])
        out = compute_target_surprise_class(m)
        assert int(out.iloc[0]) == 1

    def test_below_negative_threshold(self):
        m = _master_with_surprise([-3.0])
        out = compute_target_surprise_class(m)
        assert int(out.iloc[0]) == -1

    def test_within_threshold_zero(self):
        m = _master_with_surprise([1.0])
        out = compute_target_surprise_class(m)
        assert int(out.iloc[0]) == 0

    def test_small_negative_within_threshold_zero(self):
        m = _master_with_surprise([-1.5])
        out = compute_target_surprise_class(m)
        assert int(out.iloc[0]) == 0

    def test_exactly_threshold_is_positive(self):
        m = _master_with_surprise([2.0])
        out = compute_target_surprise_class(m)
        assert int(out.iloc[0]) == 1

    def test_exactly_negative_threshold_is_negative(self):
        m = _master_with_surprise([-2.0])
        out = compute_target_surprise_class(m)
        assert int(out.iloc[0]) == -1

    def test_nan_passes_through(self):
        m = _master_with_surprise([np.nan, 5.0])
        out = compute_target_surprise_class(m)
        assert pd.isna(out.iloc[0])
        assert int(out.iloc[1]) == 1

    def test_default_threshold_is_2bps(self):
        assert SURPRISE_THRESHOLD_BPS == 2.0

    def test_output_is_int64_nullable(self):
        m = _master_with_surprise([np.nan, 5.0, -3.0, 0.5])
        out = compute_target_surprise_class(m)
        assert out.dtype == "Int64"

    def test_custom_threshold_applied(self):
        m = _master_with_surprise([5.0])
        out = compute_target_surprise_class(m, threshold_bps=10.0)
        assert int(out.iloc[0]) == 0  # 5bps < 10bps custom threshold


# ============================================================
# TestComputeTargetRegimeClass
# ============================================================


class TestComputeTargetRegimeClass:
    def test_bullish_regime_above_threshold(self):
        # Linear price from 1.00 → 1.50 across ~125 bd, so the 42-bd segment
        # starting at T captures roughly a 17% move — well above threshold.
        eu = _synthetic_eurusd(
            start="2021-01-01", end="2021-06-30", start_px=1.00, end_px=1.50
        )
        meeting = pd.Timestamp("2021-01-15")
        m = pd.DataFrame({"fedwatch_surprise_bps": [0.0]},
                         index=pd.DatetimeIndex([meeting], name="meeting_date"))
        out = compute_target_regime_class(m, eu, window_days=42, threshold_pct=0.02)
        assert int(out.iloc[0]) == 1

    def test_bearish_regime_below_negative(self):
        # Linear price from 1.50 → 1.00 — 42-bd segment captures large negative move.
        eu = _synthetic_eurusd(
            start="2021-01-01", end="2021-06-30", start_px=1.50, end_px=1.00
        )
        meeting = pd.Timestamp("2021-01-15")
        m = pd.DataFrame({"fedwatch_surprise_bps": [0.0]},
                         index=pd.DatetimeIndex([meeting], name="meeting_date"))
        out = compute_target_regime_class(m, eu, window_days=42, threshold_pct=0.02)
        assert int(out.iloc[0]) == -1

    def test_range_regime_within_threshold(self):
        # +1.5% total change over the period - below 2% threshold.
        eu = _synthetic_eurusd(
            start="2021-01-01", end="2021-06-30", start_px=1.000, end_px=1.015
        )
        meeting = pd.Timestamp("2021-01-15")
        m = pd.DataFrame({"fedwatch_surprise_bps": [0.0]},
                         index=pd.DatetimeIndex([meeting], name="meeting_date"))
        out = compute_target_regime_class(m, eu, window_days=42, threshold_pct=0.02)
        assert int(out.iloc[0]) == 0

    def test_uses_42_business_day_window(self):
        # Build a step-function price series: flat at 1.00 up to and including T+41 bd,
        # jumps to 1.20 from T+42 bd onward. The regime lookup must hit the jump
        # exactly at T+42bd.
        meeting = pd.Timestamp("2021-01-15")
        idx = pd.bdate_range("2020-12-01", "2021-06-30")
        t42 = (meeting + pd.offsets.BusinessDay(42)).normalize()
        prices = np.where(idx >= t42, 1.20, 1.00)
        eu = pd.DataFrame({"eurusd_close": prices}, index=pd.DatetimeIndex(idx, name="date"))

        m = pd.DataFrame({"fedwatch_surprise_bps": [0.0]},
                         index=pd.DatetimeIndex([meeting], name="meeting_date"))
        out = compute_target_regime_class(m, eu, window_days=42, threshold_pct=0.02)
        assert int(out.iloc[0]) == 1  # 20% jump captured at T+42bd

    def test_handles_holidays_correctly(self):
        # If T+42bd falls on a day absent from the price series (e.g. holiday),
        # the helper walks forward up to max_walk and still returns a valid
        # result when data resumes.
        meeting = pd.Timestamp("2021-01-15")
        all_bd = pd.bdate_range("2020-12-01", "2021-06-30")
        t42 = (meeting + pd.offsets.BusinessDay(42)).normalize()
        # Drop T+42 itself to simulate a holiday gap; forward walk should pick
        # up the next business day.
        idx_kept = [d for d in all_bd if d != t42]
        # Large linear slope so the 42-bd segment clears the 2% threshold.
        prices = np.linspace(1.00, 1.50, len(idx_kept))
        eu = pd.DataFrame({"eurusd_close": prices}, index=pd.DatetimeIndex(idx_kept, name="date"))

        m = pd.DataFrame({"fedwatch_surprise_bps": [0.0]},
                         index=pd.DatetimeIndex([meeting], name="meeting_date"))
        out = compute_target_regime_class(m, eu, window_days=42, threshold_pct=0.02)
        # Strong positive slope + holiday-walk still lands on +1.
        assert int(out.iloc[0]) == 1

    def test_nan_when_window_exceeds_data(self):
        # Meeting close to the end of the EUR/USD series: T+42bd exceeds data.
        eu = _synthetic_eurusd(start="2021-01-01", end="2021-03-31",
                               start_px=1.00, end_px=1.05)
        meeting = pd.Timestamp("2021-03-25")
        m = pd.DataFrame({"fedwatch_surprise_bps": [0.0]},
                         index=pd.DatetimeIndex([meeting], name="meeting_date"))
        out = compute_target_regime_class(m, eu, window_days=42, threshold_pct=0.02)
        assert pd.isna(out.iloc[0])

    def test_source_date_column_accurate(self):
        # Import the private helper to verify the source_date column.
        from macro_context_reader.divergence.targets_v2 import _compute_regime_details
        eu = _synthetic_eurusd(start="2021-01-01", end="2021-06-30",
                               start_px=1.00, end_px=1.04)
        meeting = pd.Timestamp("2021-01-15")
        m = pd.DataFrame({"fedwatch_surprise_bps": [0.0]},
                         index=pd.DatetimeIndex([meeting], name="meeting_date"))
        detail = _compute_regime_details(m, eu)
        expected = (meeting + pd.offsets.BusinessDay(REGIME_WINDOW_DAYS)).normalize()
        actual = pd.Timestamp(detail["target_regime_source_date"].iloc[0])
        # Allow small forward walk (up to 5 bd) for holiday/weekend handling.
        delta = (actual - expected).days
        assert 0 <= delta <= 7

    def test_default_threshold_is_2pct(self):
        assert REGIME_THRESHOLD_PCT == 0.02

    def test_default_window_is_42_bd(self):
        assert REGIME_WINDOW_DAYS == 42

    def test_output_is_int64_nullable(self):
        eu = _synthetic_eurusd(start="2021-01-01", end="2021-06-30")
        meeting = pd.Timestamp("2021-01-15")
        m = pd.DataFrame({"fedwatch_surprise_bps": [0.0]},
                         index=pd.DatetimeIndex([meeting], name="meeting_date"))
        out = compute_target_regime_class(m, eu)
        assert out.dtype == "Int64"


# ============================================================
# TestBuildTargetsV2Table — integration, uses real artifacts
# ============================================================


class TestBuildTargetsV2Table:
    REAL_MASTER = REPO_ROOT / "data/divergence/calibration_features.parquet"
    REAL_EURUSD = REPO_ROOT / "data/market_pricing/eurusd_daily.parquet"

    def _real_artifacts_present(self) -> bool:
        return self.REAL_MASTER.exists() and self.REAL_EURUSD.exists()

    def test_schema_has_required_columns(self, tmp_path):
        if not self._real_artifacts_present():
            pytest.skip("real master/eurusd artifacts not present")
        out_path = tmp_path / "targets_v2.parquet"
        df = build_targets_v2_table(
            master_table_path=self.REAL_MASTER,
            eurusd_path=self.REAL_EURUSD,
            output_path=out_path,
        )
        required = {
            "target_surprise_class",
            "target_regime_class",
            "target_surprise_raw",
            "target_regime_raw_pct",
            "target_regime_source_date",
        }
        assert required.issubset(df.columns)

    def test_row_count_matches_master_alignment(self, tmp_path):
        if not self._real_artifacts_present():
            pytest.skip("real master/eurusd artifacts not present")
        out_path = tmp_path / "targets_v2.parquet"
        df = build_targets_v2_table(
            master_table_path=self.REAL_MASTER,
            eurusd_path=self.REAL_EURUSD,
            output_path=out_path,
        )
        master = pd.read_parquet(self.REAL_MASTER)
        assert len(df) == len(master)

    def test_persistence_parquet(self, tmp_path):
        if not self._real_artifacts_present():
            pytest.skip("real master/eurusd artifacts not present")
        out_path = tmp_path / "targets_v2.parquet"
        df = build_targets_v2_table(
            master_table_path=self.REAL_MASTER,
            eurusd_path=self.REAL_EURUSD,
            output_path=out_path,
        )
        assert out_path.exists()
        reloaded = pd.read_parquet(out_path)
        assert len(reloaded) == len(df)
        assert set(reloaded.columns) == set(df.columns)

    def test_integer_types_for_class_columns(self, tmp_path):
        if not self._real_artifacts_present():
            pytest.skip("real master/eurusd artifacts not present")
        out_path = tmp_path / "targets_v2.parquet"
        df = build_targets_v2_table(
            master_table_path=self.REAL_MASTER,
            eurusd_path=self.REAL_EURUSD,
            output_path=out_path,
        )
        assert str(df["target_surprise_class"].dtype) == "Int64"
        assert str(df["target_regime_class"].dtype) == "Int64"

    def test_last_meetings_have_nan_regime(self, tmp_path):
        """At least the very last meeting should have NaN regime (T+42bd exceeds cache)."""
        if not self._real_artifacts_present():
            pytest.skip("real master/eurusd artifacts not present")
        out_path = tmp_path / "targets_v2.parquet"
        df = build_targets_v2_table(
            master_table_path=self.REAL_MASTER,
            eurusd_path=self.REAL_EURUSD,
            output_path=out_path,
        )
        # The newest meeting(s) lack enough forward-window data.
        assert df["target_regime_class"].isna().sum() >= 1
        # Meetings from the first year should have valid regime classes.
        early = df[df.index < pd.Timestamp("2022-01-01")]
        assert early["target_regime_class"].notna().all()

    def test_surprise_class_values_in_valid_set(self, tmp_path):
        if not self._real_artifacts_present():
            pytest.skip("real master/eurusd artifacts not present")
        out_path = tmp_path / "targets_v2.parquet"
        df = build_targets_v2_table(
            master_table_path=self.REAL_MASTER,
            eurusd_path=self.REAL_EURUSD,
            output_path=out_path,
        )
        valid_vals = df["target_surprise_class"].dropna().unique()
        assert set(valid_vals).issubset({-1, 0, 1})
