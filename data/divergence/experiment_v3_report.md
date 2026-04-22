# CC-2a-v3 — Dual-Target Classification (Engineered Features) — Results Report

Generated: 2026-04-22T17:59:51.460823

## 1. Experiment Setup (v3 context)

**What changed from v2:** 7 theory-driven engineered features added to the classification feature set. Everything else is identical — same classifiers, same split, same gates, same seed.

**Theoretical justification (committed BEFORE running v3):**

- **Momentum** (Macrosynergy 2024, *information change framing*): level alone under-predicts; meeting-over-meeting change in tone and rate differential is the information-bearing signal.
- **Acceleration** (Scheffer et al. 2009, *Early Warning Signals for Critical Transitions*, Nature): regime transitions are preceded by acceleration in key indicators, not by level threshold crossings alone.
- **Divergence** (Djourelova et al. 2025, *communication coherence*): discordance between sources — Fed rhetoric vs market pricing, Fed now vs Fed 6 weeks ago — is itself the signal.

**Pre-committed thresholds (unchanged from v2):**
- Hit rate threshold: 0.6
- Coverage gate: val n_nonzero_pred ≥ 8
- Stability gate: CV mean hit_rate > 0.5 AND val hit_rate > 0.5
- Train/val split: chronological at 2024-06-30
- CV protocol: walk-forward (expanding window), 5 splits on train only
- Random seed: 42

## 2. Feature Inventory

**Total features: 18** (11 original + 7 engineered)

### Engineered feature NaN distribution

| Feature | NaN count | Reason |
|---|---|---|
| `statement_momentum` | 1 | T-1 required (first meeting NaN) |
| `minutes_lag_momentum` | 2 | T-1 required on minutes_lag which is NaN at T=0 → NaN for first 2 meetings |
| `real_rate_diff_momentum_21bd` | 0 | 21bd daily lookback — 0 NaN when rrd history covers pre-sample |
| `statement_acceleration` | 2 | T-1 of momentum → NaN for first 2 meetings |
| `cleveland_acceleration` | 2 | T-2 required → NaN for first 2 meetings |
| `nlp_vs_fedwatch_divergence` | 0 | No lag required → 0 NaN |
| `statement_vs_minutes_lag_divergence` | 1 | minutes_lag NaN at T=0 → NaN for first meeting |

### Rows dropped when preparing classification data

| Target | Rows after NaN drop | Train | Val |
|---|---|---|---|
| `target_surprise_class` | 40 | 26 | 14 |
| `target_regime_class` | 39 | 26 | 13 |

## 3. Results — All 10 Combinations (v3)

| Target | Classifier | CV hit± std | Val hit | Val n_nonzero_pred | Val acc | Hit>0.60 | Cov≥8 | Stability |
|---|---|---|---|---|---|---|---|---|
| surprise | equal_weighted | 0.222 ± 0.314 | 0.167 | 12 | 0.286 | - | OK | - |
| surprise | logistic_l2 | 0.125 ± 0.217 | 0.000 | 4 | 0.500 | - | - | - |
| surprise | ridge | 0.000 ± 0.000 | 0.000 | 7 | 0.357 | - | - | - |
| surprise | svc_rbf | 0.200 ± 0.163 | 0.167 | 6 | 0.500 | - | - | - |
| surprise | random_forest | 0.222 ± 0.157 | NaN | 0 | 0.786 | - | - | - |
| regime | equal_weighted | 0.000 ± 0.000 | 0.273 | 11 | 0.308 | - | OK | - |
| regime | logistic_l2 | 0.000 ± 0.000 | 0.667 | 3 | 0.615 | OK | - | - |
| regime | ridge | 0.000 ± 0.000 | 0.600 | 5 | 0.615 | - | - | - |
| regime | svc_rbf | 0.000 ± 0.000 | 0.250 | 4 | 0.385 | - | - | - |
| regime | random_forest | 0.200 ± 0.400 | 0.000 | 1 | 0.462 | - | - | - |

## 4. V2 vs V3 Comparison

| Target | Classifier | v2 val_hit | v3 val_hit | Δhit | v2 n_nz | v3 n_nz | Δn_nz | Gate change |
|---|---|---|---|---|---|---|---|---|
| regime | equal_weighted | 0.273 | 0.273 | +0.000 | 11 | 11 | +0 | no change |
| regime | logistic_l2 | 1.000 | 0.667 | -0.333 | 2 | 3 | +1 | no change |
| regime | random_forest | NaN | 0.000 | n/a | 0 | 1 | +1 | no change |
| regime | ridge | 0.429 | 0.600 | +0.171 | 7 | 5 | -2 | no change |
| regime | svc_rbf | 0.000 | 0.250 | +0.250 | 2 | 4 | +2 | no change |
| surprise | equal_weighted | 0.167 | 0.167 | +0.000 | 12 | 12 | +0 | no change |
| surprise | logistic_l2 | 0.000 | 0.000 | +0.000 | 3 | 4 | +1 | no change |
| surprise | random_forest | NaN | NaN | n/a | 0 | 0 | +0 | no change |
| surprise | ridge | 0.000 | 0.000 | +0.000 | 6 | 7 | +1 | no change |
| surprise | svc_rbf | 0.000 | 0.167 | +0.167 | 6 | 6 | +0 | no change |

**Summary:** 0 combination(s) rescued (failed in v2, pass in v3); 0 combination(s) regressed (passed in v2, fail in v3).

## 5. Engineered Feature Importance

For each combination that has a feature-importance vector, we count how often each engineered feature appears in its top-5.

**Combinations with feature-importance vector available:** 8 / 10.

| Engineered feature | Times in top-5 |
|---|---|
| `statement_momentum` | 5 |
| `real_rate_diff_momentum_21bd` | 2 |
| `cleveland_acceleration` | 2 |
| `nlp_vs_fedwatch_divergence` | 2 |
| `minutes_lag_momentum` | 1 |
| `statement_acceleration` | 1 |
| `statement_vs_minutes_lag_divergence` | 0 |

**Theoretical predictions — empirical check:**
- Momentum features in top-5: **8** total (across combinations).
- Acceleration features in top-5: **3** total.
- Divergence features in top-5: **2** total.

## 6. Winners — Combinations Passing All 3 Gates (v3)

### Surprise

**No winners for `target_surprise_class`.**

### Regime

**No winners for `target_regime_class`.**

## 7. Confusion Matrices (rows = true class, cols = predicted, labels [-1, 0, +1])

*No winners — showing the 2 highest val-hit-rate combinations for diagnostic reference.*

### regime × logistic_l2

```
[[1, 2, 0], [0, 6, 0], [1, 2, 1]]
```

### regime × ridge

```
[[1, 2, 0], [1, 5, 0], [1, 1, 2]]
```

## 8. Trading Workflow Implications

No combination passed all 3 gates in v3. Trading workflow implication: **do not deploy any v3 classifier in production**. Engineered features did not rescue the signal under the pre-committed protocol.

## 9. Recommendation for CC-2b

**Scenario D** — Signal insufficient at N=30. Options: (1) wait for more meetings, (2) revise features, (3) relax thresholds (with new pre-commit).

Scenario legend:
- **A**: both targets have ≥1 winner → dual-signal production.
- **B**: only regime has a winner → regime-only production.
- **C**: only surprise has a winner → surprise-only production.
- **D**: no winners.

**Operational recommendation:** proceed to infrastructure build (CC-7 backtesting, PRD-051 dashboard). Re-attempt calibration in 6 months with more FOMC meetings accumulated. Do NOT loosen thresholds to manufacture a winner — that is p-hacking against the pre-commit and will not generalize.

## 10. Caveats

- **Small sample.** N≈26–28 train meetings, ≈13 validation. Engineered features drop 1–2 additional rows (first meeting lost to momentum NaN; first two to acceleration NaN).
- **Multiple testing.** v3 is a re-run of the v2 protocol with a different feature set. Mathematically this inflates family-wise error rate beyond v2 alone. Theory-driven feature choice mitigates (we did not grid-search over arbitrary transforms) but does not eliminate.
- **Feature choice was committed BEFORE running.** We do NOT tune or swap features based on v3 results — that is p-hacking. If v3 ends Scenario D, the right response is NOT more feature engineering; it is more data or a new pre-commit.
- **Train/val regime asymmetry persists.** Train ends 2024-06-30 (hiking + plateau); validation is cutting cycle. Engineered features may behave differently across these regimes.
- **One validation pass only.** Do NOT re-tune, swap classifiers, or add/remove engineered features based on this report.
