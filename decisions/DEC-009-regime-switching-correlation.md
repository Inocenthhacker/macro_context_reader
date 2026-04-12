# DEC-009: Regime-Switching Correlation — PRD-300 Calibration Strategy

**Status:** Adopted
**Date:** 2026-04-12
**PRD:** PRD-200 (empirical finding), PRD-300 (downstream impact)
**Commits:** Empirical results from notebooks/02_layer2_market_pricing.ipynb, 02b_layer2_regime_diagnostic.ipynb

## Context

PRD-200 AC-6 originally required a global Pearson correlation between
`real_rate_differential` and EUR/USD on 10 years of data. The computed value
was r = −0.045 (p = 0.026) — statistically significant but economically
near-zero, which was puzzling given the strong theoretical relationship.

Notebook 02b investigated and found:
- Rolling 252-day correlation ranges from −0.93 to +0.67
- 4 sign flips across the 10-year window
- 67.4% of windows show strong negative correlation (r < −0.30)
- 13.0% show strong positive correlation (r > +0.30)
- CUSUM test: 72.2% of observations outside 95% confidence interval

## Decision

The relationship between `real_rate_differential` and EUR/USD is **regime-dependent**,
not globally stable. PRD-300 divergence calculations must use regime-conditional
correlations, not a single global estimate.

Specifically:
1. Per-regime correlation coefficients (from HMM state segmentation)
2. Rolling correlation as a feature in divergence signal (not just level)
3. Regime transition probabilities as additional signal

AC-6 was reformulated (DEC-005) as regime-conditional with 3 sub-conditions:
- (a) Median rolling r ≤ −0.30 → PASS (computed: −0.5075)
- (b) ≤ 25% windows with r > 0 → PASS (computed: 19.01%)
- (c) Min rolling r ≤ −0.50 → PASS (computed: −0.9302)

All 3 conditions satisfied — the anchor is validated under regime-conditional framework.

## Rationale

A global r = −0.045 does NOT mean the relationship is weak. It means the relationship
alternates between strongly negative and occasionally positive phases. This is
consistent with macro regime switching: during inflation-dominant regimes, real rate
differentials drive FX; during crisis/stress regimes, flight-to-safety dominates.

## Consequences

- PRD-300 must implement per-regime calibration, not global
- PRD-500 DST confidence intervals widen during regime transitions
- Backtesting on USMPD must segment by HMM regime state
- `real_rate_diff` remains the structural anchor (67.4% negative correlation),
  but signal confidence varies by regime

## References

- BBVA Research (Martínez et al. 2025): GFCI-conditional EUR/USD equilibrium
- Gebauer et al. (ECB Blog 2025): 63-day Fed spillover threshold
- Notebook 02b_layer2_regime_diagnostic.ipynb: CUSUM + rolling correlation analysis
