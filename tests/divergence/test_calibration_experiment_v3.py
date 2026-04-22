"""PRD-300 / CC-2a-v3 — integration tests for the dual-classification experiment v3."""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from macro_context_reader.divergence.calibration_experiment_v2 import (
    TARGET_NAMES,
    _scenario_and_recommendation,
)
from macro_context_reader.divergence.calibration_experiment_v3 import (
    FEATURES_FOR_CLASSIFICATION_V3,
    prepare_classification_data_v3,
    run_full_experiment_v3,
)
from macro_context_reader.divergence.feature_engineering import (
    ENGINEERED_FEATURES,
    build_features_v3_table,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


# ============================================================
# TestFeaturesForClassificationV3Constant
# ============================================================


class TestFeaturesForClassificationV3Constant:
    def test_has_18_features(self):
        assert len(FEATURES_FOR_CLASSIFICATION_V3) == 18

    def test_all_engineered_present(self):
        for f in ENGINEERED_FEATURES:
            assert f in FEATURES_FOR_CLASSIFICATION_V3


# ============================================================
# TestPrepareClassificationDataV3
# ============================================================


@pytest.fixture(scope="module")
def features_v3_table():
    return build_features_v3_table(
        master_table_path=REPO_ROOT / "data/divergence/calibration_features.parquet",
        rrd_path=REPO_ROOT / "data/market_pricing/real_rate_differential.parquet",
        output_path=REPO_ROOT / "data/divergence/calibration_features_v3.parquet",
    )


@pytest.fixture(scope="module")
def targets_v2_table():
    return pd.read_parquet(REPO_ROOT / "data/divergence/targets_v2.parquet")


class TestPrepareClassificationDataV3:
    def test_drops_rows_with_nan_engineered_features(self, features_v3_table, targets_v2_table):
        X, y = prepare_classification_data_v3(
            features_v3_table, targets_v2_table, "target_surprise_class"
        )
        # Master is 42 rows; v3 drops the first 2 (acceleration NaN)
        # plus any target NaN. Expect ≤ 40.
        assert len(X) <= 40
        assert len(X) >= 38
        assert len(X) == len(y)

    def test_feature_columns_match_v3_constant(self, features_v3_table, targets_v2_table):
        X, _ = prepare_classification_data_v3(
            features_v3_table, targets_v2_table, "target_surprise_class"
        )
        assert X.columns.tolist() == FEATURES_FOR_CLASSIFICATION_V3

    def test_logs_dropped_rows_count(self, features_v3_table, targets_v2_table, caplog):
        caplog.set_level(logging.INFO, logger="macro_context_reader.divergence.calibration_experiment_v3")
        prepare_classification_data_v3(
            features_v3_table, targets_v2_table, "target_surprise_class"
        )
        # At least one INFO record from the module should describe the drop.
        module_records = [
            r for r in caplog.records
            if r.name == "macro_context_reader.divergence.calibration_experiment_v3"
        ]
        assert any("dropped" in r.getMessage() for r in module_records), (
            "expected an INFO log reporting the number of dropped rows"
        )

    def test_returns_integer_y(self, features_v3_table, targets_v2_table):
        _, y = prepare_classification_data_v3(
            features_v3_table, targets_v2_table, "target_regime_class"
        )
        assert np.issubdtype(y.dtype, np.integer)


# ============================================================
# TestRunFullExperimentV3Integration
# ============================================================


@pytest.fixture(scope="module")
def v3_run(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("v3_experiment")
    features_out = REPO_ROOT / "data/divergence/calibration_features_v3.parquet"
    results_out = tmp / "experiment_v3_results.parquet"
    report_out = tmp / "experiment_v3_report.md"
    results = run_full_experiment_v3(
        features_v3_path=features_out,
        targets_v2_path=REPO_ROOT / "data/divergence/targets_v2.parquet",
        master_table_path=REPO_ROOT / "data/divergence/calibration_features.parquet",
        rrd_path=REPO_ROOT / "data/market_pricing/real_rate_differential.parquet",
        v2_results_path=REPO_ROOT / "data/divergence/experiment_v2_results.parquet",
        output_results_path=results_out,
        output_report_path=report_out,
    )
    return results, results_out, report_out


class TestRunFullExperimentV3Integration:
    def test_produces_10_combinations(self, v3_run):
        results, _, _ = v3_run
        assert len(results) == 10  # 2 targets × 5 classifiers

    def test_report_includes_v2_comparison(self, v3_run):
        _, _, report_path = v3_run
        text = report_path.read_text(encoding="utf-8")
        assert "## 4. V2 vs V3 Comparison" in text
        # At least the comparison table header or a "rescued"/"regression" keyword
        # should be present (columns are meaningful only when v2 results exist).
        assert "v2 val_hit" in text or "v2 results not available" in text

    def test_report_lists_engineered_features_in_winners(self, v3_run):
        results, _, report_path = v3_run
        # Report must contain the engineered-feature importance section regardless
        # of whether there are winners.
        text = report_path.read_text(encoding="utf-8")
        assert "## 5. Engineered Feature Importance" in text
        # top_features column should be a string (possibly empty)
        assert results["top_features"].apply(lambda v: isinstance(v, str)).all()

    def test_parquet_persisted(self, v3_run):
        _, results_path, _ = v3_run
        assert results_path.exists()
        reread = pd.read_parquet(results_path)
        assert len(reread) == 10
        for col in ("target", "classifier", "val_hit_rate", "val_n_nonzero_pred",
                    "meets_hit_rate_threshold", "meets_coverage_gate", "stability_gate_passed"):
            assert col in reread.columns

    def test_recommendation_logic_preserved(self, v3_run):
        results, _, _ = v3_run
        # Same function from v2 must still return a valid scenario letter.
        scenario, text = _scenario_and_recommendation(results)
        assert scenario in {"A", "B", "C", "D"}
        assert isinstance(text, str) and len(text) > 0

    def test_targets_both_evaluated(self, v3_run):
        results, _, _ = v3_run
        assert set(results["target"].unique()) == set(TARGET_NAMES)
