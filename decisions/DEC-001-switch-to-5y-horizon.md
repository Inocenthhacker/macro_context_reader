# DEC-001: Switch from 2Y to 5Y horizon for real rate differential

**Status:** Adopted
**Date:** 2026-04-10
**Layer/PRD:** PRD-200, PRD-201, PRD-202, PRD-203, PRD-204, PRD-205, PRD-206
**Decision type:** Methodological — fundamental project pivot
**Discovered during:** PRD-200/CC-2 implementation

## Context

PRD-200 originally planned to use a 2-year horizon for the real rate
differential signal: `real_rate_diff = US_2Y_real - EUR_2Y_real`.

During CC-2 implementation, Claude Code discovered that FRED does NOT
publish DFII2 (US 2Y TIPS real yield). The US Treasury has never issued
TIPS at 2-year maturities — the shortest available is DFII5 (5Y).

This forced a methodological reconsideration: how do we measure US real
rates at short horizons?

## Options considered

### Option 1: Switch entire project to 5Y horizon
- US side: DGS5 - DFII5 (both official, both forward-looking, daily)
- EUR side: ECB 5Y govt yield - ECB SPF 5Y ahead HICP forecast
- Symmetric methodology, both sides forward-looking, all data official and free

### Option 2: Keep 2Y horizon with proxy construction
- 2a: DGS2 - interpolated breakeven from 5Y/10Y → Fed officially warns against this
- 2b: DGS2 - inflation swap 2Y → not on FRED, Bloomberg only (cost incompatible)
- 2c: DGS2 - Cleveland Fed 2Y inflation expectations → workable but mixes nominal 2Y with quarterly inflation forecast

### Option 3: Accept hybrid (2Y nominal + 5Y breakeven)
- Methodologically incoherent: mixes time horizons
- Federal Reserve explicitly warns: "breakeven rates should not be
  interpreted as estimates of inflation expectations" due to risk premia
  and liquidity effects

## Decision

**Adopted Option 1: switch entire project to 5Y horizon for the structural
real rate differential signal.**

Add a separate, parallel tactical signal layer (PRD-202) using:
- Fed Funds Futures (1-12 months ahead) for policy expectations
- Cleveland Fed EXPINF1YR for short-term US inflation expectations

The structural (5Y) and tactical (short) signals are combined via
empirically calibrated weights (OLS regression on historical EUR/USD),
not hardcoded values. Calibration happens in PRD-202 implementation.

## Rationale

1. **Data quality.** DFII5 is an official, forward-looking, daily
   published series from the Federal Reserve. No proxies, no construction,
   no liquidity premium guesswork.

2. **Methodological symmetry.** Both US and EUR sides use identical
   formulation: nominal 5Y minus forward-looking 5Y inflation expectation.
   This eliminates "apples vs oranges" comparison errors.

3. **Academic consensus.** The literature on real rate differentials and
   FX (Engel 2016, Macrosynergy 2024, BBVA 2025) predominantly uses 5Y or
   10Y horizons, not 2Y. The 2Y assumption was a personal habit, not
   evidence-based.

4. **Federal Reserve guidance.** The Fed itself publishes a warning on
   their TIPS yield curve page that breakevens should not be naively
   interpreted as inflation expectations due to risk premia and liquidity
   effects. Using 5Y avoids the worst of these distortions.

5. **ECB SPF compatibility.** ECB SPF publishes explicit 5-year-ahead
   HICP forecasts. This is the same horizon ECB uses internally for
   anchoring assessments (ECB Economic Bulletin 8/2025).

6. **Multi-horizon coverage.** The new tactical layer (PRD-202) provides
   short-horizon sensitivity that 2Y would have offered, but with better
   methodological grounding (Fed Funds Futures are designed exactly for
   short-horizon policy expectations).

## Consequences

### Code changes
- us_rates.py: replace DGS2 → DGS5, T5YIE → DFII5
- eu_rates.py (CC-3): use ECB 5Y govt yield instead of 2Y
- ecb_spf.py (CC-5): use SPF 5Y ahead HICP forecast (FCT_HORIZON=P60M)
- schemas.py: rename us_2y_nominal → us_5y_nominal, etc.
- real_rate_diff.py (CC-6): formula updates accordingly
- All test fixtures updated for new column names

### Documentation changes
- PRD-200.md: all "2Y" references replaced with "5Y"
- INFLATION_EXPECTATIONS_METHODS.md: SPF method specifies 5Y horizon
- ROADMAP.md: D-PRD200-2 decision updated retroactively

### New work
- PRD-202 created as Draft for tactical short-horizon signal layer
- Combined signal aggregation deferred to a future PRD with empirical
  weight calibration via OLS

### What we lose
- Slightly slower regime change detection (5Y vs 2Y reaction time)
- Compensated by tactical layer in PRD-202

### What we gain
- Methodologically clean, peer-reviewed approach
- Zero proxy construction, zero hardcoded assumptions
- Symmetric US-EU methodology
- Better alignment with academic literature

## References

- Federal Reserve Board, TIPS Yield Curve and Inflation Compensation page:
  https://www.federalreserve.gov/data/yield-curve-tables/feds200805_1.html
- FRED DFII5 series documentation:
  https://fred.stlouisfed.org/series/DFII5
- ECB Economic Bulletin Issue 8/2025 — SPF anchoring analysis
- Burban & Guilloux-Nefussi (Banque de France 2025) — Anchoring of
  inflation expectations in the euro area
- Engel (2016) — Exchange Rates, Interest Rates, and the Risk Premium
  https://www.aeaweb.org/articles?id=10.1257/aer.20121365
- Piazzesi & Swanson (NBER 2008) — Futures prices as risk-adjusted
  forecasts of monetary policy (foundational for tactical layer in PRD-202)
