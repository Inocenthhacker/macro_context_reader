# DEC-004: EU Inflation Expectations Source — ECB SPF Longer-Term HICP

**Status:** Adopted
**Date:** 2026-04-11
**Layer/PRD:** PRD-200 (CC-5), future PRD-204 (Composite Signal)
**Decision type:** Data source selection
**Discovered during:** PRD-200/CC-5 PHASE 1 discovery

## Context

PRD-200 requires EUR 5Y inflation expectations to compute the EUR side
of the real rate differential: `eu_5y_real = eu_5y_nominal_aaa - eu_inflation_5y`.

PHASE 1 discovery (2026-04-10) systematically searched all ECB Data Portal
dataflows (FM, YC, ILM, IRS, SPF — 102 total dataflows) for available
inflation expectations series.

## Options evaluated

### Option A: Inflation-Linked Swap (ILS) rates
- 5Y spot ILS or 5Y5Y forward ILS
- **Result: NOT AVAILABLE on ECB free Data Portal.**
- FM dataflow has only 114 series total: ECB key rates, EURIBOR, govt bond
  yields, equity indices, oil. Zero inflation swap rates.
- ILS data is Bloomberg/Reuters proprietary — cost incompatible with project
  constraint of free data sources only.

### Option B (ADOPTED): ECB SPF longer-term HICP forecast
- Serie: `SPF.Q.U2.HICP.POINT.LT.Q.AVG`
- TITLE_COMPL: "Euro area (changing composition) - Harmonised ICP - Point
  forecast - Longer term (5 calendar years ahead in SPF Q3 and Q4 rounds
  and 4 calendar years ahead in SPF Q1 and Q2 rounds) - Quarterly survey"
- Frequency: Quarterly (Q1-Q4)
- Date range: 1999-Q1 → present (103+ observations)
- Value range: [1.648, 2.175] — stable around ECB 2% target
- Free, official, academically validated.

### Option C: YC inflation-indexed yield curves
- **Result: NOT AVAILABLE.**
- ECB Yield Curve (YC dataflow) explicitly excludes inflation-linked bonds
  from the Svensson model estimation. Only nominal curves exist (G_N_A, G_N_C).

## Decision

**Adopt Option B: ECB SPF longer-term HICP forecast as the EUR inflation
expectations source for real_rate_differential.**

Serie: `SPF.Q.U2.HICP.POINT.LT.Q.AVG`

## Rationale

1. **Only viable free source.** ILS and inflation-indexed bond curves are
   simply not available on the ECB free Data Portal. SPF is the sole
   official ECB source for forward-looking inflation expectations that is
   freely accessible.

2. **Academic validation.** ECB Economic Bulletin Issue 8/2025 and
   Burban & Guilloux-Nefussi (Banque de France 2025) both use SPF as the
   primary anchor for assessing inflation expectations anchoring in the
   euro area. This is the same series the ECB itself monitors internally.

3. **Long history.** 103+ quarterly observations from 1999 — sufficient
   for backtesting real_rate_differential against EUR/USD over multiple
   economic cycles.

4. **Methodological coherence.** SPF is a forward-looking expectations
   measure (not backward-looking realized inflation), matching the
   conceptual role in the real rate formula.

## Known limitations

### 1. Quarterly frequency (not daily)
SPF is published once per quarter. US DFII5 is daily. This creates an
asymmetry in the real_rate_differential:
- US side: daily (market-observed TIPS yield)
- EUR side: quarterly (survey-based, forward-filled to daily in CC-6)

**Mitigation:** Forward-fill with ~95 day limit in CC-6. The SPF value
changes slowly anyway (range [1.65, 2.18] over 25 years), so the stale
data between publications is a minor concern.

### 2. Variable horizon (4Y vs 5Y)
The "longer-term" horizon is not constant:
- Q3 and Q4 rounds: 5 calendar years ahead
- Q1 and Q2 rounds: 4 calendar years ahead

**Impact estimate:** 5-15bp difference in normal regimes, up to 30bp in
stress regimes. Negligible relative to the real_rate_differential signal
magnitude (typically 100-300bp).

### 3. Survey-based, not market-implied
SPF reflects forecaster consensus, not market-implied expectations. It is
inherently slow-moving and less reactive to shocks than a market price
like ILS would be.

**Implication for CC-6:** The composite real_rate_diff will be "smoother"
on the EUR side than on the US side. This methodological asymmetry must
be remembered during backtesting — a sudden move in real_rate_diff is
more likely driven by US DFII5 changes than by EUR SPF changes.

## Consequences

### Code changes
- `eu_inflation.py`: fetches SPF series, validates, saves quarterly Parquet
- `schemas.py`: adds `EUInflationRow` with NaN rejection
- CC-6 (future): forward-fills quarterly to daily with ~95 day limit

### What we gain
- Official, free, academically validated inflation expectations
- 25+ years of quarterly data for backtesting
- Same source the ECB itself uses for anchoring assessments

### What we lose
- Daily granularity (compensated by forward-fill)
- Market-reactivity (compensated by US side being market-observed)

## References

- ECB SPF documentation: https://www.ecb.europa.eu/stats/ecb_surveys/survey_of_professional_forecasters/html/index.en.html
- FRED DFII5 (US side comparison): https://fred.stlouisfed.org/series/DFII5
- ECB Economic Bulletin Issue 8/2025 — SPF anchoring analysis
- Burban & Guilloux-Nefussi (Banque de France 2025) — Anchoring of
  inflation expectations in the euro area
- ECB Data Portal SPF series: SPF.Q.U2.HICP.POINT.LT.Q.AVG
