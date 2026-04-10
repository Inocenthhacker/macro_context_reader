# DEC-002: Dual EUR Yield Curves (AAA + All Issuers) with Credit Stress Spread

**Status:** Adopted
**Date:** 2026-04-10
**Layer/PRD:** PRD-200, future PRD-300 (Divergence)
**Decision type:** Methodological — multi-source data design
**Discovered during:** PRD-200/CC-3 planning

## Context

ECB Data Portal publishes two parallel versions of the euro area
government bond yield curve at every maturity:

1. **AAA only** (`G_N_C`): includes only AAA-rated euro area sovereigns
   (Germany, Netherlands, Luxembourg). Closest analog to "risk-free
   benchmark", methodologically symmetric with US Treasury yields.

2. **All issuers** (`G_N_A`): includes all euro area sovereigns,
   reflecting average yields across the bloc. Includes credit risk
   premium from peripheral countries (Italy, Spain, Greece).

Both series use identical methodology (Svensson model, daily business
days, from 2004-09-06 to present, fixed coupon and zero coupon bonds
only — explicitly excludes inflation-linked bonds).

## Options considered

### Option 1: AAA only
- Pro: methodological symmetry with US Treasury (both top-rated)
- Pro: closest to "risk-free" benchmark concept
- Con: ignores broader euro area market dynamics

### Option 2: All issuers only
- Pro: reflects realistic market average
- Con: contaminated with credit risk premium varying over time

### Option 3: AAA principal, All as fallback only
- Pro: ensures availability
- Con: ECB Yield Curve has no real availability issues; fallback never triggered
- Con: wastes opportunity to analyze the spread

### Option 4 (ADOPTED): Both series in parallel + computed credit stress spread
- Pro: AAA used as principal input for real_rate_diff (methodological purity)
- Pro: All preserved as independent signal
- Pro: spread = (All - AAA) computed automatically as third signal
- Pro: spread itself is an independent regime indicator (financial stress in eurozone)
- Pro: zero additional cost — same data source, same fetch operation

## Decision

**Adopt Option 4: store both yield curves in eu_rates.parquet plus
the computed credit stress spread.**

Schema:
- `eu_5y_nominal_aaa` (principal, used in real_rate_diff)
- `eu_5y_nominal_all` (parallel, available for cross-validation)
- `eu_credit_stress_5y` (computed: all - aaa, in basis points or percent)

## Rationale

1. **Symmetry preservation.** AAA matches US Treasury methodology, so
   real_rate_diff uses AAA for its 5Y EUR nominal input.

2. **Free additional signal.** The spread between All and AAA is a
   well-known indicator of euro area financial stress. Historical
   examples:
   - 2010-2012 sovereign debt crisis: spread expanded from ~10bp to ~200bp
   - March 2020 COVID panic: sharp spike
   - Summer 2022 energy crisis: notable widening
   - 2024-2025 political tensions: localized expansions

3. **No marginal cost.** Both series come from the same ECB Yield Curve
   dataflow, same API endpoint, same frequency. Fetching both is one
   additional API call per dataset (total: 2 calls instead of 1).

4. **Future-proof for PRD-300.** The credit stress signal will be
   useful as a regime filter in PRD-300 (Divergence Signal). Storing
   it now avoids refactoring later.

## Consequences

### Code changes
- `eu_rates.py`: fetches both series, computes spread, stores all 3 columns
- `schemas.py`: EURRatesRow updated with three fields
- `eu_rates.parquet`: contains 4 columns (date + 3 series)

### Downstream impact
- PRD-200/CC-6 (real_rate_diff): uses `eu_5y_nominal_aaa` as input
- PRD-300 (future): can use `eu_credit_stress_5y` as regime indicator
- PRD-204 (future composite): may include credit stress as additional feature

### What we gain
- Two yield series + one derived signal from a single fetch operation
- Methodologically pure principal signal (AAA)
- Independent stress signal (spread) for regime detection

### What we lose
- Negligible: ~5KB additional storage per parquet

## References

- ECB Yield Curve documentation:
  https://www.ecb.europa.eu/stats/financial_markets_and_interest_rates/euro_area_yield_curves/html/index.en.html
- ECB Data Portal yield curve methodology:
  https://data.ecb.europa.eu/methodology/yield-curves
- AAA series: YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_5Y (G_N_A = AAA rated)
- All issuers series: YC.B.U2.EUR.4F.G_N_C.SV_C_YM.SR_5Y (G_N_C = all ratings)
- Note: the SDMX codes are counterintuitive — G_N_A is AAA, G_N_C is All.
  Verified via ECB TITLE_COMPL metadata on 2026-04-10.
- Svensson methodology: Svensson, L. E. O. (1994), "Estimating and
  Interpreting Forward Interest Rates: Sweden 1992-1994", NBER WP 4871
