"""PRD-300 / CC-2a — tests for target construction."""
from __future__ import annotations

from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd
import pytest

from macro_context_reader.divergence import targets as targets_mod
from macro_context_reader.divergence.targets import (
    build_targets_table,
    compute_target_A_fedwatch_surprise,
    compute_target_D_real_rate_diff_change,
    compute_target_E_eurusd_5d_return,
    compute_target_F_eurusd_21d_return,
    fetch_eurusd_daily,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def _tiny_master(dates):
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d in dates], name="meeting_date")
    return pd.DataFrame(
        {
            "fedwatch_surprise_bps": np.linspace(-10, 10, len(idx)),
        },
        index=idx,
    )


def _tiny_rrd(start="2021-01-01", end="2022-12-31", slope=0.01):
    dates = pd.date_range(start, end, freq="B")
    values = np.linspace(1.0, 1.0 + slope * len(dates), len(dates))
    return pd.DataFrame({"date": dates, "real_rate_differential": values})


def _tiny_eurusd(start="2021-01-01", end="2022-12-31", start_px=1.0, end_px=1.20):
    dates = pd.date_range(start, end, freq="B")
    prices = np.linspace(start_px, end_px, len(dates))
    return pd.DataFrame({"eurusd_close": prices}, index=dates)


# ============================================================
# TestFetchEURUSD
# ============================================================


class TestFetchEURUSD:
    def test_fetches_from_fred_and_caches(self, tmp_path):
        cache = tmp_path / "eurusd.parquet"
        fake = _tiny_eurusd().reset_index().rename(columns={"index": "date"})
        fake_series = pd.Series(
            fake["eurusd_close"].values, index=pd.to_datetime(fake["date"].values)
        )

        class _StubFred:
            def __init__(self):
                self.calls = 0

            def get_series(self, *args, **kwargs):
                self.calls += 1
                return fake_series

        stub = _StubFred()
        with mock.patch.object(targets_mod, "_get_fred_client", return_value=stub):
            df1 = fetch_eurusd_daily(cache_path=cache, use_cache=False)
            assert stub.calls == 1
            assert cache.exists()
            df2 = fetch_eurusd_daily(cache_path=cache, use_cache=True)
            assert stub.calls == 1  # cached — no additional FRED call
            pd.testing.assert_frame_equal(df1.reset_index(drop=True), df2.reset_index(drop=True))

    def test_returns_datetime_indexed_df(self, tmp_path):
        cache = tmp_path / "eu.parquet"
        _tiny_eurusd().to_parquet(cache)
        df = fetch_eurusd_daily(cache_path=cache, use_cache=True)
        assert isinstance(df.index, pd.DatetimeIndex)
        assert "eurusd_close" in df.columns

    def test_date_range_covers_2021_2026(self):
        cache = REPO_ROOT / "data/market_pricing/eurusd_daily.parquet"
        if not cache.exists():
            pytest.skip("Real EUR/USD cache not yet built")
        df = fetch_eurusd_daily(cache_path=cache, use_cache=True)
        assert df.index.min() <= pd.Timestamp("2021-01-10")
        assert df.index.max() >= pd.Timestamp("2026-03-01")


# ============================================================
# TestTargetA
# ============================================================


class TestTargetA:
    def test_equals_existing_column(self):
        master = _tiny_master(["2022-01-26", "2022-03-16", "2022-05-04"])
        result = compute_target_A_fedwatch_surprise(master)
        np.testing.assert_allclose(result.values, master["fedwatch_surprise_bps"].values)
        assert result.name == "target_A_fedwatch_surprise"


# ============================================================
# TestTargetD
# ============================================================


class TestTargetD:
    def test_uses_5bd_forward_window(self):
        rrd = _tiny_rrd()
        master = _tiny_master(["2022-03-16"])
        out = compute_target_D_real_rate_diff_change(master, rrd, window_days=5)
        T = pd.Timestamp("2022-03-16")
        series = rrd.set_index("date")["real_rate_differential"]
        v_t = series.loc[T]
        v_end = series.loc[T + pd.offsets.BusinessDay(5)]
        assert out.loc[T] == pytest.approx(v_end - v_t)

    def test_handles_holidays(self):
        dates = pd.date_range("2022-01-01", "2022-06-30", freq="B")
        values = np.linspace(1.0, 2.0, len(dates))
        rrd = pd.DataFrame({"date": dates, "real_rate_differential": values})
        master = _tiny_master(["2022-03-16"])
        out = compute_target_D_real_rate_diff_change(master, rrd, window_days=5)
        assert not np.isnan(out.iloc[0])

    def test_nan_when_window_exceeds_data(self):
        rrd = _tiny_rrd(start="2022-01-01", end="2022-03-20")
        master = _tiny_master(["2022-03-18"])
        out = compute_target_D_real_rate_diff_change(master, rrd, window_days=5)
        assert np.isnan(out.iloc[0])


# ============================================================
# TestTargetE
# ============================================================


class TestTargetE:
    def test_log_return_formula(self):
        dates = pd.bdate_range("2022-01-03", periods=10)
        prices = np.ones(10)
        prices[5] = 1.10
        df = pd.DataFrame({"eurusd_close": prices}, index=dates)
        # Compute 5bd return from day 0 (1.00) to day 5 (1.10)
        master = pd.DataFrame(index=pd.DatetimeIndex([dates[0]], name="meeting_date"))
        out = compute_target_E_eurusd_5d_return(master, df, window_days=5)
        assert out.iloc[0] == pytest.approx(np.log(1.10 / 1.00), abs=1e-6)

    def test_positive_means_eur_up(self):
        dates = pd.bdate_range("2022-01-03", periods=15)
        prices = np.linspace(1.00, 1.10, 15)
        df = pd.DataFrame({"eurusd_close": prices}, index=dates)
        master = pd.DataFrame(index=pd.DatetimeIndex([dates[0]], name="meeting_date"))
        out = compute_target_E_eurusd_5d_return(master, df, window_days=5)
        assert out.iloc[0] > 0

    def test_5bd_window(self):
        dates = pd.bdate_range("2022-01-03", periods=15)
        prices = np.arange(1.0, 1.0 + 0.01 * 15, 0.01)[:15]
        df = pd.DataFrame({"eurusd_close": prices}, index=dates)
        master = pd.DataFrame(index=pd.DatetimeIndex([dates[0]], name="meeting_date"))
        out = compute_target_E_eurusd_5d_return(master, df, window_days=5)
        expected = float(np.log(prices[5] / prices[0]))
        assert out.iloc[0] == pytest.approx(expected, abs=1e-6)


# ============================================================
# TestTargetF
# ============================================================


class TestTargetF:
    def test_21bd_window_vs_5bd(self):
        dates = pd.bdate_range("2022-01-03", periods=40)
        prices = np.linspace(1.00, 1.10, 40)
        df = pd.DataFrame({"eurusd_close": prices}, index=dates)
        master = pd.DataFrame(index=pd.DatetimeIndex([dates[0]], name="meeting_date"))
        e = compute_target_E_eurusd_5d_return(master, df, window_days=5)
        f = compute_target_F_eurusd_21d_return(master, df, window_days=21)
        assert f.iloc[0] != e.iloc[0]
        assert abs(f.iloc[0]) > abs(e.iloc[0])

    def test_magnitude_typically_larger_than_E(self):
        dates = pd.bdate_range("2022-01-03", periods=40)
        prices = 1.0 + np.cumsum(np.random.RandomState(42).normal(0, 0.005, 40))
        df = pd.DataFrame({"eurusd_close": prices}, index=dates)
        master = pd.DataFrame(
            index=pd.DatetimeIndex(
                [dates[0], dates[5], dates[10]], name="meeting_date"
            )
        )
        e = compute_target_E_eurusd_5d_return(master, df, window_days=5).abs().mean()
        f = compute_target_F_eurusd_21d_return(master, df, window_days=21).abs().mean()
        # For random walk, |21bd| typically larger than |5bd|
        assert f > e


# ============================================================
# TestBuildTargetsTable
# ============================================================


REAL_MASTER = REPO_ROOT / "data/divergence/calibration_features.parquet"
REAL_RRD = REPO_ROOT / "data/market_pricing/real_rate_differential.parquet"
REAL_EURUSD = REPO_ROOT / "data/market_pricing/eurusd_daily.parquet"


@pytest.mark.skipif(
    not (REAL_MASTER.exists() and REAL_RRD.exists() and REAL_EURUSD.exists()),
    reason="real inputs not yet built",
)
class TestBuildTargetsTable:
    @pytest.fixture(scope="class")
    def targets(self, tmp_path_factory):
        out = tmp_path_factory.mktemp("tgt") / "targets.parquet"
        return build_targets_table(
            master_table_path=REAL_MASTER,
            rrd_path=REAL_RRD,
            output_path=out,
            eurusd_cache_path=REAL_EURUSD,
        ), out

    def test_all_four_targets_present(self, targets):
        df, _ = targets
        assert set(df.columns) == {
            "target_A_fedwatch_surprise",
            "target_D_rrd_change_5d",
            "target_E_eurusd_5d",
            "target_F_eurusd_21d",
        }

    def test_index_is_canonical_fomc_dates(self, targets):
        df, _ = targets
        master = pd.read_parquet(REAL_MASTER)
        assert list(df.index) == list(master.index)

    def test_row_count_matches_master(self, targets):
        df, _ = targets
        assert len(df) == 42

    def test_persistence(self, targets):
        _, path = targets
        assert path.exists()
        reloaded = pd.read_parquet(path)
        assert len(reloaded) == 42
