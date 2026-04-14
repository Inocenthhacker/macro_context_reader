"""Tests for fedwatch surprise computation — PRD-202 CC-3."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from macro_context_reader.market_pricing.fedwatch.surprise import (
    DEFAULT_NLP_CALIBRATION_BPS,
    _compute_nlp_distribution,
    _get_buckets_for_date,
    _market_expected_change_bps,
    _market_prob_hike,
    _surprise_binary,
    _surprise_expected_change,
    _surprise_kl_divergence,
    compute_surprise_signal,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
SEED_CSV = (
    REPO_ROOT / "data" / "market_pricing" / "fedwatch_snapshots"
    / "FedMeetingHistory_20260414.csv"
)
SEED_PRESENT = SEED_CSV.exists()


def _make_buckets_df():
    return pd.DataFrame({
        "rate_bucket_low": [325, 350, 375, 400],
        "rate_bucket_high": [350, 375, 400, 425],
        "probability": [0.2, 0.6, 0.15, 0.05],
    })


class TestBinarySurprise:
    def test_hawkish_beyond_market(self):
        assert _surprise_binary(0.8, 0.3) == pytest.approx(0.5)

    def test_aligned(self):
        assert _surprise_binary(0.5, 0.5) == pytest.approx(0.0)

    def test_dovish_surprise(self):
        assert _surprise_binary(-0.3, 0.6) == pytest.approx(-0.9)


class TestExpectedChangeSurprise:
    def test_hawkish_nlp_vs_dovish_market(self):
        # NLP +0.5 -> +12.5bps implied; market -10bps -> surprise +22.5
        assert _surprise_expected_change(0.5, -10.0) == pytest.approx(22.5)

    def test_dovish_nlp_vs_hawkish_market(self):
        # NLP -0.3 -> -7.5bps; market +15bps -> surprise -22.5
        assert _surprise_expected_change(-0.3, 15.0) == pytest.approx(-22.5)

    def test_aligned(self):
        # NLP +0.4 -> +10bps; market +10bps -> 0
        assert _surprise_expected_change(0.4, 10.0) == pytest.approx(0.0)

    def test_custom_calibration(self):
        assert _surprise_expected_change(1.0, 0.0, calibration_bps=50.0) == pytest.approx(50.0)

    def test_default_calibration_constant(self):
        assert DEFAULT_NLP_CALIBRATION_BPS == 25.0


class TestKLDivergence:
    def test_identical_distributions_zero(self):
        d = np.array([0.25, 0.5, 0.25])
        assert _surprise_kl_divergence(d, d) == pytest.approx(0.0, abs=1e-6)

    def test_different_distributions_positive(self):
        p = np.array([0.7, 0.2, 0.1])
        q = np.array([0.1, 0.2, 0.7])
        assert _surprise_kl_divergence(p, q) > 0.5

    def test_always_nonneg(self):
        p = np.array([0.3, 0.3, 0.4])
        q = np.array([0.5, 0.3, 0.2])
        assert _surprise_kl_divergence(p, q) >= 0.0


class TestBucketAggregation:
    def test_market_expected_change(self):
        df = _make_buckets_df()
        # Midpoints: 337.5, 362.5, 387.5, 412.5; current 362.5
        # Changes: -25, 0, 25, 50; weighted: -5 + 0 + 3.75 + 2.5 = 1.25
        assert _market_expected_change_bps(df, 362.5) == pytest.approx(1.25)

    def test_prob_hike_above_current(self):
        df = _make_buckets_df()
        # Buckets with low >= 363.5 (i.e. 375, 400): probs 0.15 + 0.05 = 0.20
        assert _market_prob_hike(df, 362.5) == pytest.approx(0.20)


class TestNLPDistribution:
    def test_sums_to_one(self):
        df = _make_buckets_df()
        assert _compute_nlp_distribution(0.0, 362.5, df).sum() == pytest.approx(1.0, abs=1e-6)

    def test_hawkish_shifts_right(self):
        df = _make_buckets_df()
        neutral = _compute_nlp_distribution(0.0, 362.5, df)
        hawkish = _compute_nlp_distribution(1.0, 362.5, df)
        assert hawkish[2:].sum() > neutral[2:].sum()

    def test_dovish_shifts_left(self):
        df = _make_buckets_df()
        neutral = _compute_nlp_distribution(0.0, 362.5, df)
        dovish = _compute_nlp_distribution(-1.0, 362.5, df)
        assert dovish[:2].sum() > neutral[:2].sum()


class TestGetBucketsForDate:
    def _mini_df(self):
        return pd.DataFrame({
            "observation_date": [pd.Timestamp("2026-04-14")] * 6,
            "meeting_date": [pd.Timestamp("2026-04-29")] * 3 + [pd.Timestamp("2026-06-17")] * 3,
            "rate_bucket_low": [325, 350, 375] * 2,
            "rate_bucket_high": [350, 375, 400] * 2,
            "probability": [0.3, 0.5, 0.2] * 2,
        })

    def test_picks_nearest_upcoming(self):
        df = self._mini_df()
        result = _get_buckets_for_date(df, date(2026, 4, 14))
        assert (result["meeting_date"] == pd.Timestamp("2026-04-29")).all()

    def test_explicit_meeting_date(self):
        df = self._mini_df()
        result = _get_buckets_for_date(df, date(2026, 4, 14), date(2026, 6, 17))
        assert (result["meeting_date"] == pd.Timestamp("2026-06-17")).all()

    def test_missing_date_raises(self):
        df = self._mini_df()
        with pytest.raises(ValueError, match="No FedWatch data"):
            _get_buckets_for_date(df, date(2099, 1, 1))


@pytest.mark.skipif(not SEED_PRESENT, reason="Seed CSV not present")
class TestSingleEventWithMockedRate:
    def test_expected_change_with_explicit_rate(self):
        from macro_context_reader.market_pricing.fedwatch import load_fedwatch_history
        df = load_fedwatch_history(rebuild=True)
        test_date = df["observation_date"].max().date()
        s = compute_surprise_signal(
            nlp_score=0.3, as_of_date=test_date, method="expected_change",
            fedwatch_df=df, current_rate_bps=362.5,
        )
        assert isinstance(s, float)

    def test_kl_method(self):
        from macro_context_reader.market_pricing.fedwatch import load_fedwatch_history
        df = load_fedwatch_history(rebuild=True)
        test_date = df["observation_date"].max().date()
        s = compute_surprise_signal(
            nlp_score=0.0, as_of_date=test_date, method="kl_divergence",
            fedwatch_df=df, current_rate_bps=362.5,
        )
        assert s >= 0.0

    def test_binary_method(self):
        from macro_context_reader.market_pricing.fedwatch import load_fedwatch_history
        df = load_fedwatch_history(rebuild=True)
        test_date = df["observation_date"].max().date()
        s = compute_surprise_signal(
            nlp_score=0.5, as_of_date=test_date, method="binary",
            fedwatch_df=df, current_rate_bps=362.5,
        )
        assert isinstance(s, float)


class TestInvalidInputs:
    def test_unknown_method_raises(self):
        mini = pd.DataFrame({
            "observation_date": [pd.Timestamp("2026-04-14")],
            "meeting_date": [pd.Timestamp("2026-04-29")],
            "rate_bucket_low": [350],
            "rate_bucket_high": [375],
            "probability": [1.0],
        })
        with pytest.raises(ValueError, match="Unknown method"):
            compute_surprise_signal(
                nlp_score=0.5, as_of_date=date(2026, 4, 14),
                method="invalid",  # type: ignore[arg-type]
                current_rate_bps=362.5, fedwatch_df=mini,
            )
