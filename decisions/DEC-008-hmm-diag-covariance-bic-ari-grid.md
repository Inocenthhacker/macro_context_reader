# DEC-008: HMM Diag Covariance + BIC+ARI Grid Selection

**Status:** Adopted
**Date:** 2026-04-12
**PRD:** PRD-050 CC-1b
**Commits:** c778a5e, ca1651f

## Context

PRD-050 CC-1 used `covariance_type="full"` with 6 features. For n_states=6, this
means 6 × 6×7/2 = 126 covariance parameters on ~300 monthly observations — high
overfitting risk. Additionally, model selection used only BIC without stability
validation, leading to seed-dependent results.

## Options Considered

1. **Full covariance + BIC only** — original CC-1
   - Pro: Captures cross-feature correlations
   - Con: 126 params / 300 obs = underdetermined; seed-dependent selections

2. **Diag covariance + BIC only**
   - Pro: 36 params — much more parsimonious
   - Con: Ignores cross-feature correlations; no stability guarantee

3. **Diag covariance + BIC + ARI stability** (chosen)
   - Pro: Parsimonious parameters; stability validated across seeds
   - Con: Slightly more computation (10 seeds × 7 grid = 70 fits)

4. **Tied covariance**
   - Pro: Single shared covariance — fewest parameters
   - Con: Forces same spread for all states — unrealistic for macro regimes

## Decision

- `covariance_type="diag"` (default parameter)
- Extended grid: `[2, 3, 4, 5, 6, 7, 8]`
- Dual criterion:
  1. For each n_states, fit 10 seeds {0..9}
  2. Compute BIC mean/std, AIC mean/std, pairwise ARI mean/std
  3. Filter: candidates with ARI mean ≥ 0.70 (Steinley 2004 threshold)
  4. Among stable candidates: select minimum BIC
  5. Fallback: if no candidate passes ARI, select max ARI with warning

## Rationale

- **Diag over full:** With 6 features and ~300 observations, diag (36 params) is
  adequately parameterized while full (126 params) is borderline. Cross-feature
  correlations are already captured by the standardized feature construction.

- **ARI threshold 0.70:** Steinley (2004) established 0.70 as a practical threshold
  for "good" cluster recovery. Below this, different random seeds produce substantially
  different state assignments — the model is not reliable.

- **10 seeds:** Sufficient to estimate pairwise ARI (45 pairs). Computation is
  ~70 fits × <0.5s each = ~35s total — acceptable.

## Consequences

- `HMMFitDiagnostics` schema extended with: grid, bic/aic/ari mean+std, selection_reason
- Notebook cell 3 shows triple BIC/AIC/ARI errorbar plot
- If ARI fallback triggers, a Python warning is emitted — user should investigate
  feature selection or data quality

## References

- Steinley (2004), "Properties of the Hubert-Arabie Adjusted Rand Index",
  Psychological Methods — ARI threshold justification
- Schwarz (1978), "Estimating the Dimension of a Model" — BIC criterion
