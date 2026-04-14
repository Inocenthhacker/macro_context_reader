"""Tests for CME FedWatch CSV parser — PRD-202."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from macro_context_reader.market_pricing.fedwatch import (
    get_snapshot_metadata,
    parse_fedwatch_csv,
)
from macro_context_reader.market_pricing.fedwatch.parser import (
    MEETING_HEADER_RE,
    RATE_BUCKET_RE,
    _parse_meeting_date,
    _parse_snapshot_date_from_filename,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_CSV = (
    REPO_ROOT / "data" / "market_pricing" / "fedwatch_snapshots"
    / "FedMeetingHistory_20260414.csv"
)


class TestMeetingDateParser:
    def test_standard_format(self):
        assert _parse_meeting_date("History for 29 Apr 2026 Fed meeting") == date(2026, 4, 29)

    def test_single_digit_day(self):
        assert _parse_meeting_date("History for 9 Dec 2026 Fed meeting") == date(2026, 12, 9)

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            _parse_meeting_date("not a meeting label")


class TestSnapshotDateFromFilename:
    def test_standard_filename(self):
        assert _parse_snapshot_date_from_filename(
            Path("FedMeetingHistory_20260414.csv")
        ) == date(2026, 4, 14)

    def test_malformed_filename_raises(self):
        with pytest.raises(ValueError):
            _parse_snapshot_date_from_filename(Path("random.csv"))


class TestRegexes:
    def test_bucket_regex_matches(self):
        m = RATE_BUCKET_RE.search("(25-50)")
        assert m is not None
        assert m.group(1) == "25"
        assert m.group(2) == "50"

    def test_bucket_regex_large_values(self):
        m = RATE_BUCKET_RE.search("(1550-1575)")
        assert m is not None
        assert m.group(1) == "1550"
        assert m.group(2) == "1575"

    def test_meeting_header_regex(self):
        m = MEETING_HEADER_RE.search("History for 29 Apr 2026 Fed meeting")
        assert m is not None


@pytest.mark.skipif(not SAMPLE_CSV.exists(), reason="Sample CSV not present")
class TestRealCSVParsing:
    def test_returns_dataframe(self):
        df = parse_fedwatch_csv(SAMPLE_CSV)
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 1000

    def test_expected_columns(self):
        df = parse_fedwatch_csv(SAMPLE_CSV)
        expected = {
            "observation_date", "meeting_date",
            "rate_bucket_low", "rate_bucket_high", "probability",
        }
        assert expected.issubset(set(df.columns))

    def test_probabilities_in_valid_range(self):
        df = parse_fedwatch_csv(SAMPLE_CSV)
        assert (df["probability"] > 0.0).all()
        assert (df["probability"] <= 1.0).all()

    def test_meeting_dates_multiple(self):
        df = parse_fedwatch_csv(SAMPLE_CSV)
        assert df["meeting_date"].nunique() >= 8

    def test_observation_dates_span_months(self):
        df = parse_fedwatch_csv(SAMPLE_CSV)
        span = df["observation_date"].max() - df["observation_date"].min()
        assert span.days > 300

    def test_probabilities_sum_to_one_per_day_per_meeting(self):
        df = parse_fedwatch_csv(SAMPLE_CSV)
        sums = df.groupby(["observation_date", "meeting_date"])["probability"].sum()
        assert (sums > 0.95).mean() > 0.9

    def test_metadata_extraction(self):
        meta = get_snapshot_metadata(SAMPLE_CSV)
        assert meta.snapshot_date == date(2026, 4, 14)
        assert meta.source_file == "FedMeetingHistory_20260414.csv"
        assert len(meta.meeting_dates) >= 8
        assert meta.row_count > 1000


class TestMissingFile:
    def test_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            parse_fedwatch_csv(tmp_path / "nonexistent.csv")
