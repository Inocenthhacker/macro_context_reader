"""CC-2a-v3 dual-classification experiment with engineered features.

Identical protocol to v2 (chronological split, pre-committed thresholds,
stability + coverage gates). Only change: expanded feature list
(11 original + 7 engineered = 18).

Hypothesis under test: theory-driven derivative features (momentum,
acceleration, divergence) rescue the experiment from Scenario D.

Infrastructure is reused directly from v2 — no classifier or metric logic is
redefined here. If v3 reveals differences from v2 it is because of the feature
set only, which is the point of the experiment.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from macro_context_reader.divergence.calibration_experiment_v2 import (
    CLASSIFIERS,
    HIT_RATE_THRESHOLD,
    MIN_NONZERO_SIGNALS_VAL,
    RANDOM_SEED,
    TARGET_NAMES,
    TRAIN_END_DATE,
    EqualWeightedClassifier,  # noqa: F401 (re-exported via __init__)
    _scenario_and_recommendation,
    _top_features,
    compute_classification_metrics,
    evaluate_on_validation,
    extract_feature_importance,  # noqa: F401 (re-exported via __init__)
    split_train_validation,
    walk_forward_cv_classification,
)
from macro_context_reader.divergence.feature_engineering import (
    ENGINEERED_FEATURES,
    build_features_v3_table,
)

logger = logging.getLogger(__name__)


# ============================================================
# Pre-committed feature list: 11 original + 7 engineered = 18
# ============================================================


FEATURES_FOR_CLASSIFICATION_V3: list[str] = [
    # ===== ORIGINAL (from v2) =====
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
    # ===== ENGINEERED (new in v3) =====
    "statement_momentum",
    "minutes_lag_momentum",
    "real_rate_diff_momentum_21bd",
    "statement_acceleration",
    "cleveland_acceleration",
    "nlp_vs_fedwatch_divergence",
    "statement_vs_minutes_lag_divergence",
]


# ============================================================
# Data prep
# ============================================================


def prepare_classification_data_v3(
    features_v3_table: pd.DataFrame,
    targets_table: pd.DataFrame,
    target_name: str,
) -> tuple[pd.DataFrame, pd.Series]:
    """Align features_v3 + target on meeting_date, drop NaN rows, coerce y to int.

    Uses FEATURES_FOR_CLASSIFICATION_V3. Expect more rows dropped than v2 due to
    NaN in engineered features (first meeting: momentum NaN; first two: acceleration
    NaN). Logs the drop explicitly.
    """
    X = features_v3_table[FEATURES_FOR_CLASSIFICATION_V3].copy()
    y = targets_table[target_name].copy()
    joined_raw = X.join(y, how="inner")
    before = len(joined_raw)
    joined = joined_raw.dropna(subset=FEATURES_FOR_CLASSIFICATION_V3 + [target_name])
    after = len(joined)
    dropped = before - after
    logger.info(
        "prepare_classification_data_v3(%s): %d rows in, %d rows after NaN drop (%d dropped)",
        target_name,
        before,
        after,
        dropped,
    )
    X_clean = joined[FEATURES_FOR_CLASSIFICATION_V3].astype(float)
    y_clean = joined[target_name].astype(int)
    y_clean.name = target_name
    return X_clean, y_clean


# ============================================================
# Experiment orchestrator
# ============================================================


def run_full_experiment_v3(
    features_v3_path: Path = Path("data/divergence/calibration_features_v3.parquet"),
    targets_v2_path: Path = Path("data/divergence/targets_v2.parquet"),
    master_table_path: Path = Path("data/divergence/calibration_features.parquet"),
    rrd_path: Path = Path("data/market_pricing/real_rate_differential.parquet"),
    v2_results_path: Path = Path("data/divergence/experiment_v2_results.parquet"),
    output_results_path: Path = Path("data/divergence/experiment_v3_results.parquet"),
    output_report_path: Path = Path("data/divergence/experiment_v3_report.md"),
) -> pd.DataFrame:
    """Run 2 targets × 5 classifiers = 10 combinations on expanded feature set.

    Same gate logic as v2:
      - meets_hit_rate_threshold: val hit_rate_nonzero > HIT_RATE_THRESHOLD
      - meets_coverage_gate:      val n_nonzero_pred >= MIN_NONZERO_SIGNALS_VAL
      - stability_gate_passed:    CV mean hit_rate_nonzero > 0.5 AND
                                  val hit_rate_nonzero > 0.5
    """
    features_v3_path = Path(features_v3_path)
    if not features_v3_path.exists():
        logger.info("Features v3 parquet missing — building now at %s", features_v3_path)
        build_features_v3_table(
            master_table_path=master_table_path,
            rrd_path=rrd_path,
            output_path=features_v3_path,
        )

    features_v3 = pd.read_parquet(features_v3_path)
    targets = pd.read_parquet(targets_v2_path)

    rows = []
    per_combo_detail: dict = {}
    for target_name in TARGET_NAMES:
        X, y = prepare_classification_data_v3(features_v3, targets, target_name)
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
    logger.info(
        "Experiment v3 results persisted: %s (%d rows)", output_results_path, len(results)
    )

    # Load v2 baseline for comparison section (if present).
    v2_results: pd.DataFrame | None = None
    try:
        v2_results = pd.read_parquet(v2_results_path)
    except Exception as e:
        logger.warning("Could not load v2 results for comparison: %s", e)

    _write_report_v3(
        results=results,
        features_v3=features_v3,
        targets=targets,
        per_combo_detail=per_combo_detail,
        v2_results=v2_results,
        output_path=Path(output_report_path),
    )
    return results


# ============================================================
# Report
# ============================================================


def _merge_v2_v3_for_comparison(
    v2: pd.DataFrame, v3: pd.DataFrame
) -> pd.DataFrame:
    keep_v2 = v2[
        [
            "target",
            "classifier",
            "cv_mean_hit_rate",
            "val_hit_rate",
            "val_n_nonzero_pred",
            "meets_hit_rate_threshold",
            "meets_coverage_gate",
            "stability_gate_passed",
        ]
    ].rename(
        columns={
            "cv_mean_hit_rate": "v2_cv_hit",
            "val_hit_rate": "v2_val_hit",
            "val_n_nonzero_pred": "v2_n_nz",
            "meets_hit_rate_threshold": "v2_hit_pass",
            "meets_coverage_gate": "v2_cov_pass",
            "stability_gate_passed": "v2_stab_pass",
        }
    )
    keep_v3 = v3[
        [
            "target",
            "classifier",
            "cv_mean_hit_rate",
            "val_hit_rate",
            "val_n_nonzero_pred",
            "meets_hit_rate_threshold",
            "meets_coverage_gate",
            "stability_gate_passed",
        ]
    ].rename(
        columns={
            "cv_mean_hit_rate": "v3_cv_hit",
            "val_hit_rate": "v3_val_hit",
            "val_n_nonzero_pred": "v3_n_nz",
            "meets_hit_rate_threshold": "v3_hit_pass",
            "meets_coverage_gate": "v3_cov_pass",
            "stability_gate_passed": "v3_stab_pass",
        }
    )
    return keep_v3.merge(keep_v2, on=["target", "classifier"], how="outer")


def _write_report_v3(
    results: pd.DataFrame,
    features_v3: pd.DataFrame,
    targets: pd.DataFrame,
    per_combo_detail: dict,
    v2_results: pd.DataFrame | None,
    output_path: Path,
) -> None:
    lines: list[str] = []
    lines.append("# CC-2a-v3 — Dual-Target Classification (Engineered Features) — Results Report")
    lines.append("")
    lines.append(f"Generated: {pd.Timestamp.now().isoformat()}")
    lines.append("")

    # --- 1. Experiment setup (v3 context)
    lines.append("## 1. Experiment Setup (v3 context)")
    lines.append("")
    lines.append("**What changed from v2:** 7 theory-driven engineered features added to the classification "
                 "feature set. Everything else is identical — same classifiers, same split, same gates, same seed.")
    lines.append("")
    lines.append("**Theoretical justification (committed BEFORE running v3):**")
    lines.append("")
    lines.append("- **Momentum** (Macrosynergy 2024, *information change framing*): level alone under-predicts; "
                 "meeting-over-meeting change in tone and rate differential is the information-bearing signal.")
    lines.append("- **Acceleration** (Scheffer et al. 2009, *Early Warning Signals for Critical Transitions*, "
                 "Nature): regime transitions are preceded by acceleration in key indicators, not by level "
                 "threshold crossings alone.")
    lines.append("- **Divergence** (Djourelova et al. 2025, *communication coherence*): discordance between "
                 "sources — Fed rhetoric vs market pricing, Fed now vs Fed 6 weeks ago — is itself the signal.")
    lines.append("")
    lines.append("**Pre-committed thresholds (unchanged from v2):**")
    lines.append(f"- Hit rate threshold: {HIT_RATE_THRESHOLD}")
    lines.append(f"- Coverage gate: val n_nonzero_pred ≥ {MIN_NONZERO_SIGNALS_VAL}")
    lines.append("- Stability gate: CV mean hit_rate > 0.5 AND val hit_rate > 0.5")
    lines.append(f"- Train/val split: chronological at {TRAIN_END_DATE.date()}")
    lines.append(f"- CV protocol: walk-forward (expanding window), 5 splits on train only")
    lines.append(f"- Random seed: {RANDOM_SEED}")
    lines.append("")

    # --- 2. Feature inventory
    n_original = len(FEATURES_FOR_CLASSIFICATION_V3) - len(ENGINEERED_FEATURES)
    lines.append("## 2. Feature Inventory")
    lines.append("")
    lines.append(f"**Total features: {len(FEATURES_FOR_CLASSIFICATION_V3)}** "
                 f"({n_original} original + {len(ENGINEERED_FEATURES)} engineered)")
    lines.append("")
    lines.append("### Engineered feature NaN distribution")
    lines.append("")
    lines.append("| Feature | NaN count | Reason |")
    lines.append("|---|---|---|")
    nan_reasons = {
        "statement_momentum": "T-1 required (first meeting NaN)",
        "minutes_lag_momentum": "T-1 required on minutes_lag which is NaN at T=0 → NaN for first 2 meetings",
        "real_rate_diff_momentum_21bd": "21bd daily lookback — 0 NaN when rrd history covers pre-sample",
        "statement_acceleration": "T-1 of momentum → NaN for first 2 meetings",
        "cleveland_acceleration": "T-2 required → NaN for first 2 meetings",
        "nlp_vs_fedwatch_divergence": "No lag required → 0 NaN",
        "statement_vs_minutes_lag_divergence": "minutes_lag NaN at T=0 → NaN for first meeting",
    }
    for feat in ENGINEERED_FEATURES:
        n_nan = int(features_v3[feat].isna().sum())
        reason = nan_reasons.get(feat, "")
        lines.append(f"| `{feat}` | {n_nan} | {reason} |")
    lines.append("")
    lines.append("### Rows dropped when preparing classification data")
    lines.append("")
    lines.append("| Target | Rows after NaN drop | Train | Val |")
    lines.append("|---|---|---|---|")
    for target_name in TARGET_NAMES:
        X, y = prepare_classification_data_v3(features_v3, targets, target_name)
        X_train, _, X_val, _ = split_train_validation(X, y)
        lines.append(f"| `{target_name}` | {len(X)} | {len(X_train)} | {len(X_val)} |")
    lines.append("")

    # --- 3. Results table (10 combinations)
    lines.append("## 3. Results — All 10 Combinations (v3)")
    lines.append("")
    lines.append(
        "| Target | Classifier | CV hit± std | Val hit | Val n_nonzero_pred "
        "| Val acc | Hit>0.60 | Cov≥8 | Stability |"
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
            f"{'OK' if r['meets_hit_rate_threshold'] else '-'} | "
            f"{'OK' if r['meets_coverage_gate'] else '-'} | "
            f"{'OK' if r['stability_gate_passed'] else '-'} |"
        )
    lines.append("")

    # --- 4. V2 vs V3 comparison
    lines.append("## 4. V2 vs V3 Comparison")
    lines.append("")
    if v2_results is None:
        lines.append("*v2 results not available on disk; comparison skipped.*")
        lines.append("")
    else:
        merged = _merge_v2_v3_for_comparison(v2_results, results)
        # Per-combination deltas
        lines.append(
            "| Target | Classifier | v2 val_hit | v3 val_hit | Δhit | v2 n_nz | v3 n_nz | Δn_nz | Gate change |"
        )
        lines.append("|---|---|---|---|---|---|---|---|---|")
        regressions = 0
        rescues = 0
        for _, r in merged.iterrows():
            v2h = r.get("v2_val_hit", np.nan)
            v3h = r.get("v3_val_hit", np.nan)
            dh = v3h - v2h if (not pd.isna(v2h) and not pd.isna(v3h)) else np.nan
            v2n = r.get("v2_n_nz", 0)
            v3n = r.get("v3_n_nz", 0)
            dn = int(v3n) - int(v2n) if (not pd.isna(v2n) and not pd.isna(v3n)) else 0

            v2_passed = bool(r.get("v2_hit_pass", False)) and bool(r.get("v2_cov_pass", False)) and bool(
                r.get("v2_stab_pass", False)
            )
            v3_passed = bool(r.get("v3_hit_pass", False)) and bool(r.get("v3_cov_pass", False)) and bool(
                r.get("v3_stab_pass", False)
            )
            if v3_passed and not v2_passed:
                gate_change = "rescued"
                rescues += 1
            elif v2_passed and not v3_passed:
                gate_change = "regression"
                regressions += 1
            elif v2_passed and v3_passed:
                gate_change = "still passing"
            else:
                gate_change = "no change"

            tgt_short = str(r["target"]).replace("target_", "").replace("_class", "")
            v2h_s = f"{v2h:.3f}" if not pd.isna(v2h) else "NaN"
            v3h_s = f"{v3h:.3f}" if not pd.isna(v3h) else "NaN"
            dh_s = f"{dh:+.3f}" if not pd.isna(dh) else "n/a"
            lines.append(
                f"| {tgt_short} | {r['classifier']} | {v2h_s} | {v3h_s} | {dh_s} | "
                f"{int(v2n)} | {int(v3n)} | {dn:+d} | {gate_change} |"
            )
        lines.append("")
        lines.append(f"**Summary:** {rescues} combination(s) rescued (failed in v2, pass in v3); "
                     f"{regressions} combination(s) regressed (passed in v2, fail in v3).")
        lines.append("")

    # --- 5. Engineered feature importance
    lines.append("## 5. Engineered Feature Importance")
    lines.append("")
    lines.append("For each combination that has a feature-importance vector, we count how often "
                 "each engineered feature appears in its top-5.")
    lines.append("")
    engineered_set = set(ENGINEERED_FEATURES)
    eng_in_top5_counts: dict[str, int] = {f: 0 for f in ENGINEERED_FEATURES}
    total_combos_with_importance = 0
    for _, r in results.iterrows():
        top_feats_str = r.get("top_features", "") or ""
        if not top_feats_str:
            continue
        total_combos_with_importance += 1
        top_feats = [t.strip() for t in top_feats_str.split(",") if t.strip()]
        for tf in top_feats:
            if tf in engineered_set:
                eng_in_top5_counts[tf] += 1
    lines.append(
        f"**Combinations with feature-importance vector available:** {total_combos_with_importance} / {len(results)}."
    )
    lines.append("")
    lines.append("| Engineered feature | Times in top-5 |")
    lines.append("|---|---|")
    for f, c in sorted(eng_in_top5_counts.items(), key=lambda x: -x[1]):
        lines.append(f"| `{f}` | {c} |")
    lines.append("")
    lines.append("**Theoretical predictions — empirical check:**")
    momentum_hits = sum(
        eng_in_top5_counts[f] for f in ("statement_momentum", "minutes_lag_momentum", "real_rate_diff_momentum_21bd")
    )
    accel_hits = sum(eng_in_top5_counts[f] for f in ("statement_acceleration", "cleveland_acceleration"))
    div_hits = sum(eng_in_top5_counts[f] for f in ("nlp_vs_fedwatch_divergence", "statement_vs_minutes_lag_divergence"))
    lines.append(f"- Momentum features in top-5: **{momentum_hits}** total (across combinations).")
    lines.append(f"- Acceleration features in top-5: **{accel_hits}** total.")
    lines.append(f"- Divergence features in top-5: **{div_hits}** total.")
    lines.append("")

    # --- 6. Winners passing all 3 gates (split by target)
    winners = results[
        results["meets_hit_rate_threshold"]
        & results["meets_coverage_gate"]
        & results["stability_gate_passed"]
    ]
    lines.append("## 6. Winners — Combinations Passing All 3 Gates (v3)")
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
            lines.append("| Classifier | Val hit rate | Val n_nonzero_pred | CV mean hit rate | Top features |")
            lines.append("|---|---|---|---|---|")
            for _, r in w_tgt.sort_values("val_hit_rate", ascending=False).iterrows():
                lines.append(
                    f"| {r['classifier']} | {r['val_hit_rate']:.3f} | "
                    f"{int(r['val_n_nonzero_pred'])} | {r['cv_mean_hit_rate']:.3f} | "
                    f"{r['top_features'] or '(none)'} |"
                )
        lines.append("")

    # --- 7. Confusion matrices
    lines.append("## 7. Confusion Matrices (rows = true class, cols = predicted, labels [-1, 0, +1])")
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

    # --- 8. Trading workflow implications
    lines.append("## 8. Trading Workflow Implications")
    lines.append("")
    if len(winners) == 0:
        lines.append("No combination passed all 3 gates in v3. Trading workflow implication: "
                     "**do not deploy any v3 classifier in production**. Engineered features "
                     "did not rescue the signal under the pre-committed protocol.")
    else:
        lines.append("Two targets remain complementary, not substitutes:")
        lines.append("")
        lines.append("- **Regime signal:** position-direction filter over multi-week horizon.")
        lines.append("- **Surprise signal:** event-level timing / confirmation on FOMC day.")
        lines.append("")
        lines.append("Where a v3 winner exists, it should carry forward to CC-2b for production calibration. "
                     "Composite scoring (regime × surprise) is out of scope for this experiment.")
    lines.append("")

    # --- 9. Recommendation for CC-2b
    scenario, recommendation = _scenario_and_recommendation(results)
    lines.append("## 9. Recommendation for CC-2b")
    lines.append("")
    lines.append(f"**Scenario {scenario}** — {recommendation}")
    lines.append("")
    lines.append("Scenario legend:")
    lines.append("- **A**: both targets have ≥1 winner → dual-signal production.")
    lines.append("- **B**: only regime has a winner → regime-only production.")
    lines.append("- **C**: only surprise has a winner → surprise-only production.")
    lines.append("- **D**: no winners.")
    lines.append("")
    if scenario == "D":
        lines.append(
            "**Operational recommendation:** proceed to infrastructure build (CC-7 backtesting, "
            "PRD-051 dashboard). Re-attempt calibration in 6 months with more FOMC meetings "
            "accumulated. Do NOT loosen thresholds to manufacture a winner — that is p-hacking "
            "against the pre-commit and will not generalize."
        )
    else:
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
        lines.append(
            "**Operational recommendation:** proceed to CC-2b production calibration on the identified "
            "combinations. Engineered features must be included in the production feature pipeline."
        )
    lines.append("")

    # --- 10. Caveats
    lines.append("## 10. Caveats")
    lines.append("")
    lines.append("- **Small sample.** N≈26–28 train meetings, ≈13 validation. Engineered features drop "
                 "1–2 additional rows (first meeting lost to momentum NaN; first two to acceleration NaN).")
    lines.append("- **Multiple testing.** v3 is a re-run of the v2 protocol with a different feature set. "
                 "Mathematically this inflates family-wise error rate beyond v2 alone. Theory-driven feature "
                 "choice mitigates (we did not grid-search over arbitrary transforms) but does not eliminate.")
    lines.append("- **Feature choice was committed BEFORE running.** We do NOT tune or swap features "
                 "based on v3 results — that is p-hacking. If v3 ends Scenario D, the right response is "
                 "NOT more feature engineering; it is more data or a new pre-commit.")
    lines.append("- **Train/val regime asymmetry persists.** Train ends 2024-06-30 (hiking + plateau); "
                 "validation is cutting cycle. Engineered features may behave differently across these regimes.")
    lines.append("- **One validation pass only.** Do NOT re-tune, swap classifiers, or add/remove engineered "
                 "features based on this report.")
    lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Experiment v3 report written: %s", output_path)
