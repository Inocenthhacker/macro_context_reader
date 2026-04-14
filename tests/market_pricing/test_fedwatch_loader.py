"""Tests for FedWatch multi-snapshot loader — PRD-202 CC-2."""
from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd
import pytest

from macro_context_reader.market_pricing.fedwatch import (
    build_master_dataset,
    list_available_snapshots,
    load_all_snapshots,
    load_fedwatch_history,
)
from macro_context_reader.market_pricing.fedwatch.parser import (
    _parse_snapshot_date_from_filename,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_SNAPSHOTS_DIR = REPO_ROOT / "data" / "market_pricing" / "fedwatch_snapshots"
SAMPLE_CSV = SAMPLE_SNAPSHOTS_DIR / "FedMeetingHistory_20260414.csv"
SEED_PRESENT = SAMPLE_CSV.exists()


class TestListSnapshots:
    def test_returns_list(self):
        assert isinstance(list_available_snapshots(), list)

    @pytest.mark.skipif(not SEED_PRESENT, reason="Seed CSV not present")
    def test_finds_seed_csv(self):
        names = [s.name for s in list_available_snapshots()]
        assert "FedMeetingHistory_20260414.csv" in names

    @pytest.mark.skipif(not SEED_PRESENT, reason="Seed CSV not present")
    def test_sorted_ascending(self):
        snaps = list_available_snapshots()
        dates = [_parse_snapshot_date_from_filename(s) for s in snaps]
        assert dates == sorted(dates)

    def test_empty_folder_returns_empty(self, tmp_path):
        assert list_available_snapshots(tmp_path) == []

    def test_skips_invalid_filename(self, tmp_path):
        (tmp_path / "FedMeetingHistory_random.csv").write_text("noop")
        assert list_available_snapshots(tmp_path) == []


@pytest.mark.skipif(not SEED_PRESENT, reason="Seed CSV not present")
class TestLoadAllSnapshots:
    def test_loads_combined_dataframe(self):
        df = load_all_snapshots()
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 1000

    def test_has_source_snapshot_date(self):
        df = load_all_snapshots()
        assert "source_snapshot_date" in df.columns
        assert pd.api.types.is_datetime64_any_dtype(df["source_snapshot_date"])


class TestLoadAllSnapshotsErrors:
    def test_raises_when_no_snapshots(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="No snapshots"):
            load_all_snapshots(tmp_path)


@pytest.mark.skipif(not SEED_PRESENT, reason="Seed CSV not present")
class TestDedup:
    def test_no_duplicates_on_primary_key(self):
        df = load_all_snapshots()
        dup = df.duplicated(subset=["observation_date", "meeting_date", "rate_bucket_low"])
        assert dup.sum() == 0

    def test_dedup_keeps_latest_snapshot(self, tmp_path):
        """Two copies of same source CSV under different filenames -> later wins."""
        early = tmp_path / "FedMeetingHistory_20260101.csv"
        late = tmp_path / "FedMeetingHistory_20260414.csv"
        shutil.copy(SAMPLE_CSV, early)
        shutil.copy(SAMPLE_CSV, late)

        df = load_all_snapshots(tmp_path)
        # All rows should report the LATEST snapshot date as winner
        assert (df["source_snapshot_date"] == pd.Timestamp("2026-04-14")).all()


@pytest.mark.skipif(not SEED_PRESENT, reason="Seed CSV not present")
class TestMasterParquet:
    def test_build_creates_parquet(self, tmp_path):
        out = tmp_path / "master.parquet"
        df = build_master_dataset(output_path=out)
        assert out.exists()
        assert len(df) > 0

    def test_roundtrip_parquet(self, tmp_path):
        out = tmp_path / "master.parquet"
        built = build_master_dataset(output_path=out)
        read = pd.read_parquet(out)
        assert len(built) == len(read)
        assert set(built.columns) == set(read.columns)


@pytest.mark.skipif(not SEED_PRESENT, reason="Seed CSV not present")
class TestLoadFedwatchHistory:
    def test_returns_dataframe(self):
        df = load_fedwatch_history(rebuild=True)
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    def test_date_filter(self):
        df = load_fedwatch_history(
            start_date="2026-01-01", end_date="2026-04-14", rebuild=True
        )
        assert df["observation_date"].min() >= pd.Timestamp("2026-01-01")
        assert df["observation_date"].max() <= pd.Timestamp("2026-04-14")


class TestWarningOnInvalidFile:
    """Invalid files should trigger warnings instead of silent skip."""

    def test_warns_on_wrong_prefix(self, tmp_path, caplog):
        import logging

        (tmp_path / "random_name.csv").write_text("dummy,content")

        with caplog.at_level(logging.WARNING, logger="macro_context_reader.market_pricing.fedwatch.loader"):
            result = list_available_snapshots(tmp_path)

        assert result == []
        assert any(
            "Ignoring CSV with unexpected name" in r.message for r in caplog.records
        ), f"Expected warning not found: {[r.message for r in caplog.records]}"

    def test_warns_on_bad_date_pattern(self, tmp_path, caplog):
        import logging

        (tmp_path / "FedMeetingHistory_notadate.csv").write_text("dummy,content")

        with caplog.at_level(logging.WARNING, logger="macro_context_reader.market_pricing.fedwatch.loader"):
            result = list_available_snapshots(tmp_path)

        assert result == []
        assert any(
            "Cannot parse snapshot date" in r.message for r in caplog.records
        ), f"Expected warning not found: {[r.message for r in caplog.records]}"

    @pytest.mark.skipif(not SEED_PRESENT, reason="Seed CSV not present")
    def test_valid_file_mixed_with_invalid_still_loaded(self, tmp_path, caplog):
        import logging

        shutil.copy(SAMPLE_CSV, tmp_path / "FedMeetingHistory_20260414.csv")
        (tmp_path / "random_garbage.csv").write_text("x")

        with caplog.at_level(logging.WARNING, logger="macro_context_reader.market_pricing.fedwatch.loader"):
            result = list_available_snapshots(tmp_path)

        assert len(result) == 1
        assert result[0].name == "FedMeetingHistory_20260414.csv"
        assert any("Ignoring" in r.message for r in caplog.records)
