# DEC-007: Full-History Scaler Scope

**Status:** Adopted
**Date:** 2026-04-12
**PRD:** PRD-050 CC-1b
**Commits:** c778a5e, ca1651f

## Context

PRD-050 CC-1 initially implemented `StandardScaler.fit()` on a pre-COVID window
(2000-01-01 to 2019-12-31), then `.transform()` on the full history including
post-COVID data.

Observed problem: post-transform standard deviations were 1.42-2.63 for features
in the post-2020 period — far from the expected ~1.0 for standardized data. This
caused HMM with `covariance_type="full"` to overfit on the inflated variance of
`core_pce_yoy`, and BIC selected `n_states=6` (grid extremum).

## Options Considered

1. **Pre-COVID scaler fit (2000-2019)** — original implementation
   - Rationale: "COVID is an outlier, normalize against pre-COVID baseline"
   - Problem: Post-COVID features are systematically mis-scaled; HMM overfits

2. **Full-history scaler fit** (chosen)
   - Rationale: Post-COVID is a regime, not an outlier. The HMM should discover
     it as a distinct state, not be biased by rescaling artifacts.

3. **Rolling scaler with expanding window**
   - Rationale: Adapts gradually
   - Problem: Introduces look-forward bias at training boundaries; unnecessary complexity

## Decision

`StandardScaler.fit()` on `features.dropna()` — the full available history.
Post-COVID regime is part of the population the HMM needs to cluster.

## Rationale

The purpose of standardization here is to ensure features are on comparable scales
for HMM fitting — NOT to measure deviations from a "normal" baseline. If the scaler
is fit on pre-COVID only, post-COVID observations appear as systematic outliers in
all features simultaneously, which distorts the covariance structure the HMM learns.

After this change, BIC selected `n_states=3` (no longer an extremum), and the
discovered states aligned with known macro episodes (GFC, COVID → same state;
2022-2023 hiking → distinct inflation state).

## Consequences

- `indicators.py`: removed `SCALER_FIT_START`/`SCALER_FIT_END` constants
- HMM now treats all historical regimes symmetrically
- Regime labels may shift if new extreme data (e.g., a future crisis) is added —
  acceptable since model is refit periodically

## References

- Empirical observation in session 2026-04-12: pre-COVID scaler → n_states=6 (extremum),
  full-history scaler → n_states=3 (validated)
