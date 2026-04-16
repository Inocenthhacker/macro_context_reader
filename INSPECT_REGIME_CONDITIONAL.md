# regime_conditional.py — Inspection Report

Generated: 2026-04-15

## File summary

- **Lines:** 315
- **Functions:** 5 (4 public: `load_aligned_data`, `compute_conditional_correlations`, `compute_lead_lag`; 2 private: `_bootstrap_pearson_ci`, `_permutation_pvalue`)
- **Classes:** 2 Pydantic schemas (`RegimeCorrelation`, `RegimeConditionalResults`)
- **Tests:** 12, all in `tests/divergence/test_regime_conditional.py`
- **Notebook consumers:** 1 — `notebooks/03_regime_conditional_diagnostic.ipynb` (titled *"PRD-300 / CC-0d — Regime-Conditional Correlation Diagnostic"*)

## Function-by-function classification

| Function / Class | Inputs | Outputs | Classification | Justification |
|---|---|---|---|---|
| `load_aligned_data(start="2003-01-01") -> pd.DataFrame` | FRED real_rate_diff parquet + fetch_fx_eurusd + HMM regime history | DataFrame with monthly `real_rate_diff`, `eurusd`, `regime_state`, `regime_label`, `regime_prob_max` | **DIAGNOSTIC** | Produces a wide-format alignment frame for inspection; does not calibrate or fit anything, no downstream consumer outside diagnostic notebook and tests. |
| `_bootstrap_pearson_ci(x, y, n_resamples, random_state) -> (low, high)` | 2 numpy arrays | 95% CI tuple | **DIAGNOSTIC** | Descriptive statistic bundled with correlation result for human reading; not used to weight or gate downstream signals. |
| `_permutation_pvalue(x, y, n_perm, random_state) -> float` | 2 numpy arrays | scalar p-value | **DIAGNOSTIC** | Significance test to support the DEC-009 claim; no downstream consumer. |
| `compute_lead_lag(x, y, max_lag=6) -> dict[int, float]` | 2 numpy arrays | {lag: correlation} | **DIAGNOSTIC** | Cross-correlation scan for exploratory lead/lag inspection; output embedded in `RegimeCorrelation` schema but never feeds a model. |
| `compute_conditional_correlations(df, ...) -> RegimeConditionalResults` | aligned DataFrame | Pydantic bundle: `global_pearson`, `per_regime` list (Pearson level + diff + Spearman + Kendall + lead-lag + bootstrap CI + p-value), `comparison_vs_global`, `regime_switching_confirmed` boolean | **DIAGNOSTIC** | Returns a statistics bundle for inspection and hypothesis validation; no calibrated weight vector, no regime→score mapping, no parameters intended for `composite_divergence_score`. The `regime_switching_confirmed` boolean is a validation flag (DEC-009), not a production gate. |
| `RegimeCorrelation` (Pydantic) | — | `pearson_level`, `pearson_level_ci95`, `pearson_level_pvalue`, `pearson_diff`, `spearman`, `kendall`, `best_lag_months`, `best_lag_corr`, `n_obs`, `low_sample_warning`, `regime_label/state` | **DIAGNOSTIC** | Pure descriptive schema; all fields are statistics for human reading. |
| `RegimeConditionalResults` (Pydantic) | — | `global_pearson`, `per_regime: list`, `comparison_vs_global: dict`, `regime_switching_confirmed: bool` | **DIAGNOSTIC** | Wraps per-regime statistics + hypothesis-validation boolean; no field is a model parameter. |
| Constant `MIN_OBS_PER_REGIME = 30` | — | 30 | **DIAGNOSTIC** | Threshold for `low_sample_warning` flag only. |

All 7 code units → DIAGNOSTIC. Zero PREDICTIVE units.

## Consumer analysis

### Tests (`tests/divergence/test_regime_conditional.py`)

| Test | What it verifies | Nature |
|---|---|---|
| `test_detects_strong_correlations` | On synthetic data with known regime correlations, `pearson_level` recovers them | Descriptive-correctness |
| `test_n_obs_match` | Sum of per-regime n_obs = input row count | Accounting sanity |
| `test_bootstrap_ci_not_degenerate` | `low < high` on CI tuple | Statistic well-formed |
| `test_permutation_pvalue_reproducible` | Same `random_state` → same p-value | Determinism |
| `test_regime_switching_confirmed` | Strong synthetic split sets flag True | Hypothesis flag |
| `test_regime_switching_not_confirmed_weak_corrs` | Weak synthetic split sets flag False | Hypothesis flag negative |
| `test_identical_series_lag_zero` | Lead-lag peaks at 0 for identical series | Lag statistic correctness |
| `test_lead_lag_symmetry` | Dict keys span `[-max_lag, +max_lag]` | Completeness |
| `test_bootstrap_ci_contains_true_corr` | CI lower > 0.3 for r≈0.8 | Statistic correctness |
| `test_permutation_significant_for_strong_corr` | p < 0.05 on strongly correlated data | Statistic correctness |
| `test_low_sample_warning` | `n_obs < 30 → low_sample_warning=True` | Flag correctness |
| `test_default_start_respects_t5yie` | Default `start >= 2003-01-01` | Data availability guard |

**Every test verifies a descriptive statistic or a hypothesis-flag behaviour. No test treats an output as a production parameter (e.g. "this weight is between 0 and 1 and sums across regimes to 1").**

### Notebook: `notebooks/03_regime_conditional_diagnostic.ipynb`

- 9 cells total; title cell confirms *"Regime-Conditional Correlation Diagnostic"* explicitly scoped to **PRD-300 / CC-0d**.
- Imports: `load_aligned_data`, `compute_conditional_correlations`.
- Usage: loads the alignment frame, computes per-regime stats, then visualizes via `matplotlib`. No cell captures the output for feeding into a calibration or scoring function.

## Overlap with PRD-300 v2 CC-3 plans

PRD-300 v2 CC-3 specifies two predictive artifacts:

- **`regime_conditional/fitter.py`** — *fits weights per regime* (e.g. an OLS or Ridge re-estimated inside each regime partition, producing a weight vector `w_r ∈ R^k` per regime)
- **`regime_conditional/router.py`** — *selects weights based on current regime* (e.g. `get_regime_weights(current_regime) -> w_r` for runtime composite scoring)

Inspection of `regime_conditional.py`:

| CC-3 artifact | Present in current file? | Evidence |
|---|---|---|
| `fitter` — regression/Ridge/Lasso weights per regime | **NO** | No `sklearn.linear_model` imports. No function returns a coefficient vector. `compute_conditional_correlations` computes raw Pearson/Spearman correlations, not regression weights — these are descriptive dependency measures, not calibrated per-regime feature weights. |
| `router` — runtime regime→weights lookup | **NO** | No function takes a `current_regime` label and returns weights. There is no weight storage, no `DEFAULT_REGIME_WEIGHTS` constant, no dispatch logic. |

**Overlap: zero.** The existing file produces a statistical characterization of regime-dependent dependence structure; CC-3 will produce calibrated regression weights and a runtime selector. Both happen to live under the same module name because both are "regime-conditional" analytics, but the artifacts are semantically disjoint.

## Final classification: **A (diagnostic only)**

Every public and private function returns descriptive statistics (correlations, CIs, p-values, lead-lag scans) packaged for human inspection via the companion notebook and tests. The `regime_switching_confirmed` boolean is a hypothesis-validation flag for DEC-009, not a production gate. No code unit computes or exports weights, coefficients, or runtime routing parameters — so there is no overlap with the CC-3 fitter/router deliverables.

## Recommendation

**Safe to restructure with zero code rewrite:**

```
divergence/
└── regime_conditional/
    ├── __init__.py                 ← re-export diagnostic + fitter + router (future)
    ├── diagnostic.py               ← current regime_conditional.py, moved verbatim
    ├── fitter.py                   ← NEW in CC-3 (weights per regime, OLS/Ridge)
    └── router.py                   ← NEW in CC-3 (runtime regime → weights lookup)
```

Mechanics:
1. `git mv src/macro_context_reader/divergence/regime_conditional.py src/macro_context_reader/divergence/regime_conditional/diagnostic.py`
2. Create `regime_conditional/__init__.py` re-exporting the existing public surface (`load_aligned_data`, `compute_conditional_correlations`, `compute_lead_lag`, `RegimeConditionalResults`, `RegimeCorrelation`) from `diagnostic`
3. Update test import: `from macro_context_reader.divergence.regime_conditional import ...` keeps working (package-level re-export) — no test file changes needed
4. Notebook import identical string — no change
5. CC-3 adds `fitter.py` + `router.py` without touching existing code

This preserves 12 passing tests, the DEC-009 validation artifact, and the PRD-200 AC-6 empirical evidence, while giving CC-3 its own clean namespace. No risk of deleting diagnostic work that supports existing PRD claims.

---

Inspection complete. regime_conditional.py classified as: **A**. See INSPECT_REGIME_CONDITIONAL.md.
