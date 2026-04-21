"""Calibration experiment — PRD-300 / CC-2a.

Tests 4 candidate targets × 5 regression methods on master alignment table.
Chronological split: 28 train / 14 held-out validation (meetings cut at 2024-06-30).
Pre-committed decision metric: Spearman IC > 0.10 on validation.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import (
    ElasticNetCV,
    LassoCV,
    LinearRegression,
    RidgeCV,
)
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import TimeSeriesSplit

logger = logging.getLogger(__name__)


FEATURES_FOR_CALIBRATION: list[str] = [
    # NLP — current meeting (forward-looking at T)
    "statement_ensemble_net",
    "statement_fomc_roberta_net",
    "statement_llama_deepinfra_net",
    # NLP — lag from previous meeting (backward-looking, published before T)
    "minutes_lag_ensemble_net",
    "minutes_lag_fomc_roberta_net",
    "minutes_lag_llama_deepinfra_net",
    # Market pricing (forward-looking market expectation)
    "fedwatch_implied_change_bps",
    "real_rate_diff_5y",
    # Economic sentiment (backward-looking, forward-filled)
    "cleveland_national_score",
    "cleveland_consensus_score",
    "cleveland_divergence",
]
# fedwatch_actual_change_bps & fedwatch_surprise_bps deliberately excluded
# (circularity for target A; consistency across all targets).


TRAIN_END_DATE: pd.Timestamp = pd.Timestamp("2024-06-30")
# Empirical split at this cutoff: 28 train (2021-01-27 → 2024-06-12)
# and 14 validation (2024-07-31 → 2026-03-18) meetings.

PRE_COMMITTED_METRIC: str = "spearman_ic"
PRE_COMMITTED_THRESHOLD: float = 0.10


RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)


class EqualWeightedRegressor:
    """Baseline: z-score features, equal-weight average, then fit 1-D OLS for y scale."""

    def __init__(self):
        self.feature_means_: Optional[pd.Series] = None
        self.feature_stds_: Optional[pd.Series] = None
        self.scaler_: Optional[LinearRegression] = None

    def fit(self, X, y):
        X_df = pd.DataFrame(X) if not isinstance(X, pd.DataFrame) else X
        self.feature_means_ = X_df.mean()
        self.feature_stds_ = X_df.std().replace(0.0, 1.0)
        X_z = (X_df - self.feature_means_) / self.feature_stds_
        composite = X_z.mean(axis=1).values.reshape(-1, 1)
        y_arr = np.asarray(y)
        self.scaler_ = LinearRegression().fit(composite, y_arr)
        return self

    def predict(self, X):
        X_df = pd.DataFrame(X) if not isinstance(X, pd.DataFrame) else X
        X_z = (X_df - self.feature_means_) / self.feature_stds_
        composite = X_z.mean(axis=1).values.reshape(-1, 1)
        return self.scaler_.predict(composite)

    @property
    def coef_(self) -> np.ndarray:
        if self.scaler_ is None or self.feature_stds_ is None:
            raise RuntimeError("EqualWeightedRegressor not fit")
        n = len(self.feature_stds_)
        return (1.0 / n) * float(self.scaler_.coef_[0]) / self.feature_stds_.values


def _ridge_factory():
    return RidgeCV(alphas=np.logspace(-3, 3, 20))


def _lasso_factory():
    return LassoCV(alphas=np.logspace(-3, 3, 20), max_iter=5000, random_state=RANDOM_SEED)


def _elasticnet_factory():
    return ElasticNetCV(
        alphas=np.logspace(-3, 3, 20),
        l1_ratio=[0.1, 0.3, 0.5, 0.7, 0.9],
        max_iter=5000,
        random_state=RANDOM_SEED,
    )


METHODS: dict[str, Callable] = {
    "equal_weighted": EqualWeightedRegressor,
    "ols": LinearRegression,
    "ridge": _ridge_factory,
    "lasso": _lasso_factory,
    "elasticnet": _elasticnet_factory,
}


def prepare_features_targets(
    master_table: pd.DataFrame,
    targets_table: pd.DataFrame,
    target_name: str,
) -> tuple[pd.DataFrame, pd.Series]:
    """Align features + target on meeting_date; drop rows with NaN in target or any feature."""
    X = master_table[FEATURES_FOR_CALIBRATION].copy()
    y = targets_table[target_name].copy()
    joined = X.join(y, how="inner").dropna()
    X_clean = joined[FEATURES_FOR_CALIBRATION]
    y_clean = joined[target_name]
    return X_clean, y_clean


def split_train_validation(
    X: pd.DataFrame,
    y: pd.Series,
    train_end: pd.Timestamp = TRAIN_END_DATE,
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]:
    """Chronological split — NO shuffle."""
    train_mask = X.index <= train_end
    X_train, y_train = X.loc[train_mask], y.loc[train_mask]
    X_val, y_val = X.loc[~train_mask], y.loc[~train_mask]
    return X_train, y_train, X_val, y_val


def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    out: dict = {}
    if len(y_true) >= 3 and np.std(y_true) > 0 and np.std(y_pred) > 0:
        ic_res = spearmanr(y_true, y_pred)
        out["spearman_ic"] = float(ic_res.correlation) if not np.isnan(ic_res.correlation) else float("nan")
        pcorr = np.corrcoef(y_true, y_pred)[0, 1]
        out["pearson_corr"] = float(pcorr) if not np.isnan(pcorr) else float("nan")
    else:
        out["spearman_ic"] = float("nan")
        out["pearson_corr"] = float("nan")
    out["rmse"] = float(np.sqrt(mean_squared_error(y_true, y_pred))) if len(y_true) > 0 else float("nan")
    out["mae"] = float(mean_absolute_error(y_true, y_pred)) if len(y_true) > 0 else float("nan")
    out["r2"] = float(r2_score(y_true, y_pred)) if len(y_true) >= 2 else float("nan")
    return out


def walk_forward_cv_evaluation(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    method_factory: Callable,
    n_splits: int = 5,
    min_train_size: int = 15,
) -> dict:
    """Walk-forward time-series CV on train set (expanding window)."""
    n = len(X_train)
    if n < min_train_size + n_splits:
        logger.warning("Small train set: n=%d, expected >= %d", n, min_train_size + n_splits)
    # Spearman requires >= 3 points; test_size=3 min. With n=28, 5 folds × 3 = 15 test
    # samples, min train = 13 — acceptable compromise on small N.
    test_size = max(3, (n - min_train_size) // n_splits)
    tscv = TimeSeriesSplit(n_splits=n_splits, test_size=test_size)

    folds: dict = {}
    ics: list[float] = []
    rmses: list[float] = []
    r2s: list[float] = []
    for k, (train_idx, test_idx) in enumerate(tscv.split(X_train)):
        X_tr = X_train.iloc[train_idx]
        y_tr = y_train.iloc[train_idx]
        X_te = X_train.iloc[test_idx]
        y_te = y_train.iloc[test_idx]
        model = method_factory()
        model.fit(X_tr.values, y_tr.values)
        preds = model.predict(X_te.values)
        m = _metrics(y_te.values, preds)
        m["n_train"] = len(train_idx)
        m["n_test"] = len(test_idx)
        folds[f"fold_{k}"] = m
        if not np.isnan(m["spearman_ic"]):
            ics.append(m["spearman_ic"])
        if not np.isnan(m["rmse"]):
            rmses.append(m["rmse"])
        if not np.isnan(m["r2"]):
            r2s.append(m["r2"])
    folds["aggregate"] = {
        "mean_spearman_ic": float(np.mean(ics)) if ics else float("nan"),
        "std_spearman_ic": float(np.std(ics)) if ics else float("nan"),
        "mean_rmse": float(np.mean(rmses)) if rmses else float("nan"),
        "mean_r2": float(np.mean(r2s)) if r2s else float("nan"),
        "n_folds_valid": len(ics),
    }
    return folds


def evaluate_on_validation(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    method_factory: Callable,
) -> dict:
    """Fit on full train, predict on held-out validation — single evaluation pass."""
    model = method_factory()
    model.fit(X_train.values, y_train.values)
    preds = model.predict(X_val.values)
    m = _metrics(y_val.values, preds)
    coefs = getattr(model, "coef_", None)
    coef_arr = np.asarray(coefs, dtype=float).ravel() if coefs is not None else np.full(len(FEATURES_FOR_CALIBRATION), np.nan)
    m["predictions"] = preds
    m["coefficients"] = coef_arr
    return m


def _top_features(coef: np.ndarray, names: list[str], k: int = 5) -> list[str]:
    if coef is None or np.all(np.isnan(coef)):
        return []
    abs_coef = np.abs(np.nan_to_num(coef, nan=0.0))
    order = np.argsort(-abs_coef)
    return [names[i] for i in order[:k] if abs_coef[i] > 0]


def run_full_experiment(
    master_table_path: Path = Path("data/divergence/calibration_features.parquet"),
    targets_table_path: Path = Path("data/divergence/targets.parquet"),
    output_results_path: Path = Path("data/divergence/experiment_results.parquet"),
    output_report_path: Path = Path("data/divergence/experiment_report.md"),
) -> pd.DataFrame:
    """Run 4 targets × 5 methods, persist results + markdown report."""
    master = pd.read_parquet(master_table_path)
    targets = pd.read_parquet(targets_table_path)

    target_names = [
        "target_A_fedwatch_surprise",
        "target_D_rrd_change_5d",
        "target_E_eurusd_5d",
        "target_F_eurusd_21d",
    ]

    rows = []
    per_combo_detail = {}
    for target_name in target_names:
        X, y = prepare_features_targets(master, targets, target_name)
        X_train, y_train, X_val, y_val = split_train_validation(X, y)
        for method_name, factory in METHODS.items():
            try:
                cv = walk_forward_cv_evaluation(X_train, y_train, factory)
                val = evaluate_on_validation(X_train, y_train, X_val, y_val, factory)
            except Exception as e:
                logger.error("Failed %s × %s: %s", target_name, method_name, e)
                continue
            top = _top_features(val["coefficients"], FEATURES_FOR_CALIBRATION)
            cv_mean_ic = cv["aggregate"]["mean_spearman_ic"]
            cv_std_ic = cv["aggregate"]["std_spearman_ic"]
            val_ic = val["spearman_ic"]
            meets = (not np.isnan(val_ic)) and (val_ic > PRE_COMMITTED_THRESHOLD)
            rows.append(
                {
                    "target": target_name,
                    "method": method_name,
                    "n_train": len(X_train),
                    "n_val": len(X_val),
                    "cv_mean_ic": cv_mean_ic,
                    "cv_std_ic": cv_std_ic,
                    "cv_mean_r2": cv["aggregate"]["mean_r2"],
                    "val_ic": val_ic,
                    "val_pearson": val["pearson_corr"],
                    "val_rmse": val["rmse"],
                    "val_mae": val["mae"],
                    "val_r2": val["r2"],
                    "meets_threshold": bool(meets),
                    "top_features": ", ".join(top) if top else "",
                }
            )
            per_combo_detail[(target_name, method_name)] = {"cv": cv, "val": val}

    results = pd.DataFrame(rows)
    output_results_path = Path(output_results_path)
    output_results_path.parent.mkdir(parents=True, exist_ok=True)
    results.to_parquet(output_results_path, index=False)

    _write_experiment_report(
        results=results,
        targets=targets,
        master=master,
        per_combo_detail=per_combo_detail,
        output_path=Path(output_report_path),
    )
    return results


def _write_experiment_report(
    results: pd.DataFrame,
    targets: pd.DataFrame,
    master: pd.DataFrame,
    per_combo_detail: dict,
    output_path: Path,
) -> None:
    lines: list[str] = []
    lines.append("# CC-2a — Target Selection Experiment — Results Report")
    lines.append("")
    lines.append(f"Generated: {pd.Timestamp.now().isoformat()}")
    lines.append("")

    lines.append("## 1. Experiment Setup")
    lines.append("")
    lines.append("- **Targets tested:** 4 (FedWatch surprise, real-rate-diff 5bd change, EUR/USD 5bd return, EUR/USD 21bd return)")
    lines.append("- **Methods tested:** 5 (equal_weighted baseline, OLS, Ridge, Lasso, ElasticNet — last three with internal alpha CV)")
    lines.append(f"- **Features:** {len(FEATURES_FOR_CALIBRATION)} (3 statement NLP + 3 minutes-lag NLP + 2 market pricing + 3 Cleveland Fed)")
    lines.append(f"- **Train/validation split:** chronological at {TRAIN_END_DATE.date()}")
    lines.append("- **CV protocol:** walk-forward expanding-window, 5 splits on train only")
    lines.append(f"- **Decision metric (pre-committed):** {PRE_COMMITTED_METRIC} > {PRE_COMMITTED_THRESHOLD} on held-out validation")
    lines.append("- **Anti-circularity:** fedwatch_actual_change_bps and fedwatch_surprise_bps excluded from feature set")
    lines.append(f"- **Random seed:** {RANDOM_SEED}")
    lines.append("")

    lines.append("## 2. Target Summary")
    lines.append("")
    lines.append("| Target | Mean | Std | Min | Max | N non-null |")
    lines.append("|---|---|---|---|---|---|")
    for c in targets.columns:
        s = targets[c]
        lines.append(
            f"| `{c}` | {s.mean():.4f} | {s.std():.4f} | {s.min():.4f} | {s.max():.4f} | {int(s.notna().sum())} |"
        )
    lines.append("")

    lines.append("## 3. Results Table (20 combinations)")
    lines.append("")
    lines.append("| Target | Method | CV mean IC ± std | Val IC | Val R² | Val RMSE | Meets IC>0.10 |")
    lines.append("|---|---|---|---|---|---|---|")
    for _, r in results.iterrows():
        cv_ic = f"{r['cv_mean_ic']:.3f} ± {r['cv_std_ic']:.3f}"
        val_ic = f"{r['val_ic']:.3f}"
        val_r2 = f"{r['val_r2']:.3f}"
        val_rmse = f"{r['val_rmse']:.4f}"
        meets = "✓" if r["meets_threshold"] else "✗"
        lines.append(
            f"| {r['target']} | {r['method']} | {cv_ic} | {val_ic} | {val_r2} | {val_rmse} | {meets} |"
        )
    lines.append("")

    winners = results[results["meets_threshold"]]
    lines.append("## 4. Winners — Combinations that Meet IC > 0.10 on Validation")
    lines.append("")
    if len(winners) == 0:
        lines.append("**None.** No target × method combination cleared the pre-committed IC > 0.10 threshold on the 14-meeting held-out validation set.")
    else:
        lines.append(f"**{len(winners)} combination(s) pass.** Ranked by validation IC:")
        lines.append("")
        lines.append("| Rank | Target | Method | Val IC | CV mean IC | Val R² |")
        lines.append("|---|---|---|---|---|---|")
        for rank, (_, r) in enumerate(winners.sort_values("val_ic", ascending=False).iterrows(), 1):
            lines.append(f"| {rank} | {r['target']} | {r['method']} | {r['val_ic']:.3f} | {r['cv_mean_ic']:.3f} | {r['val_r2']:.3f} |")
    lines.append("")

    lines.append("## 5. Feature Importance (Top 5 by |coef|)")
    lines.append("")
    if len(winners) > 0:
        for _, r in winners.sort_values("val_ic", ascending=False).iterrows():
            lines.append(f"- **{r['target']} × {r['method']}**: {r['top_features']}")
    else:
        lines.append("For reference, top features across *all* 20 combinations:")
        lines.append("")
        for _, r in results.sort_values("val_ic", ascending=False).head(5).iterrows():
            lines.append(f"- **{r['target']} × {r['method']}** (val IC={r['val_ic']:.3f}): {r['top_features']}")
    lines.append("")

    lines.append("## 6. Interpretation")
    lines.append("")
    best = results.sort_values("val_ic", ascending=False).iloc[0]
    median_val_ic = results["val_ic"].median()
    lines.append(f"- **Best combination (by val IC):** {best['target']} × {best['method']} with IC = {best['val_ic']:.3f}, R² = {best['val_r2']:.3f}.")
    lines.append(f"- **Median validation IC across 20 combinations:** {median_val_ic:.3f}.")
    lines.append(f"- **Combinations above threshold:** {len(winners)}/20.")
    # CV vs val agreement
    cv_val_corr = results[["cv_mean_ic", "val_ic"]].corr().iloc[0, 1]
    if not np.isnan(cv_val_corr):
        lines.append(f"- **CV ↔ Val agreement (rank-corr across combos):** {cv_val_corr:.3f} — "
                     f"{'strong' if cv_val_corr > 0.5 else 'weak'} signal stability between folds and hold-out.")
    # Any method dominating?
    method_means = results.groupby("method")["val_ic"].mean().sort_values(ascending=False)
    lines.append(f"- **Method ranking by mean val IC:** " + ", ".join(f"{m}={v:.3f}" for m, v in method_means.items()))
    target_means = results.groupby("target")["val_ic"].mean().sort_values(ascending=False)
    lines.append(f"- **Target ranking by mean val IC:** " + ", ".join(f"{t.replace('target_', '')}={v:.3f}" for t, v in target_means.items()))
    lines.append("")

    lines.append("## 7. Recommendation for CC-2b")
    lines.append("")
    # Stable winners: val_ic > threshold AND cv_mean_ic > 0 (same-direction agreement
    # between CV and held-out). This avoids recommending combinations where the
    # validation result looks like a single-sample fluke.
    stable = winners[winners["cv_mean_ic"] > 0].copy()
    if len(stable) >= 1:
        stable = stable.sort_values(["val_ic", "cv_mean_ic"], ascending=False)
        top = stable.iloc[0]
        lines.append(
            f"**Use target `{top['target']}` with method `{top['method']}`** for CC-2b production calibration."
        )
        lines.append("")
        lines.append("Selection rule: pre-committed IC > 0.10 on validation AND CV mean IC > 0 (direction agreement).")
        lines.append("")
        lines.append(f"- Val IC = {top['val_ic']:.3f} (> {PRE_COMMITTED_THRESHOLD} threshold)")
        lines.append(f"- CV mean IC = {top['cv_mean_ic']:.3f} ± {top['cv_std_ic']:.3f} (same sign as val — stable)")
        lines.append(f"- Val R² = {top['val_r2']:.3f}, RMSE = {top['val_rmse']:.4f}")
        lines.append(f"- Top features: {top['top_features']}")
        if len(stable) > 1:
            lines.append("")
            lines.append(f"Secondary stable candidates ({len(stable) - 1}): " + ", ".join(
                f"{r['target']} × {r['method']} (val IC={r['val_ic']:.3f}, CV IC={r['cv_mean_ic']:.3f})"
                for _, r in stable.iloc[1:].iterrows()
            ))
    elif len(winners) >= 1:
        top = winners.sort_values("val_ic", ascending=False).iloc[0]
        lines.append(
            f"**CAUTION — top val-IC winner is CV-unstable.**"
        )
        lines.append("")
        lines.append(
            f"`{top['target']} × {top['method']}` has val IC = {top['val_ic']:.3f} but CV mean IC = "
            f"{top['cv_mean_ic']:.3f} (opposite sign). The model trained on full train would likely "
            "regress on a fresh hold-out."
        )
        lines.append("")
        lines.append("Do NOT proceed to CC-2b on this combo without additional validation (e.g. rolling-origin backtest with refits).")
        winner_list = ", ".join(f"{r['target']} × {r['method']}" for _, r in winners.iterrows())
        lines.append(f"Winners by val IC (none CV-stable): {winner_list}")
    else:
        lines.append("**NO_SIGNAL** — no combination cleared the pre-committed IC > 0.10 threshold.")
        lines.append("")
        lines.append("Do NOT proceed to CC-2b production calibration on any of these 20 combinations without re-scoping:")
        lines.append("- The Fed-language features (NLP) may carry too little incremental information over the market pricing baseline on this N=14 validation window.")
        lines.append("- Consider: (a) richer targets (e.g. conditional on VIX regime), (b) more features (tactical positioning — PRD-401), (c) longer horizon (F=21bd is already the longest tested).")
        lines.append("- Do NOT p-hack by lowering the threshold or swapping methods until something passes — pre-committed gates exist precisely to resist this.")
    lines.append("")

    lines.append("## 8. Caveats")
    lines.append("")
    lines.append("- **Sample size is small** by ML standards: 28 train meetings, 14 validation meetings. Spearman IC variance on N=14 is high — a single outlier can flip sign. Interpret with humility.")
    lines.append("- **Multiple testing risk:** 20 combinations tested → family-wise error rate inflated. One winner at p≈0.05 could easily be noise. Pre-committed threshold mitigates but doesn't eliminate this.")
    lines.append("- **Regime mismatch:** train covers hiking cycle (2022-2023) + plateau; validation covers cutting cycle (2024+). Model coefficients fit to hiking behavior may not transfer cleanly. This is a feature of the test, not a bug — we explicitly want to see if a model trained on 2022-era Fed behavior holds up on 2024-era Fed behavior.")
    lines.append("- **One validation pass only.** Results are what they are. Do NOT re-fit or re-tune based on this report.")
    lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Experiment report written: %s", output_path)
