"""Tests for canonical FOMC dates utility."""
import pandas as pd
import pytest

from macro_context_reader.utils.canonical_fomc_dates import (
    FOMC_MEETING_DATES,
    snap_to_fomc,
    snap_series_to_fomc,
    is_fomc_date,
)


class TestFOMCMeetingDatesList:
    def test_is_datetime_index(self):
        assert isinstance(FOMC_MEETING_DATES, pd.DatetimeIndex)

    def test_is_sorted(self):
        assert FOMC_MEETING_DATES.is_monotonic_increasing

    def test_has_expected_count_per_year(self):
        """Each year 1990-2025 should have ~8 meetings (allowing 9 for 2020 emergency)."""
        for year in range(1990, 2026):
            count = sum(1 for d in FOMC_MEETING_DATES if d.year == year)
            assert 7 <= count <= 10, f"Year {year} has {count} meetings (expected 7-10)"

    def test_no_duplicates(self):
        assert len(FOMC_MEETING_DATES) == len(set(FOMC_MEETING_DATES))

    def test_known_critical_dates_present(self):
        """Spot-check a few historically important FOMC dates."""
        critical = [
            "2008-09-16",  # Lehman week
            "2015-12-16",  # First liftoff from ZIRP
            "2020-03-15",  # Emergency pandemic cut
            "2022-03-16",  # Start of hiking cycle
            "2024-09-18",  # Start of cutting cycle
        ]
        for d in critical:
            assert pd.Timestamp(d) in FOMC_MEETING_DATES, f"Missing critical date: {d}"


class TestSnapToFOMC:
    def test_exact_match_returns_same_date(self):
        result = snap_to_fomc("2024-09-18")
        assert result == pd.Timestamp("2024-09-18")

    def test_7day_forward_offset_snaps_back(self):
        """MPT case: 2023-06-21 should snap to 2023-06-14 meeting."""
        result = snap_to_fomc("2023-06-21", direction="backward")
        assert result == pd.Timestamp("2023-06-14")

    def test_beyond_max_offset_raises(self):
        with pytest.raises(ValueError, match="exceeds max_offset_days"):
            snap_to_fomc("2024-04-15", max_offset_days=14, direction="backward")

    def test_direction_forward(self):
        result = snap_to_fomc("2023-06-13", direction="forward")
        assert result == pd.Timestamp("2023-06-14")

    def test_direction_nearest(self):
        result = snap_to_fomc("2023-06-20", direction="nearest")
        assert result == pd.Timestamp("2023-06-14")

    def test_invalid_direction_raises(self):
        with pytest.raises(ValueError, match="direction must be"):
            snap_to_fomc("2024-01-31", direction="sideways")

    def test_before_first_meeting_raises(self):
        with pytest.raises(ValueError):
            snap_to_fomc("1989-01-01", direction="backward")


class TestSnapSeriesToFOMC:
    def test_vectorized_snapping(self):
        dates = pd.DatetimeIndex(["2023-06-21", "2023-12-20", "2024-06-19"])
        result = snap_series_to_fomc(dates, direction="backward")
        expected = pd.DatetimeIndex(["2023-06-14", "2023-12-13", "2024-06-12"])
        pd.testing.assert_index_equal(result, expected)


class TestIsFOMCDate:
    def test_true_for_meeting_date(self):
        assert is_fomc_date("2024-09-18") is True

    def test_false_for_non_meeting_date(self):
        assert is_fomc_date("2024-09-19") is False
