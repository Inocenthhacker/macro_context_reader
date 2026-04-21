"""CC-2a-v2 dual-classification experiment — PRD-300.

Architecture: 2 independent targets × 5 classifiers = 10 combinations.

Why classification instead of regression (v1 was IC-based):
- User workflow is regime detection + surprise confirmation, NOT magnitude
  prediction.
- Hit rate > 60% on non-zero signals is directly actionable as a trading
  metric.
- Classification with an explicit neutral class matches the "no trade"
  condition in the live workflow.

Classifiers tested:
- equal_weighted  — baseline: z-score features, sum their signed contributions,
                    threshold into {-1, 0, +1} using training-set quantiles.
- logistic_l2     — LogisticRegression penalty=l2, C=1, balanced class weights
                    (scaled via StandardScaler).
- ridge           — RidgeClassifier alpha=1, balanced class weights (scaled).
- svc_rbf         — SVC kernel=rbf, C=1, gamma=scale, balanced (scaled).
- random_forest   — RandomForest n_estimators=100, max_depth=3, balanced.

Pre-committed decision metrics (DO NOT adjust mid-experiment):
- PRIMARY: val hit_rate_nonzero > 0.60.
- COVERAGE GATE: val n_nonzero_pred >= 8.
- STABILITY GATE: CV mean hit_rate_nonzero > 0.5 AND val hit_rate_nonzero > 0.5
  (sign agreement between folds and hold-out).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression, RidgeClassifier
from sklearn.metrics import (
    confusion_matrix,
    precision_score,
    recall_score,
)
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

logger = logging.getLogger(__name__)


# ============================================================
# Pre-committed constants
# ============================================================

FEATURES_FOR_CLASSIFICATION: list[str] = [
    "statement_ensemble_net",
    "statement_fomc_roberta_net",
    "statement_llama_deepinfra_net",
    "minutes_lag_ensemble_net",
    "minutes_lag_fomc_roberta_net",
    "minutes_lag_llama_deepinfra_net",
    "fedwatch_implied_change_bps",
    "real_rate_diff_5y",
    "cleveland_national_score",
    "cleveland_consensus_score",
    "cleveland_divergence",
]

TRAIN_END_DATE: pd.Timestamp = pd.Timestamp("2024-06-30")
HIT_RATE_THRESHOLD: float = 0.60
MIN_NONZERO_SIGNALS_VAL: int = 8

RANDOM_SEED: int = 42
np.random.seed(RANDOM_SEED)


# ============================================================
# EqualWeightedClassifier — baseline
# ============================================================


class EqualWeightedClassifier:
    """Baseline: z-score features, average them, threshold into {-1, 0, +1}.

    Logic:
      z_i = (x_i - mean_i) / std_i
      composite = mean(z_i)  # equal weight, sign-aware

    Thresholds are fit on the training composite distribution and, where the
    training label distribution has enough non-zero class members, adjusted to
    match that distribution.
    """

    def __init__(self):
        self.feature_means_: Optional[pd.Series] = None
        self.feature_stds_: Optional[pd.Series] = None
        self.threshold_pos_: float = 0.0
        self.threshold_neg_: float = 0.0

    def fit(self, X, y):
        X_df = pd.DataFrame(X) if not isinstance(X, pd.DataFrame) else X
        y_arr = np.asarray(y).astype(int)

        self.feature_means_ = X_df.mean()
        self.feature_stds_ = X_df.std().replace(0.0, 1.0)

        X_z = (X_df - self.feature_means_) / self.feature_stds_
        composite_train = X_z.mean(axis=1)
        composite_arr = composite_train.values

        nonzero_mask = y_arr != 0
        if nonzero_mask.sum() >= 6:
            pos_vals = composite_arr[y_arr == 1]
            neg_vals = composite_arr[y_arr == -1]
            self.threshold_pos_ = (
                float(np.quantile(pos_vals, 0.25)) if len(pos_vals) >= 2 else 0.33
            )
            self.threshold_neg_ = (
                float(np.quantile(neg_vals, 0.75)) if len(neg_vals) >= 2 else -0.33
            )
        else:
            self.threshold_pos_ = float(np.quantile(composite_arr, 0.67))
            self.threshold_neg_ = float(np.quantile(composite_arr, 0.33))

        # Guard: if thresholds are inverted (pos < neg), fall back to global
        # quantiles. Can happen when classes are scrambled relative to the
        # composite direction.
        if self.threshold_pos_ <= self.threshold_neg_:
            self.threshold_pos_ = float(np.quantile(composite_arr, 0.67))
            self.threshold_neg_ = float(np.quantile(composite_arr, 0.33))

        return self

    def predict(self, X):
        X_df = pd.DataFrame(X) if not isinstance(X, pd.DataFrame) else X
        X_z = (X_df - self.feature_means_) / self.feature_stds_
        composite = X_z.mean(axis=1).values

        preds = np.zeros(len(composite), dtype=int)
        preds[composite >= self.threshold_pos_] = 1
        preds[composite <= self.threshold_neg_] = -1
        return preds

    @property
    def feature_importance_(self) -> pd.Series:
        """All features equal-weighted in z-space → uniform importance."""
        if self.feature_stds_ is None:
            raise RuntimeError("EqualWeightedClassifier not fit")
        n = len(self.feature_stds_)
        return pd.Series(
            np.ones(n) / n,
            index=self.feature_means_.index,
        )


# ============================================================
# Classifier factories — Pipelines add StandardScaler for scale-sensitive
# models (LogReg L2, Ridge, SVC-RBF). RandomForest is scale-invariant.
# ============================================================


def _logistic_factory():
    return Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "clf",
                LogisticRegression(
                    penalty="l2",
                    C=1.0,
                    class_weight="balanced",
                    max_iter=2000,
                    random_state=RANDOM_SEED,
                ),
            ),
        ]
    )


def _ridge_factory():
    return Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "clf",
                RidgeClassifier(
                    alpha=1.0,
                    class_weight="balanced",
                    random_state=RANDOM_SEED,
                ),
            ),
        ]
    )


def _svc_factory():
    return Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "clf",
                SVC(
                    kernel="rbf",
                    C=1.0,
                    gamma="scale",
                    class_weight="balanced",
                    random_state=RANDOM_SEED,
                ),
            ),
        ]
    )


def _rf_factory():
    return RandomForestClassifier(
        n_estimators=100,
        max_depth=3,
        min_samples_leaf=3,
        class_weight="balanced",
        random_state=RANDOM_SEED,
    )


CLASSIFIERS: dict[str, Callable] = {
    "equal_weighted": EqualWeightedClassifier,
    "logistic_l2": _logistic_factory,
    "ridge": _ridge_factory,
    "svc_rbf": _svc_factory,
    "random_forest": _rf_factory,
}


# ============================================================
# Data prep
# ============================================================


def prepare_classification_data(
    master_table: pd.DataFrame,
    targets_table: pd.DataFrame,
    target_name: str,
) -> tuple[pd.DataFrame, pd.Series]:
    """Align features + target on meeting_date, drop NaN rows, coerce y to int.

    target_name must be one of {"target_surprise_class", "target_regime_class"}.
    """
    X = master_table[FEATURES_FOR_CLASSIFICATION].copy()
    y = targets_table[target_name].copy()
    joined = X.join(y, how="inner").dropna(subset=FEATURES_FOR_CLASSIFICATION + [target_name])
    X_clean = joined[FEATURES_FOR_CLASSIFICATION].astype(float)
    y_clean = joined[target_name].astype(int)
    y_clean.name = target_name
    return X_clean, y_clean


def split_train_validation(
    X: pd.DataFrame,
    y: pd.Series,
    train_end: pd.Timestamp = TRAIN_END_DATE,
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]:
    """Chronological split — NO shuffle."""
    train_mask = X.index <= train_end
    return (
        X.loc[train_mask],
        y.loc[train_mask],
        X.loc[~train_mask],
        y.loc[~train_mask],
    )


# ============================================================
# Metrics
# ============================================================


def compute_classification_metrics(y_true, y_pred) -> dict:
    """Metrics tailored for {-1, 0, +1} with neutral class.

    hit_rate_nonzero is the KEY trading metric: P(sign(pred) == sign(truth) |
    pred != 0). When model commits to a direction, is it right?
    """
    truths = pd.Series(np.asarray(y_true).astype(int)).reset_index(drop=True)
    preds = pd.Series(np.asarray(y_pred).astype(int)).reset_index(drop=True)

    n = len(preds)
    accuracy = float((preds == truths).mean()) if n > 0 else float("nan")

    nonzero_mask = preds != 0
    n_nonzero_pred = int(nonzero_mask.sum())
    if n_nonzero_pred > 0:
        hit_rate = float(
            (np.sign(preds[nonzero_mask]) == np.sign(truths[nonzero_mask])).mean()
        )
    else:
        hit_rate = None

    precision_up = (
        float(precision_score(truths, preds, labels=[1], average="micro", zero_division=0))
        if (preds == 1).any()
        else None
    )
    precision_down = (
        float(precision_score(truths, preds, labels=[-1], average="micro", zero_division=0))
        if (preds == -1).any()
        else None
    )
    recall_up = (
        float(recall_score(truths, preds, labels=[1], average="micro", zero_division=0))
        if (truths == 1).any()
        else None
    )
    recall_down = (
        float(recall_score(truths, preds, labels=[-1], average="micro", zero_division=0))
        if (truths == -1).any()
        else None
    )

    cm = confusion_matrix(truths, preds, labels=[-1, 0, 1])

    return {
        "accuracy": accuracy,
        "hit_rate_nonzero": hit_rate,
        "n_nonzero_pred": n_nonzero_pred,
        "n_nonzero_true": int((truths != 0).sum()),
        "precision_up": precision_up,
        "precision_down": precision_down,
        "recall_up": recall_up,
        "recall_down": recall_down,
        "confusion": cm.tolist(),
        "signal_frequency": float(n_nonzero_pred / n) if n > 0 else 0.0,
    }


# ============================================================
# Walk-forward CV
# ============================================================


def walk_forward_cv_classification(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    classifier_factory: Callable,
    n_splits: int = 5,
    min_train_size: int = 15,
) -> dict:
    """Walk-forward (expanding-window) CV on training set only.

    Uses sklearn.model_selection.TimeSeriesSplit to preserve temporal order.
    Returns per-fold metrics + aggregate means in the 'aggregate' key.
    """
    n = len(X_train)
    if n < min_train_size + n_splits:
        logger.warning("Small train set for CV: n=%d, expected >= %d", n, min_train_size + n_splits)
    test_size = max(3, (n - min_train_size) // n_splits)
    tscv = TimeSeriesSplit(n_splits=n_splits, test_size=test_size)

    folds: dict = {}
    hit_rates: list[float] = []
    accuracies: list[float] = []
    n_nonzeros: list[int] = []

    for k, (train_idx, test_idx) in enumerate(tscv.split(X_train)):
        X_tr = X_train.iloc[train_idx]
        y_tr = y_train.iloc[train_idx]
        X_te = X_train.iloc[test_idx]
        y_te = y_train.iloc[test_idx]

        model = classifier_factory()
        try:
            model.fit(X_tr.values, y_tr.values)
            preds = model.predict(X_te.values)
        except Exception as e:
            logger.warning("CV fold %d failed: %s", k, e)
            folds[f"fold_{k}"] = {"error": str(e)}
            continue

        m = compute_classification_metrics(y_te.values, preds)
        m["n_train"] = int(len(train_idx))
        m["n_test"] = int(len(test_idx))
        folds[f"fold_{k}"] = m
        if m["hit_rate_nonzero"] is not None:
            hit_rates.append(m["hit_rate_nonzero"])
        accuracies.append(m["accuracy"])
        n_nonzeros.append(m["n_nonzero_pred"])

    folds["aggregate"] = {
        "mean_hit_rate_nonzero": float(np.mean(hit_rates)) if hit_rates else float("nan"),
        "std_hit_rate_nonzero": float(np.std(hit_rates)) if hit_rates else float("nan"),
        "mean_accuracy": float(np.mean(accuracies)) if accuracies else float("nan"),
        "mean_n_nonzero_pred": float(np.mean(n_nonzeros)) if n_nonzeros else 0.0,
        "n_folds_with_signals": len(hit_rates),
    }
    return folds


# ============================================================
# Validation evaluation + feature importance
# ============================================================


def _unwrap_estimator(clf):
    """If clf is a sklearn Pipeline, return its final estimator; else clf."""
    if isinstance(clf, Pipeline):
        return clf.named_steps.get("clf", clf.steps[-1][1])
    return clf


def extract_feature_importance(clf, feature_names: list[str]) -> Optional[pd.Series]:
    """Unified importance extractor normalized to sum=1.

    - LogisticRegression / RidgeClassifier: mean abs coef across class rows.
    - RandomForest: feature_importances_.
    - EqualWeightedClassifier: uniform.
    - SVC (rbf): no native importance → returns None (permutation importance
      is out of scope for this small-sample experiment).
    """
    inner = _unwrap_estimator(clf)

    if isinstance(inner, EqualWeightedClassifier):
        # EqualWeightedClassifier is uniform-by-construction; build the Series
        # directly from feature_names so numpy-fit (where column names are
        # lost) still produces a correct importance vector.
        n = len(feature_names)
        return pd.Series(np.ones(n) / n, index=feature_names)

    if hasattr(inner, "feature_importances_"):
        imp = np.asarray(inner.feature_importances_, dtype=float)
        total = imp.sum()
        if total > 0:
            imp = imp / total
        return pd.Series(imp, index=feature_names)

    if hasattr(inner, "coef_"):
        coef = np.asarray(inner.coef_, dtype=float)
        # For multi-class, coef_ is shape (n_classes, n_features); average
        # absolute contribution across classes.
        if coef.ndim == 2:
            magnitude = np.abs(coef).mean(axis=0)
        else:
            magnitude = np.abs(coef)
        total = magnitude.sum()
        if total > 0:
            magnitude = magnitude / total
        return pd.Series(magnitude, index=feature_names)

    return None


def evaluate_on_validation(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    classifier_factory: Callable,
) -> dict:
    """Fit on full train, predict on held-out val — single evaluation pass."""
    model = classifier_factory()
    model.fit(X_train.values, y_train.values)
    preds = model.predict(X_val.values)
    metrics = compute_classification_metrics(y_val.values, preds)
    metrics["predictions"] = preds
    metrics["feature_importance"] = extract_feature_importance(
        model, list(X_train.columns)
    )
    return metrics


def _top_features(importance: Optional[pd.Series], k: int = 5) -> list[str]:
    if importance is None:
        return []
    ordered = importance.sort_values(ascending=False)
    ordered = ordered[ordered > 0]
    return ordered.head(k).index.tolist()


# ============================================================
# Full experiment orchestrator
# ============================================================


TARGET_NAMES: list[str] = ["target_surprise_class", "target_regime_class"]


def run_full_experiment_v2(
    master_table_path: Path = Path("data/divergence/calibration_features.parquet"),
    targets_v2_path: Path = Path("data/divergence/targets_v2.parquet"),
    output_results_path: Path = Path("data/divergence/experiment_v2_results.parquet"),
    output_report_path: Path = Path("data/divergence/experiment_v2_report.md"),
) -> pd.DataFrame:
    """Run 2 targets × 5 classifiers = 10 combinations; persist + report.

    Gate logic per combination:
      - meets_hit_rate_threshold: val hit_rate_nonzero > HIT_RATE_THRESHOLD
      - meets_coverage_gate:      val n_nonzero_pred >= MIN_NONZERO_SIGNALS_VAL
      - stability_gate_passed:    CV mean hit_rate_nonzero > 0.5 AND
                                  val hit_rate_nonzero > 0.5
    """
    master = pd.read_parquet(master_table_path)
    targets = pd.read_parquet(targets_v2_path)

    rows = []
    per_combo_detail: dict = {}
    for target_name in TARGET_NAMES:
        X, y = prepare_classification_data(master, targets, target_name)
        X_train, y_train, X_val, y_val = split_train_validation(X, y)

        for clf_name, factory in CLASSIFIERS.items():
            try:
                cv = walk_forward_cv_classification(X_train, y_train, factory)
                val = evaluate_on_validation(X_train, y_train, X_val, y_val, factory)
            except Exception as e:
                logger.error("Failed %s × %s: %s", target_name, clf_name, e)
                continue

            cv_mean = cv["aggregate"]["mean_hit_rate_nonzero"]
            cv_std = cv["aggregate"]["std_hit_rate_nonzero"]
            val_hit = val["hit_rate_nonzero"]
            n_nonzero_pred = val["n_nonzero_pred"]

            meets_hit = (val_hit is not None) and (val_hit > HIT_RATE_THRESHOLD)
            meets_cov = n_nonzero_pred >= MIN_NONZERO_SIGNALS_VAL
            stability = (
                (not np.isnan(cv_mean))
                and cv_mean > 0.5
                and (val_hit is not None)
                and val_hit > 0.5
            )

            top_feats = _top_features(val["feature_importance"])

            rows.append(
                {
                    "target": target_name,
                    "classifier": clf_name,
                    "n_train": int(len(X_train)),
                    "n_val": int(len(X_val)),
                    "cv_mean_hit_rate": float(cv_mean),
                    "cv_std_hit_rate": float(cv_std),
                    "cv_mean_accuracy": float(cv["aggregate"]["mean_accuracy"]),
                    "val_hit_rate": float(val_hit) if val_hit is not None else float("nan"),
                    "val_n_nonzero_pred": int(n_nonzero_pred),
                    "val_n_nonzero_true": int(val["n_nonzero_true"]),
                    "val_accuracy": float(val["accuracy"]),
                    "val_precision_up": (
                        float(val["precision_up"]) if val["precision_up"] is not None else float("nan")
                    ),
                    "val_precision_down": (
                        float(val["precision_down"]) if val["precision_down"] is not None else float("nan")
                    ),
                    "val_recall_up": (
                        float(val["recall_up"]) if val["recall_up"] is not None else float("nan")
                    ),
                    "val_recall_down": (
                        float(val["recall_down"]) if val["recall_down"] is not None else float("nan")
                    ),
                    "val_signal_frequency": float(val["signal_frequency"]),
                    "meets_hit_rate_threshold": bool(meets_hit),
                    "meets_coverage_gate": bool(meets_cov),
                    "stability_gate_passed": bool(stability),
                    "top_features": ", ".join(top_feats) if top_feats else "",
                    "confusion_matrix": str(val["confusion"]),
                }
            )
            per_combo_detail[(target_name, clf_name)] = {"cv": cv, "val": val}

    results = pd.DataFrame(rows)

    output_results_path = Path(output_results_path)
    output_results_path.parent.mkdir(parents=True, exist_ok=True)
    results.to_parquet(output_results_path, index=False)
    logger.info("Experiment v2 results persisted: %s (%d rows)", output_results_path, len(results))

    _write_report_v2(
        results=results,
        targets=targets,
        per_combo_detail=per_combo_detail,
        output_path=Path(output_report_path),
    )
    return results


# ============================================================
# Report
# ============================================================


def _scenario_and_recommendation(results: pd.DataFrame) -> tuple[str, str]:
    """Return (scenario letter, recommendation text) based on gate results."""
    winners = results[
        results["meets_hit_rate_threshold"]
        & results["meets_coverage_gate"]
        & results["stability_gate_passed"]
    ]
    has_surprise = (winners["target"] == "target_surprise_class").any()
    has_regime = (winners["target"] == "target_regime_class").any()

    if has_surprise and has_regime:
        return (
            "A",
            "Dual-signal production calibration (CC-2b on both targets).",
        )
    if has_regime and not has_surprise:
        return (
            "B",
            "Regime-only classifier (CC-2b on target_regime_class).",
        )
    if has_surprise and not has_regime:
        return (
            "C",
            "Surprise-only classifier (CC-2b on target_surprise_class).",
        )
    return (
        "D",
        "Signal insufficient at N=30. Options: (1) wait for more meetings, "
        "(2) revise features, (3) relax thresholds (with new pre-commit).",
    )


def _write_report_v2(
    results: pd.DataFrame,
    targets: pd.DataFrame,
    per_combo_detail: dict,
    output_path: Path,
) -> None:
    lines: list[str] = []
    lines.append("# CC-2a-v2 — Dual-Target Classification Experiment — Results Report")
    lines.append("")
    lines.append(f"Generated: {pd.Timestamp.now().isoformat()}")
    lines.append("")

    # --- 1. Setup
    lines.append("## 1. Experiment Setup (v2 context)")
    lines.append("")
    lines.append("**Architecture:** 2 independent classification targets × 5 classifiers = 10 combinations.")
    lines.append("")
    lines.append("**Why classification, not regression:** v1 measured Spearman IC (ordering of magnitudes). The user's real workflow is:")
    lines.append("  1. Detect the structural regime (EUR/USD direction over ~2 months).")
    lines.append("  2. Use FedWatch surprise as event-level confirmation/timing.")
    lines.append("")
    lines.append("Hit rate on non-zero directional predictions is the metric that maps directly to trading decisions.")
    lines.append("")
    lines.append("**Pre-committed thresholds:**")
    lines.append(f"- Hit rate threshold: {HIT_RATE_THRESHOLD}")
    lines.append(f"- Coverage gate: val n_nonzero_pred ≥ {MIN_NONZERO_SIGNALS_VAL}")
    lines.append("- Stability gate: CV mean hit_rate > 0.5 AND val hit_rate > 0.5")
    lines.append(f"- Train/val split: chronological at {TRAIN_END_DATE.date()}")
    lines.append(f"- CV protocol: walk-forward (expanding window), 5 splits on train only")
    lines.append(f"- Features ({len(FEATURES_FOR_CLASSIFICATION)}): "
                 + ", ".join(f"`{f}`" for f in FEATURES_FOR_CLASSIFICATION))
    lines.append(f"- Random seed: {RANDOM_SEED}")
    lines.append("")

    # --- 2. Target distributions
    lines.append("## 2. Target Distributions")
    lines.append("")
    for tgt in TARGET_NAMES:
        s = targets[tgt]
        lines.append(f"### `{tgt}`")
        lines.append("")
        counts_full = s.value_counts(dropna=False).sort_index(key=lambda x: x.astype(str))
        lines.append("| Class | Count (all meetings) |")
        lines.append("|---|---|")
        for cls_val, cnt in counts_full.items():
            label = "NaN" if pd.isna(cls_val) else str(int(cls_val))
            lines.append(f"| {label} | {int(cnt)} |")
        lines.append("")
        # Train vs val distribution
        train_mask = s.index <= TRAIN_END_DATE
        train_dist = s[train_mask].value_counts(dropna=False).sort_index(key=lambda x: x.astype(str))
        val_dist = s[~train_mask].value_counts(dropna=False).sort_index(key=lambda x: x.astype(str))
        lines.append("| Class | Train count | Val count |")
        lines.append("|---|---|---|")
        all_keys = sorted(set(list(train_dist.index) + list(val_dist.index)), key=lambda x: str(x))
        for k in all_keys:
            label = "NaN" if pd.isna(k) else str(int(k))
            tc = int(train_dist.get(k, 0))
            vc = int(val_dist.get(k, 0))
            lines.append(f"| {label} | {tc} | {vc} |")
        lines.append("")
        # Flag imbalance
        train_valid = s[train_mask].dropna()
        for cls_val in [-1, 0, 1]:
            cnt = int((train_valid == cls_val).sum())
            if cnt < 5:
                lines.append(f"> **WARN:** training has only {cnt} example(s) of class {cls_val} — classifier may struggle.")
        lines.append("")

    # --- 3. Results table
    lines.append("## 3. Results — All 10 Combinations")
    lines.append("")
    lines.append(
        "| Target | Classifier | CV hit± std | Val hit | Val n_nonzero_pred "
        "| Val acc | Hit≥0.60 | Cov≥8 | Stability |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for _, r in results.iterrows():
        cv_ic = (
            f"{r['cv_mean_hit_rate']:.3f} ± {r['cv_std_hit_rate']:.3f}"
            if not np.isnan(r["cv_mean_hit_rate"])
            else "NaN"
        )
        val_hit_str = (
            f"{r['val_hit_rate']:.3f}" if not np.isnan(r["val_hit_rate"]) else "NaN"
        )
        tgt_short = r["target"].replace("target_", "").replace("_class", "")
        lines.append(
            f"| {tgt_short} | {r['classifier']} | {cv_ic} | {val_hit_str} | "
            f"{int(r['val_n_nonzero_pred'])} | {r['val_accuracy']:.3f} | "
            f"{'✓' if r['meets_hit_rate_threshold'] else '✗'} | "
            f"{'✓' if r['meets_coverage_gate'] else '✗'} | "
            f"{'✓' if r['stability_gate_passed'] else '✗'} |"
        )
    lines.append("")

    # --- 4. Winners (passing all 3 gates), split by target
    winners = results[
        results["meets_hit_rate_threshold"]
        & results["meets_coverage_gate"]
        & results["stability_gate_passed"]
    ]
    lines.append("## 4. Winners — Combinations Passing All 3 Gates")
    lines.append("")
    for tgt in TARGET_NAMES:
        tgt_short = tgt.replace("target_", "").replace("_class", "")
        w_tgt = winners[winners["target"] == tgt]
        lines.append(f"### {tgt_short.capitalize()}")
        lines.append("")
        if len(w_tgt) == 0:
            lines.append(f"**No winners for `{tgt}`.**")
        else:
            lines.append(f"**{len(w_tgt)} winner(s):**")
            lines.append("")
            lines.append("| Classifier | Val hit rate | Val n_nonzero_pred | CV mean hit rate |")
            lines.append("|---|---|---|---|")
            for _, r in w_tgt.sort_values("val_hit_rate", ascending=False).iterrows():
                lines.append(
                    f"| {r['classifier']} | {r['val_hit_rate']:.3f} | "
                    f"{int(r['val_n_nonzero_pred'])} | {r['cv_mean_hit_rate']:.3f} |"
                )
        lines.append("")

    # --- 5. Top features per winner
    lines.append("## 5. Top Features per Winner")
    lines.append("")
    if len(winners) == 0:
        lines.append("*No winners — showing top features for the highest-hit-rate combo per target for reference.*")
        lines.append("")
        for tgt in TARGET_NAMES:
            sub = results[results["target"] == tgt].sort_values(
                "val_hit_rate", ascending=False, na_position="last"
            )
            if len(sub) > 0:
                r = sub.iloc[0]
                tgt_short = tgt.replace("target_", "").replace("_class", "")
                lines.append(f"- **{tgt_short} × {r['classifier']}** (val hit={r['val_hit_rate']:.3f}, "
                             f"n_nonzero={int(r['val_n_nonzero_pred'])}): {r['top_features'] or '(no importance available)'}")
    else:
        for _, r in winners.sort_values("val_hit_rate", ascending=False).iterrows():
            tgt_short = r["target"].replace("target_", "").replace("_class", "")
            lines.append(f"- **{tgt_short} × {r['classifier']}**: {r['top_features'] or '(no importance available)'}")
    lines.append("")

    # --- 6. Confusion matrices
    lines.append("## 6. Confusion Matrices (rows = true class, cols = predicted)")
    lines.append("")
    lines.append("Labels in order: [-1, 0, +1].")
    lines.append("")
    if len(winners) > 0:
        lines.append("*Winners only.*")
        to_show = winners
    else:
        lines.append("*No winners — showing the 2 highest val-hit-rate combinations for diagnostic reference.*")
        to_show = results.sort_values("val_hit_rate", ascending=False, na_position="last").head(2)
    lines.append("")
    for _, r in to_show.iterrows():
        tgt_short = r["target"].replace("target_", "").replace("_class", "")
        lines.append(f"### {tgt_short} × {r['classifier']}")
        lines.append("")
        lines.append("```")
        lines.append(r["confusion_matrix"])
        lines.append("```")
        lines.append("")

    # --- 7. Trading workflow implications
    lines.append("## 7. Trading Workflow Implications")
    lines.append("")
    lines.append(
        "The two targets are complementary, not substitutes:"
    )
    lines.append("")
    lines.append(
        "- **Regime signal (42 bd horizon):** slow-moving, persists for weeks. "
        "Acts as a **position-direction filter**. A +1 regime = bias long EUR/USD; "
        "-1 regime = bias short; 0 regime = no structural bias → stand aside."
    )
    lines.append(
        "- **Surprise signal (event-level):** fast, fires on FOMC day. Acts as "
        "**entry timing / confirmation**. A +1 surprise inside a +1 regime = dual "
        "confirmation → higher-conviction entry. Contradictory signals (e.g. +1 regime, "
        "-1 surprise) → reduced size or wait for the next event."
    )
    lines.append("")
    lines.append(
        "Combination logic is NOT calibrated in this experiment — that is scope for "
        "CC-2b (production calibration) or CC-7 (composite scoring). This report only "
        "selects the individual classifier(s) worth carrying forward."
    )
    lines.append("")

    # --- 8. Recommendation
    scenario, recommendation = _scenario_and_recommendation(results)
    lines.append("## 8. Recommendation for CC-2b")
    lines.append("")
    lines.append(f"**Scenario {scenario}** — {recommendation}")
    lines.append("")
    lines.append("Scenario legend:")
    lines.append("- **A**: both targets have ≥1 winner → dual-signal production.")
    lines.append("- **B**: only regime has a winner → regime-only production.")
    lines.append("- **C**: only surprise has a winner → surprise-only production.")
    lines.append(
        "- **D**: no winners → treat N=30 train as underpowered; pick one of: "
        "(1) wait for more meetings, (2) revise the feature set, (3) relax thresholds via a *new* pre-commit (do not p-hack the existing one)."
    )
    lines.append("")
    if len(winners) > 0:
        lines.append("Selected combinations (top by val hit rate within each target):")
        lines.append("")
        for tgt in TARGET_NAMES:
            w_tgt = winners[winners["target"] == tgt].sort_values("val_hit_rate", ascending=False)
            if len(w_tgt) > 0:
                top = w_tgt.iloc[0]
                tgt_short = tgt.replace("target_", "").replace("_class", "")
                lines.append(f"- **{tgt_short}** → `{top['classifier']}` "
                             f"(val hit={top['val_hit_rate']:.3f}, n_nonzero={int(top['val_n_nonzero_pred'])}, "
                             f"CV={top['cv_mean_hit_rate']:.3f}±{top['cv_std_hit_rate']:.3f})")
        lines.append("")

    # --- 9. Caveats
    lines.append("## 9. Caveats")
    lines.append("")
    lines.append("- **Sample size is small by ML standards:** ~28 train meetings, ~14 validation. Single outliers can flip gate results.")
    lines.append("- **Regime shift:** train spans the 2022–2023 hiking cycle + plateau; validation spans the 2024+ cutting cycle. Coefficients fit to hiking-era Fed behavior may not transfer.")
    lines.append("- **Coverage gate (≥8 non-zero val predictions):** a classifier that is too conservative — predicting class 0 too often — fails the gate even with high accuracy on the few directional calls it does make. Low coverage = low trading utility, which is the correct rejection.")
    lines.append("- **Multiple testing:** 10 combinations evaluated → family-wise error rate inflated. Pre-committed gates mitigate but do not eliminate this.")
    lines.append("- **One validation pass only.** Do NOT re-tune or swap classifiers based on this report; that is p-hacking against the pre-commit.")
    lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Experiment v2 report written: %s", output_path)
