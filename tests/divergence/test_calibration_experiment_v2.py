"""PRD-300 / CC-2a-v2 — tests for dual-classification experiment."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from macro_context_reader.divergence.calibration_experiment_v2 import (
    CLASSIFIERS,
    FEATURES_FOR_CLASSIFICATION,
    HIT_RATE_THRESHOLD,
    MIN_NONZERO_SIGNALS_VAL,
    TARGET_NAMES,
    TRAIN_END_DATE,
    EqualWeightedClassifier,
    _scenario_and_recommendation,
    compute_classification_metrics,
    evaluate_on_validation,
    extract_feature_importance,
    prepare_classification_data,
    run_full_experiment_v2,
    split_train_validation,
    walk_forward_cv_classification,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def _synth_features(n: int, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2021-01-01", periods=n, freq="MS", name="meeting_date")
    data = {col: rng.normal(size=n) for col in FEATURES_FOR_CLASSIFICATION}
    return pd.DataFrame(data, index=idx)


def _synth_targets(n: int, seed: int = 42) -> pd.Series:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2021-01-01", periods=n, freq="MS", name="meeting_date")
    return pd.Series(rng.choice([-1, 0, 1], size=n), index=idx)


# ============================================================
# TestEqualWeightedClassifier
# ============================================================


class TestEqualWeightedClassifier:
    def test_fit_predict_shapes(self):
        X = _synth_features(20)
        y = _synth_targets(20)
        clf = EqualWeightedClassifier().fit(X, y)
        preds = clf.predict(X)
        assert len(preds) == 20

    def test_predicts_three_classes(self):
        X = _synth_features(40)
        y = _synth_targets(40)
        clf = EqualWeightedClassifier().fit(X, y)
        preds = clf.predict(X)
        assert set(np.unique(preds)).issubset({-1, 0, 1})

    def test_threshold_respects_training_distribution(self):
        # y has plenty of each class; classifier must produce at least one of
        # each predicted class on the training set itself.
        rng = np.random.default_rng(0)
        idx = pd.date_range("2021-01-01", periods=30, freq="MS", name="meeting_date")
        # Build features where composite z-score correlates with y.
        y = pd.Series(np.tile([-1, 0, 1], 10), index=idx)
        # Inject signal: features are all y + noise so composite ~ y.
        X_vals = y.values[:, None] * np.ones((1, len(FEATURES_FOR_CLASSIFICATION)))
        X_vals = X_vals + rng.normal(scale=0.1, size=X_vals.shape)
        X = pd.DataFrame(X_vals, index=idx, columns=FEATURES_FOR_CLASSIFICATION)
        clf = EqualWeightedClassifier().fit(X, y)
        preds = clf.predict(X)
        classes = set(np.unique(preds))
        assert -1 in classes and 1 in classes

    def test_feature_importance_uniform(self):
        X = _synth_features(20)
        y = _synth_targets(20)
        clf = EqualWeightedClassifier().fit(X, y)
        imp = clf.feature_importance_
        assert np.allclose(imp.values, 1.0 / len(FEATURES_FOR_CLASSIFICATION))
        assert abs(imp.sum() - 1.0) < 1e-9

    def test_handles_zero_std_feature(self):
        X = _synth_features(20)
        X[FEATURES_FOR_CLASSIFICATION[0]] = 3.14  # constant
        y = _synth_targets(20)
        clf = EqualWeightedClassifier().fit(X, y)
        # No crash, predict returns integer class labels
        preds = clf.predict(X)
        assert preds.dtype.kind == "i"
        assert len(preds) == 20


# ============================================================
# TestPrepareClassificationData
# ============================================================


class TestPrepareClassificationData:
    def _master(self, n=20):
        return _synth_features(n)

    def _targets(self, n=20, nan_indices: list[int] | None = None):
        y = _synth_targets(n)
        df = pd.DataFrame(
            {
                "target_surprise_class": y.astype("Int64"),
                "target_regime_class": y.astype("Int64"),
            },
            index=y.index,
        )
        if nan_indices:
            for i in nan_indices:
                df.iloc[i] = pd.NA
        return df

    def test_drops_rows_with_nan_target(self):
        master = self._master(20)
        targets = self._targets(20, nan_indices=[0, 5, 10])
        X, y = prepare_classification_data(master, targets, "target_surprise_class")
        assert len(X) == 17
        assert len(y) == 17
        assert y.notna().all()

    def test_drops_rows_with_nan_feature(self):
        master = self._master(20)
        master.iloc[3, 0] = np.nan
        master.iloc[7, 2] = np.nan
        targets = self._targets(20)
        X, y = prepare_classification_data(master, targets, "target_surprise_class")
        assert len(X) == 18
        assert X.notna().all().all()

    def test_returns_integer_y(self):
        master = self._master(20)
        targets = self._targets(20)
        X, y = prepare_classification_data(master, targets, "target_surprise_class")
        assert y.dtype.kind == "i"

    def test_y_values_in_valid_set(self):
        master = self._master(20)
        targets = self._targets(20)
        X, y = prepare_classification_data(master, targets, "target_regime_class")
        assert set(y.unique()).issubset({-1, 0, 1})

    def test_feature_list_matches_constant(self):
        master = self._master(20)
        targets = self._targets(20)
        X, y = prepare_classification_data(master, targets, "target_surprise_class")
        assert list(X.columns) == FEATURES_FOR_CLASSIFICATION


# ============================================================
# TestSplitTrainValidation
# ============================================================


class TestSplitTrainValidation:
    def test_chronological_split(self):
        idx = pd.date_range("2021-01-01", periods=50, freq="MS", name="meeting_date")
        X = pd.DataFrame({"a": range(50)}, index=idx)
        y = pd.Series(range(50), index=idx)
        X_tr, y_tr, X_val, y_val = split_train_validation(X, y, train_end=pd.Timestamp("2024-06-30"))
        assert X_tr.index.max() <= pd.Timestamp("2024-06-30")
        assert X_val.index.min() > pd.Timestamp("2024-06-30")
        assert len(X_tr) + len(X_val) == 50


# ============================================================
# TestComputeClassificationMetrics
# ============================================================


class TestComputeClassificationMetrics:
    def test_perfect_predictions_give_accuracy_1(self):
        y = np.array([-1, 0, 1, -1, 1, 0])
        m = compute_classification_metrics(y, y)
        assert m["accuracy"] == 1.0
        assert m["hit_rate_nonzero"] == 1.0

    def test_hit_rate_computation_correct(self):
        # 4 non-zero preds; 3 correct (sign matches).
        truth = np.array([1, -1, 1, -1, 0, 0])
        pred = np.array([1, -1, 1, 1, 0, 0])  # last nonzero (idx=3) wrong
        m = compute_classification_metrics(truth, pred)
        assert m["n_nonzero_pred"] == 4
        assert abs(m["hit_rate_nonzero"] - 0.75) < 1e-9

    def test_handles_all_zero_predictions(self):
        truth = np.array([1, -1, 1, -1])
        pred = np.array([0, 0, 0, 0])
        m = compute_classification_metrics(truth, pred)
        assert m["n_nonzero_pred"] == 0
        assert m["hit_rate_nonzero"] is None

    def test_confusion_matrix_shape(self):
        truth = np.array([0, 1, -1])
        pred = np.array([0, 1, -1])
        m = compute_classification_metrics(truth, pred)
        cm = np.asarray(m["confusion"])
        assert cm.shape == (3, 3)

    def test_signal_frequency_computation(self):
        truth = np.zeros(14, dtype=int)
        pred = np.array([1, 1, -1, 1, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0])
        m = compute_classification_metrics(truth, pred)
        assert abs(m["signal_frequency"] - (5 / 14)) < 1e-9


# ============================================================
# TestWalkForwardCVClassification
# ============================================================


class TestWalkForwardCVClassification:
    def test_respects_temporal_order(self):
        X = _synth_features(30)
        y = _synth_targets(30)
        factory = CLASSIFIERS["logistic_l2"]
        result = walk_forward_cv_classification(X, y, factory, n_splits=5)
        assert "fold_0" in result and "aggregate" in result

    def test_five_folds_produced(self):
        X = _synth_features(30)
        y = _synth_targets(30)
        factory = CLASSIFIERS["equal_weighted"]
        result = walk_forward_cv_classification(X, y, factory, n_splits=5)
        fold_keys = [k for k in result.keys() if k.startswith("fold_")]
        assert len(fold_keys) == 5

    def test_aggregate_metrics_computed(self):
        X = _synth_features(30)
        y = _synth_targets(30)
        factory = CLASSIFIERS["random_forest"]
        result = walk_forward_cv_classification(X, y, factory, n_splits=5)
        agg = result["aggregate"]
        assert "mean_hit_rate_nonzero" in agg
        assert "std_hit_rate_nonzero" in agg
        assert "mean_accuracy" in agg


# ============================================================
# TestExtractFeatureImportance
# ============================================================


class TestExtractFeatureImportance:
    def test_logistic_regression_importance(self):
        X = _synth_features(40)
        y = _synth_targets(40)
        pipe = Pipeline(
            [
                ("scaler", StandardScaler()),
                ("clf", LogisticRegression(max_iter=2000, random_state=42)),
            ]
        )
        pipe.fit(X.values, y.values)
        imp = extract_feature_importance(pipe, list(X.columns))
        assert imp is not None
        assert len(imp) == len(FEATURES_FOR_CLASSIFICATION)
        assert abs(imp.sum() - 1.0) < 1e-6

    def test_random_forest_importance(self):
        X = _synth_features(40)
        y = _synth_targets(40)
        rf = RandomForestClassifier(n_estimators=10, random_state=42)
        rf.fit(X.values, y.values)
        imp = extract_feature_importance(rf, list(X.columns))
        assert imp is not None
        assert len(imp) == len(FEATURES_FOR_CLASSIFICATION)
        assert abs(imp.sum() - 1.0) < 1e-6

    def test_equal_weighted_uniform(self):
        X = _synth_features(30)
        y = _synth_targets(30)
        ew = EqualWeightedClassifier().fit(X, y)
        imp = extract_feature_importance(ew, list(X.columns))
        assert imp is not None
        expected = 1.0 / len(FEATURES_FOR_CLASSIFICATION)
        assert np.allclose(imp.values, expected)

    def test_returns_none_for_svc_rbf(self):
        X = _synth_features(30)
        y = _synth_targets(30)
        pipe = Pipeline(
            [
                ("scaler", StandardScaler()),
                ("clf", SVC(kernel="rbf", random_state=42)),
            ]
        )
        pipe.fit(X.values, y.values)
        imp = extract_feature_importance(pipe, list(X.columns))
        assert imp is None


# ============================================================
# TestEvaluateOnValidation
# ============================================================


class TestEvaluateOnValidation:
    def test_returns_predictions_and_importance(self):
        X = _synth_features(40)
        y = _synth_targets(40)
        X_tr, X_val = X.iloc[:30], X.iloc[30:]
        y_tr, y_val = y.iloc[:30], y.iloc[30:]
        factory = CLASSIFIERS["logistic_l2"]
        result = evaluate_on_validation(X_tr, y_tr, X_val, y_val, factory)
        assert "predictions" in result
        assert "feature_importance" in result
        assert len(result["predictions"]) == len(X_val)


# ============================================================
# TestScenarioRecommendation
# ============================================================


class TestScenarioRecommendation:
    def _make_results(self, surprise_winner: bool, regime_winner: bool) -> pd.DataFrame:
        rows = []
        for tgt in ["target_surprise_class", "target_regime_class"]:
            winner_row = (tgt == "target_surprise_class" and surprise_winner) or \
                         (tgt == "target_regime_class" and regime_winner)
            rows.append({
                "target": tgt,
                "classifier": "equal_weighted",
                "meets_hit_rate_threshold": winner_row,
                "meets_coverage_gate": winner_row,
                "stability_gate_passed": winner_row,
            })
            rows.append({
                "target": tgt,
                "classifier": "logistic_l2",
                "meets_hit_rate_threshold": False,
                "meets_coverage_gate": False,
                "stability_gate_passed": False,
            })
        return pd.DataFrame(rows)

    def test_scenario_A_both_winners(self):
        scenario, _ = _scenario_and_recommendation(self._make_results(True, True))
        assert scenario == "A"

    def test_scenario_B_regime_only(self):
        scenario, _ = _scenario_and_recommendation(self._make_results(False, True))
        assert scenario == "B"

    def test_scenario_C_surprise_only(self):
        scenario, _ = _scenario_and_recommendation(self._make_results(True, False))
        assert scenario == "C"

    def test_scenario_D_no_winners(self):
        scenario, _ = _scenario_and_recommendation(self._make_results(False, False))
        assert scenario == "D"


# ============================================================
# TestRunFullExperimentV2Integration — uses real artifacts
# ============================================================


class TestRunFullExperimentV2Integration:
    REAL_MASTER = REPO_ROOT / "data/divergence/calibration_features.parquet"
    REAL_TARGETS_V2 = REPO_ROOT / "data/divergence/targets_v2.parquet"

    def _artifacts_present(self) -> bool:
        return self.REAL_MASTER.exists() and self.REAL_TARGETS_V2.exists()

    def test_produces_10_combinations(self, tmp_path):
        if not self._artifacts_present():
            pytest.skip("real master/targets_v2 artifacts not present")
        results_path = tmp_path / "results.parquet"
        report_path = tmp_path / "report.md"
        results = run_full_experiment_v2(
            master_table_path=self.REAL_MASTER,
            targets_v2_path=self.REAL_TARGETS_V2,
            output_results_path=results_path,
            output_report_path=report_path,
        )
        assert len(results) == len(TARGET_NAMES) * len(CLASSIFIERS)

    def test_results_columns_present(self, tmp_path):
        if not self._artifacts_present():
            pytest.skip("real master/targets_v2 artifacts not present")
        results_path = tmp_path / "results.parquet"
        report_path = tmp_path / "report.md"
        results = run_full_experiment_v2(
            master_table_path=self.REAL_MASTER,
            targets_v2_path=self.REAL_TARGETS_V2,
            output_results_path=results_path,
            output_report_path=report_path,
        )
        required = {
            "target",
            "classifier",
            "cv_mean_hit_rate",
            "cv_std_hit_rate",
            "val_hit_rate",
            "val_n_nonzero_pred",
            "val_n_nonzero_true",
            "val_accuracy",
            "val_precision_up",
            "val_precision_down",
            "val_signal_frequency",
            "meets_hit_rate_threshold",
            "meets_coverage_gate",
            "stability_gate_passed",
            "top_features",
            "confusion_matrix",
        }
        assert required.issubset(results.columns)

    def test_report_markdown_generated(self, tmp_path):
        if not self._artifacts_present():
            pytest.skip("real master/targets_v2 artifacts not present")
        results_path = tmp_path / "results.parquet"
        report_path = tmp_path / "report.md"
        run_full_experiment_v2(
            master_table_path=self.REAL_MASTER,
            targets_v2_path=self.REAL_TARGETS_V2,
            output_results_path=results_path,
            output_report_path=report_path,
        )
        assert report_path.exists()
        body = report_path.read_text(encoding="utf-8")
        for header in [
            "## 1. Experiment Setup",
            "## 2. Target Distributions",
            "## 3. Results",
            "## 4. Winners",
            "## 5. Top Features",
            "## 6. Confusion Matrices",
            "## 7. Trading Workflow Implications",
            "## 8. Recommendation",
            "## 9. Caveats",
        ]:
            assert header in body, f"Missing header: {header}"
        # Scenario letter must be stated explicitly.
        assert ("Scenario A" in body or "Scenario B" in body
                or "Scenario C" in body or "Scenario D" in body)

    def test_parquet_persisted(self, tmp_path):
        if not self._artifacts_present():
            pytest.skip("real master/targets_v2 artifacts not present")
        results_path = tmp_path / "results.parquet"
        report_path = tmp_path / "report.md"
        run_full_experiment_v2(
            master_table_path=self.REAL_MASTER,
            targets_v2_path=self.REAL_TARGETS_V2,
            output_results_path=results_path,
            output_report_path=report_path,
        )
        assert results_path.exists()
        reloaded = pd.read_parquet(results_path)
        assert len(reloaded) == len(TARGET_NAMES) * len(CLASSIFIERS)


# ============================================================
# Constants guard
# ============================================================


class TestConstants:
    def test_hit_rate_threshold_is_0_60(self):
        assert HIT_RATE_THRESHOLD == 0.60

    def test_min_nonzero_signals_val_is_8(self):
        assert MIN_NONZERO_SIGNALS_VAL == 8

    def test_train_end_date_matches_v1(self):
        assert TRAIN_END_DATE == pd.Timestamp("2024-06-30")

    def test_five_classifiers_registered(self):
        assert set(CLASSIFIERS.keys()) == {
            "equal_weighted", "logistic_l2", "ridge", "svc_rbf", "random_forest"
        }

    def test_feature_list_has_11_features(self):
        assert len(FEATURES_FOR_CLASSIFICATION) == 11
