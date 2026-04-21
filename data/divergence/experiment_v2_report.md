# CC-2a-v2 — Dual-Target Classification Experiment — Results Report

Generated: 2026-04-21T23:13:40.510218

## 1. Experiment Setup (v2 context)

**Architecture:** 2 independent classification targets × 5 classifiers = 10 combinations.

**Why classification, not regression:** v1 measured Spearman IC (ordering of magnitudes). The user's real workflow is:
  1. Detect the structural regime (EUR/USD direction over ~2 months).
  2. Use FedWatch surprise as event-level confirmation/timing.

Hit rate on non-zero directional predictions is the metric that maps directly to trading decisions.

**Pre-committed thresholds:**
- Hit rate threshold: 0.6
- Coverage gate: val n_nonzero_pred ≥ 8
- Stability gate: CV mean hit_rate > 0.5 AND val hit_rate > 0.5
- Train/val split: chronological at 2024-06-30
- CV protocol: walk-forward (expanding window), 5 splits on train only
- Features (11): `statement_ensemble_net`, `statement_fomc_roberta_net`, `statement_llama_deepinfra_net`, `minutes_lag_ensemble_net`, `minutes_lag_fomc_roberta_net`, `minutes_lag_llama_deepinfra_net`, `fedwatch_implied_change_bps`, `real_rate_diff_5y`, `cleveland_national_score`, `cleveland_consensus_score`, `cleveland_divergence`
- Random seed: 42

## 2. Target Distributions

### `target_surprise_class`

| Class | Count (all meetings) |
|---|---|
| -1 | 9 |
| 0 | 27 |
| 1 | 6 |

| Class | Train count | Val count |
|---|---|---|
| -1 | 7 | 2 |
| 0 | 16 | 11 |
| 1 | 5 | 1 |


### `target_regime_class`

| Class | Count (all meetings) |
|---|---|
| -1 | 11 |
| 0 | 23 |
| 1 | 7 |
| NaN | 1 |

| Class | Train count | Val count |
|---|---|---|
| -1 | 8 | 3 |
| 0 | 17 | 6 |
| 1 | 3 | 4 |
| NaN | 0 | 1 |

> **WARN:** training has only 3 example(s) of class 1 — classifier may struggle.

## 3. Results — All 10 Combinations

| Target | Classifier | CV hit± std | Val hit | Val n_nonzero_pred | Val acc | Hit≥0.60 | Cov≥8 | Stability |
|---|---|---|---|---|---|---|---|---|
| surprise | equal_weighted | 0.333 ± 0.408 | 0.167 | 12 | 0.286 | ✗ | ✓ | ✗ |
| surprise | logistic_l2 | 0.067 ± 0.133 | 0.000 | 3 | 0.571 | ✗ | ✗ | ✗ |
| surprise | ridge | 0.067 ± 0.133 | 0.000 | 6 | 0.357 | ✗ | ✗ | ✗ |
| surprise | svc_rbf | 0.133 ± 0.163 | 0.000 | 6 | 0.357 | ✗ | ✗ | ✗ |
| surprise | random_forest | 0.167 ± 0.167 | NaN | 0 | 0.786 | ✗ | ✗ | ✗ |
| regime | equal_weighted | 0.233 ± 0.291 | 0.273 | 11 | 0.231 | ✗ | ✓ | ✗ |
| regime | logistic_l2 | 0.000 ± 0.000 | 1.000 | 2 | 0.615 | ✓ | ✗ | ✗ |
| regime | ridge | 0.250 ± 0.433 | 0.429 | 7 | 0.538 | ✗ | ✗ | ✗ |
| regime | svc_rbf | 0.000 ± 0.000 | 0.000 | 2 | 0.308 | ✗ | ✗ | ✗ |
| regime | random_forest | 0.000 ± 0.000 | NaN | 0 | 0.462 | ✗ | ✗ | ✗ |

## 4. Winners — Combinations Passing All 3 Gates

### Surprise

**No winners for `target_surprise_class`.**

### Regime

**No winners for `target_regime_class`.**

## 5. Top Features per Winner

*No winners — showing top features for the highest-hit-rate combo per target for reference.*

- **surprise × equal_weighted** (val hit=0.167, n_nonzero=12): statement_ensemble_net, statement_fomc_roberta_net, statement_llama_deepinfra_net, minutes_lag_ensemble_net, minutes_lag_fomc_roberta_net
- **regime × logistic_l2** (val hit=1.000, n_nonzero=2): cleveland_consensus_score, statement_llama_deepinfra_net, real_rate_diff_5y, fedwatch_implied_change_bps, cleveland_divergence

## 6. Confusion Matrices (rows = true class, cols = predicted)

Labels in order: [-1, 0, +1].

*No winners — showing the 2 highest val-hit-rate combinations for diagnostic reference.*

### regime × logistic_l2

```
[[0, 3, 0], [0, 6, 0], [0, 2, 2]]
```

### regime × ridge

```
[[1, 1, 1], [0, 4, 2], [1, 1, 2]]
```

## 7. Trading Workflow Implications

The two targets are complementary, not substitutes:

- **Regime signal (42 bd horizon):** slow-moving, persists for weeks. Acts as a **position-direction filter**. A +1 regime = bias long EUR/USD; -1 regime = bias short; 0 regime = no structural bias → stand aside.
- **Surprise signal (event-level):** fast, fires on FOMC day. Acts as **entry timing / confirmation**. A +1 surprise inside a +1 regime = dual confirmation → higher-conviction entry. Contradictory signals (e.g. +1 regime, -1 surprise) → reduced size or wait for the next event.

Combination logic is NOT calibrated in this experiment — that is scope for CC-2b (production calibration) or CC-7 (composite scoring). This report only selects the individual classifier(s) worth carrying forward.

## 8. Recommendation for CC-2b

**Scenario D** — Signal insufficient at N=30. Options: (1) wait for more meetings, (2) revise features, (3) relax thresholds (with new pre-commit).

Scenario legend:
- **A**: both targets have ≥1 winner → dual-signal production.
- **B**: only regime has a winner → regime-only production.
- **C**: only surprise has a winner → surprise-only production.
- **D**: no winners → treat N=30 train as underpowered; pick one of: (1) wait for more meetings, (2) revise the feature set, (3) relax thresholds via a *new* pre-commit (do not p-hack the existing one).

## 9. Caveats

- **Sample size is small by ML standards:** ~28 train meetings, ~14 validation. Single outliers can flip gate results.
- **Regime shift:** train spans the 2022–2023 hiking cycle + plateau; validation spans the 2024+ cutting cycle. Coefficients fit to hiking-era Fed behavior may not transfer.
- **Coverage gate (≥8 non-zero val predictions):** a classifier that is too conservative — predicting class 0 too often — fails the gate even with high accuracy on the few directional calls it does make. Low coverage = low trading utility, which is the correct rejection.
- **Multiple testing:** 10 combinations evaluated → family-wise error rate inflated. Pre-committed gates mitigate but do not eliminate this.
- **One validation pass only.** Do NOT re-tune or swap classifiers based on this report; that is p-hacking against the pre-commit.
