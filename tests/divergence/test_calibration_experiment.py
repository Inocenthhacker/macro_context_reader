"""PRD-300 / CC-2a — tests for calibration experiment."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from macro_context_reader.divergence.calibration_experiment import (
    FEATURES_FOR_CALIBRATION,
    METHODS,
    PRE_COMMITTED_THRESHOLD,
    TRAIN_END_DATE,
    EqualWeightedRegressor,
    evaluate_on_validation,
    prepare_features_targets,
    run_full_experiment,
    split_train_validation,
    walk_forward_cv_evaluation,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def _synthetic_master(n=30, start="2021-01-01"):
    rng = np.random.RandomState(42)
    dates = pd.DatetimeIndex(
        pd.date_range(start, periods=n, freq="45D"), name="meeting_date"
    )
    return pd.DataFrame(
        {c: rng.normal(0, 1, n) for c in FEATURES_FOR_CALIBRATION},
        index=dates,
    )


def _synthetic_targets(master, signal_cols=None, noise_std=0.5, seed=42):
    rng = np.random.RandomState(seed)
    if signal_cols is None:
        signal_cols = FEATURES_FOR_CALIBRATION[:2]
    y = master[signal_cols].sum(axis=1) + rng.normal(0, noise_std, len(master))
    return pd.DataFrame(
        {
            "target_A_fedwatch_surprise": y,
            "target_D_rrd_change_5d": y + rng.normal(0, 0.1, len(master)),
            "target_E_eurusd_5d": y + rng.normal(0, 0.2, len(master)),
            "target_F_eurusd_21d": y + rng.normal(0, 0.3, len(master)),
        },
        index=master.index,
    )


# ============================================================
# TestPrepareFeaturesTargets
# ============================================================


class TestPrepareFeaturesTargets:
    def test_alignment_on_meeting_date(self):
        m = _synthetic_master()
        t = _synthetic_targets(m)
        X, y = prepare_features_targets(m, t, "target_A_fedwatch_surprise")
        assert list(X.index) == list(y.index)

    def test_drops_rows_with_nan_target(self):
        m = _synthetic_master()
        t = _synthetic_targets(m)
        t.iloc[0, 0] = float("nan")
        X, y = prepare_features_targets(m, t, "target_A_fedwatch_surprise")
        assert len(X) == len(m) - 1
        assert len(y) == len(m) - 1

    def test_drops_rows_with_nan_feature(self):
        m = _synthetic_master()
        t = _synthetic_targets(m)
        m.iloc[0, 0] = float("nan")
        X, y = prepare_features_targets(m, t, "target_A_fedwatch_surprise")
        assert len(X) == len(m) - 1

    def test_feature_columns_match_constant(self):
        m = _synthetic_master()
        t = _synthetic_targets(m)
        X, _ = prepare_features_targets(m, t, "target_A_fedwatch_surprise")
        assert list(X.columns) == FEATURES_FOR_CALIBRATION


# ============================================================
# TestSplitTrainValidation
# ============================================================


class TestSplitTrainValidation:
    def test_no_shuffle_chronological(self):
        m = _synthetic_master(n=42, start="2021-01-27")
        t = _synthetic_targets(m)
        X, y = prepare_features_targets(m, t, "target_A_fedwatch_surprise")
        X_tr, y_tr, X_val, y_val = split_train_validation(X, y)
        assert X_tr.index.max() < X_val.index.min()

    def test_train_ends_at_specified_date(self):
        m = _synthetic_master(n=42, start="2021-01-27")
        t = _synthetic_targets(m)
        X, y = prepare_features_targets(m, t, "target_A_fedwatch_surprise")
        X_tr, _, _, _ = split_train_validation(X, y, train_end=TRAIN_END_DATE)
        assert X_tr.index.max() <= TRAIN_END_DATE

    def test_validation_starts_after_train(self):
        m = _synthetic_master(n=42, start="2021-01-27")
        t = _synthetic_targets(m)
        X, y = prepare_features_targets(m, t, "target_A_fedwatch_surprise")
        X_tr, _, X_val, _ = split_train_validation(X, y, train_end=TRAIN_END_DATE)
        assert X_val.index.min() > X_tr.index.max()

    def test_approximate_30_12_split(self):
        master = pd.read_parquet(REPO_ROOT / "data/divergence/calibration_features.parquet") \
            if (REPO_ROOT / "data/divergence/calibration_features.parquet").exists() \
            else _synthetic_master(n=42, start="2021-01-27")
        t = _synthetic_targets(master)
        X, y = prepare_features_targets(master, t, "target_A_fedwatch_surprise")
        X_tr, _, X_val, _ = split_train_validation(X, y, train_end=TRAIN_END_DATE)
        assert 25 <= len(X_tr) <= 32, f"train size {len(X_tr)} not in ~30 range"
        assert 10 <= len(X_val) <= 16, f"val size {len(X_val)} not in ~12 range"


# ============================================================
# TestWalkForwardCV
# ============================================================


class TestWalkForwardCV:
    def _data(self):
        m = _synthetic_master(n=28)
        t = _synthetic_targets(m)
        X, y = prepare_features_targets(m, t, "target_A_fedwatch_surprise")
        return X, y

    def test_5_folds_produced(self):
        X, y = self._data()
        out = walk_forward_cv_evaluation(X, y, LinearFactory, n_splits=5, min_train_size=13)
        fold_keys = [k for k in out if k.startswith("fold_")]
        assert len(fold_keys) == 5
        assert "aggregate" in out

    def test_each_fold_train_before_test_chronologically(self):
        X, y = self._data()
        # Rebuild manually to access indices
        from sklearn.model_selection import TimeSeriesSplit
        tscv = TimeSeriesSplit(n_splits=5, test_size=3)
        for train_idx, test_idx in tscv.split(X):
            assert X.index[train_idx].max() < X.index[test_idx].min()

    def test_expanding_window(self):
        X, y = self._data()
        from sklearn.model_selection import TimeSeriesSplit
        tscv = TimeSeriesSplit(n_splits=5, test_size=3)
        sizes = [len(train_idx) for train_idx, _ in tscv.split(X)]
        assert all(sizes[i] < sizes[i + 1] for i in range(len(sizes) - 1))

    def test_metrics_computed(self):
        X, y = self._data()
        out = walk_forward_cv_evaluation(X, y, LinearFactory, n_splits=5, min_train_size=13)
        for k, v in out.items():
            if k.startswith("fold_"):
                assert "spearman_ic" in v
                assert "rmse" in v
                assert "r2" in v


def LinearFactory():
    from sklearn.linear_model import LinearRegression
    return LinearRegression()


# ============================================================
# TestEqualWeightedRegressor
# ============================================================


class TestEqualWeightedRegressor:
    def test_fit_predict_shapes(self):
        m = _synthetic_master(n=30)
        t = _synthetic_targets(m)
        X, y = prepare_features_targets(m, t, "target_A_fedwatch_surprise")
        mdl = EqualWeightedRegressor().fit(X, y)
        preds = mdl.predict(X)
        assert len(preds) == len(y)

    def test_coefficients_equal_sign(self):
        m = _synthetic_master(n=30)
        t = _synthetic_targets(m)
        X, y = prepare_features_targets(m, t, "target_A_fedwatch_surprise")
        mdl = EqualWeightedRegressor().fit(X, y)
        coefs = mdl.coef_
        assert np.all(coefs >= 0) or np.all(coefs <= 0)

    def test_is_baseline_not_winning_by_chance(self):
        rng = np.random.RandomState(0)
        X = pd.DataFrame(
            rng.normal(0, 1, (60, len(FEATURES_FOR_CALIBRATION))),
            columns=FEATURES_FOR_CALIBRATION,
        )
        y = pd.Series(rng.normal(0, 1, 60))
        mdl = EqualWeightedRegressor().fit(X.iloc[:40], y.iloc[:40])
        preds = mdl.predict(X.iloc[40:])
        from scipy.stats import spearmanr
        ic = spearmanr(y.iloc[40:].values, preds).correlation
        assert abs(ic) < 0.5  # near zero IC on random data


# ============================================================
# TestEvaluateOnValidation
# ============================================================


class TestEvaluateOnValidation:
    def _data(self):
        m = _synthetic_master(n=42, start="2021-01-27")
        t = _synthetic_targets(m)
        X, y = prepare_features_targets(m, t, "target_A_fedwatch_surprise")
        return split_train_validation(X, y, train_end=TRAIN_END_DATE)

    def test_returns_all_metrics(self):
        X_tr, y_tr, X_val, y_val = self._data()
        out = evaluate_on_validation(X_tr, y_tr, X_val, y_val, LinearFactory)
        for k in ["spearman_ic", "pearson_corr", "rmse", "mae", "r2", "predictions", "coefficients"]:
            assert k in out

    def test_predictions_length_matches_validation(self):
        X_tr, y_tr, X_val, y_val = self._data()
        out = evaluate_on_validation(X_tr, y_tr, X_val, y_val, LinearFactory)
        assert len(out["predictions"]) == len(y_val)

    def test_coefficients_length_matches_features(self):
        X_tr, y_tr, X_val, y_val = self._data()
        out = evaluate_on_validation(X_tr, y_tr, X_val, y_val, LinearFactory)
        assert len(out["coefficients"]) == len(FEATURES_FOR_CALIBRATION)


# ============================================================
# TestRunFullExperimentIntegration
# ============================================================


REAL_MASTER = REPO_ROOT / "data/divergence/calibration_features.parquet"
REAL_TARGETS = REPO_ROOT / "data/divergence/targets.parquet"


@pytest.mark.skipif(
    not (REAL_MASTER.exists() and REAL_TARGETS.exists()),
    reason="real master + targets parquets not yet built",
)
class TestRunFullExperimentIntegration:
    @pytest.fixture(scope="class")
    def results(self, tmp_path_factory):
        out_dir = tmp_path_factory.mktemp("exp")
        res = run_full_experiment(
            master_table_path=REAL_MASTER,
            targets_table_path=REAL_TARGETS,
            output_results_path=out_dir / "experiment_results.parquet",
            output_report_path=out_dir / "experiment_report.md",
        )
        return res, out_dir

    def test_produces_20_combinations(self, results):
        res, _ = results
        assert len(res) == 20

    def test_all_results_have_expected_columns(self, results):
        res, _ = results
        for c in ["target", "method", "cv_mean_ic", "val_ic", "meets_threshold"]:
            assert c in res.columns

    def test_report_markdown_generated(self, results):
        _, out_dir = results
        report = out_dir / "experiment_report.md"
        assert report.exists()
        text = report.read_text(encoding="utf-8")
        for section in ["Experiment Setup", "Results Table", "Recommendation"]:
            assert section in text

    def test_parquet_persisted(self, results):
        _, out_dir = results
        p = out_dir / "experiment_results.parquet"
        assert p.exists()
        reloaded = pd.read_parquet(p)
        assert len(reloaded) == 20
