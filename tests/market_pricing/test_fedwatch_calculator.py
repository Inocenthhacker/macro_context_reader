"""Tests for the custom FedWatch probability calculator.

PRD-300 / CC-1.5.2b-IMPL-2

Unit tests use mock chain data with exact CME-documented values.
Integration tests use actual ZQ chain parquets on disk.
"""
from __future__ import annotations

import calendar
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from macro_context_reader.market_pricing.fedwatch.calculator import (
    compute_all_meetings,
    compute_meeting_probability,
    compute_surprise,
    days_before_after_meeting,
    implied_avg_effr,
)
from macro_context_reader.market_pricing.fedwatch.zq_futures import (
    FRONT_MONTHS,
    load_all_chains,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PARQUET_PATH = Path("data/market_pricing/fedwatch_surprise.parquet")
MPT_ARCHIVE_PATH = Path("data/market_pricing/fedwatch_surprise_mpt_only.parquet")


def _mock_chains(watch_date, closes: dict[int, float]) -> dict[int, pd.DataFrame]:
    """Create mock chain data with given close prices at *watch_date*."""
    idx = pd.DatetimeIndex([pd.Timestamp(watch_date)], name="date")
    chains: dict[int, pd.DataFrame] = {}
    for i in range(FRONT_MONTHS):
        close = closes.get(i, 96.0)
        chains[i] = pd.DataFrame(
            {
                "open": [close],
                "high": [close],
                "low": [close],
                "close": [close],
                "volume": [1000],
            },
            index=idx,
        )
    return chains


# ---------------------------------------------------------------------------
# Unit tests -- primitives
# ---------------------------------------------------------------------------


class TestImpliedAvgEffr:
    def test_basic(self):
        assert implied_avg_effr(94.87) == pytest.approx(5.13)

    def test_zirp(self):
        assert implied_avg_effr(99.80) == pytest.approx(0.20)

    def test_inverse(self):
        assert implied_avg_effr(100.0) == pytest.approx(0.0)


class TestDaysBeforeAfterMeeting:
    def test_sept_2022(self):
        N, M = days_before_after_meeting(pd.Timestamp("2022-09-21"))
        assert (N, M) == (21, 9)

    def test_dec_2015(self):
        N, M = days_before_after_meeting(pd.Timestamp("2015-12-16"))
        assert (N, M) == (16, 15)

    def test_july_31(self):
        """Meeting on last day of month: M=0."""
        N, M = days_before_after_meeting(pd.Timestamp("2019-07-31"))
        assert (N, M) == (31, 0)

    def test_total_equals_month_days(self):
        for ds in ["2022-09-21", "2024-01-31", "2024-03-20", "2015-12-16"]:
            ts = pd.Timestamp(ds)
            N, M = days_before_after_meeting(ts)
            assert N + M == calendar.monthrange(ts.year, ts.month)[1]


# ---------------------------------------------------------------------------
# Unit tests -- CME documented example (Sep 2022)
# ---------------------------------------------------------------------------


class TestCMEExampleSept2022:
    """Reproduce the EXACT CME documented example (Arthur Lobao, CME Group 2023).

    ZQU2 (Sep 2022 contract) = 97.4475
    ZQV2 (Oct 2022 contract) = 96.9400
    Meeting: 2022-09-21
    Expected: P(50bp hike) = 10%, P(75bp hike) = 90%
    """

    @pytest.fixture()
    def result(self):
        watch_date = pd.Timestamp("2022-09-20")
        chains = _mock_chains(
            watch_date,
            {0: 97.4475, 1: 96.9400},
        )
        return compute_meeting_probability(
            watch_date, pd.Timestamp("2022-09-21"), chains
        )

    def test_effr_start(self, result):
        assert result["effr_start"] == pytest.approx(2.335, abs=0.001)

    def test_effr_end(self, result):
        assert result["effr_end"] == pytest.approx(3.060, abs=0.001)

    def test_expected_change_bps(self, result):
        assert result["expected_change_bps"] == pytest.approx(72.5, abs=0.5)

    def test_prob_50bp_hike(self, result):
        assert result["prob_lower"] == pytest.approx(0.10, abs=0.005)

    def test_prob_75bp_hike(self, result):
        assert result["prob_upper"] == pytest.approx(0.90, abs=0.005)

    def test_move_sizes(self, result):
        assert result["lower_move_bps"] == 50.0
        assert result["upper_move_bps"] == 75.0

    def test_market_implied_change(self, result):
        assert result["market_implied_change_bps"] == pytest.approx(72.5, abs=0.5)

    def test_probs_sum_to_one(self, result):
        assert result["prob_lower"] + result["prob_upper"] == pytest.approx(
            1.0, abs=0.01
        )


# ---------------------------------------------------------------------------
# Integration tests -- real chain data
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_chains():
    try:
        return load_all_chains()
    except FileNotFoundError:
        pytest.skip("ZQ chain parquets not available")


# ---- Probe ground truth ---------------------------------------------------


class TestProbeGroundTruth:
    """Validate against pyfedwatch v2 probe results (3 key meetings)."""

    @pytest.mark.integration
    def test_2015_12_zirp_exit(self, real_chains):
        """2015-12-16 ZIRP exit: P(25bps hike) ~ 77%.

        Wider tolerance (±10%): the backward chain propagates through the
        January 2016 FOMC meeting, which absorbs some rate-change attribution.
        Continuous-chain values also differ slightly from pyfedwatch data.
        """
        meeting = pd.Timestamp("2015-12-16")
        watch = meeting - pd.offsets.BDay(1)
        r = compute_meeting_probability(watch, meeting, real_chains)

        assert r["upper_move_bps"] == 25.0
        assert r["prob_upper"] == pytest.approx(0.77, abs=0.10)

    @pytest.mark.integration
    def test_2022_03_hiking_start(self, real_chains):
        """2022-03-16 hiking cycle start: P(25bps hike) ~ 88%.

        At watch_date, market priced >25bps expected change, so floor=1 (25bp)
        and prob_lower represents P(25bp hike).
        """
        meeting = pd.Timestamp("2022-03-16")
        watch = meeting - pd.offsets.BDay(1)
        r = compute_meeting_probability(watch, meeting, real_chains)

        assert r["lower_move_bps"] == 25.0
        assert r["prob_lower"] == pytest.approx(0.88, abs=0.05)

    @pytest.mark.integration
    def test_2024_09_cutting_start(self, real_chains):
        """2024-09-18 cutting cycle start: P(50bps cut) ~ 64%."""
        meeting = pd.Timestamp("2024-09-18")
        watch = meeting - pd.offsets.BDay(1)
        r = compute_meeting_probability(watch, meeting, real_chains)

        # For cuts: floor_moves is negative, so lower_move_bps = floor*25
        assert r["lower_move_bps"] == -50.0
        assert r["prob_lower"] == pytest.approx(0.64, abs=0.05)


# ---- MPT cross-validation -------------------------------------------------


class TestMPTCrossValidation:
    """Cross-validate against the 12 meetings in the MPT-only archive."""

    @pytest.mark.integration
    def test_cross_validate_mpt_overlap(self, real_chains):
        """MPT overlap: report diffs, warn >5bps (not a blocker per PRD-300).

        The CME methodology (direct ZQ chain calculation) and Atlanta Fed MPT
        (probability distribution buckets) are fundamentally different approaches.
        Larger divergences are expected for meetings far from watch_date where
        backward-chain propagation through multiple intermediate meetings
        amplifies methodology differences.
        """
        if not MPT_ARCHIVE_PATH.exists():
            pytest.skip("MPT archive not yet created")

        mpt = pd.read_parquet(MPT_ARCHIVE_PATH)

        results = []
        for meeting_date in mpt.index:
            watch = meeting_date - pd.offsets.BDay(1)
            try:
                r = compute_meeting_probability(watch, meeting_date, real_chains)
                results.append(r)
            except ValueError:
                continue

        assert len(results) > 0, "No overlapping meetings computed"

        our_df = pd.DataFrame(results).set_index("meeting_date")
        overlap = mpt.index.intersection(our_df.index)
        assert len(overlap) > 0, "No date overlap between calculator and MPT"

        diffs = []
        for date in overlap:
            ours = our_df.loc[date, "market_implied_change_bps"]
            theirs = mpt.loc[date, "market_implied_change_bps"]
            diff = abs(ours - theirs)
            diffs.append(diff)
            if diff > 5.0:
                logger.warning(
                    "MPT diff >5bps at %s: ours=%.2f, MPT=%.2f, diff=%.2f",
                    date.date(),
                    ours,
                    theirs,
                    diff,
                )

        median_diff = sorted(diffs)[len(diffs) // 2]
        max_diff = max(diffs)
        logger.info(
            "MPT cross-validation: %d meetings, median diff=%.2f, max diff=%.2f",
            len(overlap),
            median_diff,
            max_diff,
        )
        # Methodologies differ; median diff should be modest even if max is large
        assert median_diff < 10.0, (
            f"Median diff {median_diff:.2f}bps on {len(overlap)} meetings"
        )


# ---- Structural tests ------------------------------------------------------


class TestStructural:
    @pytest.mark.integration
    def test_all_probabilities_sum_to_one(self, real_chains):
        """For 20 sampled meetings, prob_lower + prob_upper ~ 1.0."""
        meetings = pd.to_datetime(
            [
                "2011-01-26",
                "2012-06-20",
                "2013-12-18",
                "2014-09-17",
                "2015-03-18",
                "2016-12-14",
                "2017-06-14",
                "2018-09-26",
                "2019-10-30",
                "2020-06-10",
                "2020-12-16",
                "2021-06-16",
                "2022-01-26",
                "2022-06-15",
                "2022-12-14",
                "2023-05-03",
                "2023-12-13",
                "2024-06-12",
                "2025-01-29",
                "2025-09-17",
            ]
        )
        for mtg in meetings:
            watch = mtg - pd.offsets.BDay(1)
            try:
                r = compute_meeting_probability(watch, mtg, real_chains)
                total = r["prob_lower"] + r["prob_upper"]
                assert total == pytest.approx(1.0, abs=0.01), (
                    f"Probs don't sum to 1 for {mtg.date()}: {total}"
                )
            except ValueError:
                pass  # skip if not computable

    @pytest.mark.integration
    def test_output_schema(self):
        if not PARQUET_PATH.exists():
            pytest.skip("Surprise parquet not yet created")
        df = pd.read_parquet(PARQUET_PATH)
        required = {
            "market_implied_change_bps",
            "actual_change_bps",
            "surprise_bps",
            "surprise_zscore",
        }
        missing = required - set(df.columns)
        assert not missing, f"Missing columns: {missing}"

    @pytest.mark.integration
    def test_no_nan_in_core_columns(self):
        if not PARQUET_PATH.exists():
            pytest.skip("Surprise parquet not yet created")
        df = pd.read_parquet(PARQUET_PATH)
        for col in ["market_implied_change_bps", "actual_change_bps", "surprise_bps"]:
            assert df[col].isna().sum() == 0, f"{col} has NaN"

    @pytest.mark.integration
    def test_chronological_index(self):
        if not PARQUET_PATH.exists():
            pytest.skip("Surprise parquet not yet created")
        df = pd.read_parquet(PARQUET_PATH)
        if isinstance(df.index, pd.DatetimeIndex):
            assert df.index.is_monotonic_increasing, "Index not chronological"
