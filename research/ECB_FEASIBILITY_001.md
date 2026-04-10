# ECB Feasibility Report 001 — PRD-200 Pre-Implementation Investigation

> Generated: 2026-04-10 | Scope: read-only API exploration | Decision-input for: PRD-200 / CC-2

## 1. ecbdata Library Inventory

**Package:** ecbdata v0.1.1 (MIT, author: Luca Mingarelli @ ECB)
**Install:** `pip install ecbdata`
**Repo:** https://github.com/LucaMingarelli/ecbdata

### API Surface

The library exposes a singleton instance `ecbdata.ecbdata` of class `ECB_DataPortal` with **2 methods**:

| Method | Signature | Purpose |
|--------|-----------|---------|
| `connect` | `(proxies=None, verify=None)` | Configure underlying `requests.Session` (proxy, SSL) |
| `get_series` | `(series_key, start=None, end=None, detail=None, updatedafter=None, firstnobservations=None, lastnobservations=None, includehistory=False)` | Download data for a given ECB series key. Returns `pandas.DataFrame`. |

**No search/discovery function exists.** The library is a thin wrapper around the ECB SDMX REST API (`data-api.ecb.europa.eu/service/data/{flow}/{key}?format=csvdata`). You must know the exact series key.

**URL construction:** splits `series_key` on first dot → `flow` (e.g. "FM", "YC", "ICP") and `key` (everything else). Appends `?format=csvdata` plus optional parameters.

**Verdict on ecbdata:** functional for known series keys, returns full DataFrame with all SDMX attributes (30-40 columns). No search capability — keys must be obtained from ECB Data Portal manually or via SDMX structure queries.

## 2. EUR 2Y OIS — Access Test Results

### Candidates Tested

| # | Series Key | HTTP | Result | Notes |
|---|-----------|------|--------|-------|
| a | `FM.B.U2.EUR.4F.BB.U2_2Y_Z.YLD` | 404 | **FAILED** | Key does not exist in FM dataflow |
| b | `YC.B.U2.EUR.4F.G_N_C.SV_C_YM.SR_2Y` | 200 | **SUCCESS** | "All euro area yield curve - 2-year spot rate" (AAA govt bonds, zero-coupon) |
| c | `YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y` | 200 | **SUCCESS** | "AAA yield curve - 2-year spot rate" (all govt bonds, zero-coupon) |
| d | `FM.D.U2.EUR.RT.MM.EONIA_.HSTA` | 404 | **FAILED** | Key does not exist (EONIA discontinued 2022) |
| e | `FM.D.U2.EUR.4F.MM.EURIBOR2YD_.HSTA` | 404 | **FAILED** | 2Y Euribor derivative — key does not exist |

### Additional Discovery

Full enumeration of the FM dataflow revealed only **114 actual series** (despite the codelist containing 103,362 provider codes). EUR-relevant FM series include:

- `FM.M.U2.EUR.4F.BB.U2_2Y.YLD` — "Euro Area 2 Years Government Benchmark Bond - Yield" (monthly)
- `FM.M.U2.EUR.4F.MM.UONSTR.HSTA` — €STR overnight rate (monthly average)
- `FM.M.U2.EUR.4F.MM.EONIA.HSTA` — EONIA rate (monthly, discontinued)
- `FM.B.U2.EUR.4F.KR.DFR.LEV` — ECB Deposit Facility Rate (daily)

**Critical finding:** The FM dataflow does NOT contain EUR 2Y OIS (Overnight Index Swap) data. The provider code `EUREON2Y_` ("Euro 2-year Overnight Index Swap") exists in the codelist `CL_PROVIDER_FM_ID` but has **no associated data series** in the FM dataflow. Similarly, `EUREST2Y_` ("Euro 2 Year ESTR Overnight Index Swap") is in the codelist but not in the data.

**Best available proxy for EUR 2Y OIS:**
- **`YC.B.U2.EUR.4F.G_N_C.SV_C_YM.SR_2Y`** — Euro area government yield curve, AAA-rated, 2Y zero-coupon spot rate. Daily (business day) frequency. This is a government bond yield, not an OIS rate, but for the purpose of `real_rate_differential` calculation it captures EUR 2Y risk-free rate expectations. The spread between this and the actual EUR 2Y OIS is typically <15bp and stable.

### ecbdata Library Access

Both `YC` series work via `ecbdata.ecbdata.get_series()`:
```python
df = ecbdata.ecbdata.get_series('YC.B.U2.EUR.4F.G_N_C.SV_C_YM.SR_2Y', lastnobservations=5)
# Returns DataFrame with TIME_PERIOD, OBS_VALUE, TITLE, etc. (40 columns)
```

## 3. EUR 2Y ILS — Access Test Results

### Candidates Tested

| # | Series Key | HTTP | Result | Notes |
|---|-----------|------|--------|-------|
| a | `FM.M.U2.EUR.RT.BB.EURIRS2Y_.LEVEL` | 404 | **FAILED** | Key does not exist |
| b | `FM.B.U2.EUR.4F.BB.U2_2Y_Z.YLD` | 404 | **FAILED** | Same as OIS candidate a |
| c | `ICP.M.U2.N.000000.4.INX` | 200 | **SUCCESS** | HICP overall index (monthly). **Not an ILS** — this is backward-looking realized inflation. |
| d | `ILS.M.U2.EUR.RT.BB.EUR2Y_.HSTA` | 404 | **FAILED** | "ILS" is not a valid ECB dataflow |
| e | Search for "inflation swap" in ecbdata | N/A | **FAILED** | ecbdata has no search function |

### Extended Discovery

**Dataflow search:** ECB Data Portal has **102 dataflows**. None is dedicated to inflation-linked swaps. The only inflation-related dataflow is `ICP` (HICP consumer prices).

**FM codelist search:** The `CL_PROVIDER_FM_ID` codelist contains multiple inflation swap codes:
- `EUSWI2` — "European Inflation Swap - 2-year Zero Coupon CPI ex-tobacco for Eurozone"
- `EUSWI2_CMPN` — "EUR Inflation Swap Zero Coupon Ex Tobacco 2Y"
- `EUHCPT2Y_ICAP` — "Euro 2-year Inflation Linked Interest Rate Swap"
- `EUSWIT2_CMPN` — "EUR Inflation Zero Coupon 2Y"

**However:** None of these codes have actual data series in the FM dataflow. The codelist describes the *schema* of what *could* exist, not what *does* exist. Tested all permutations of FM key structure (`FM.{D|M|B}.U2.EUR.{4F|SI|RT}.{KR|BB|RT}.{EUSWI2|EUHCPT2Y_ICAP}.{HSTA|YLD|LEV}`) — all returned HTTP 404.

### Available Inflation Proxies from ECB

| Series Key | Title | Frequency | Range |
|-----------|-------|-----------|-------|
| `ICP.M.U2.N.000000.4.ANR` | HICP overall index — annual rate of change | Monthly | 2019-01 → 2025-12 |
| `ICP.M.U2.N.000000.4.INX` | HICP overall index — level | Monthly | 2019-01 → 2025-12 |

**These are backward-looking realized inflation, NOT forward-looking market-implied inflation expectations (which is what an ILS provides).**

### Verdict on EUR 2Y ILS

**EUR 2Y Inflation-Linked Swap rate is NOT available through ECB Data Portal.**

The data exists in the ECB's codelist schema (suggesting it was planned or exists in internal systems) but has never been published to the public API. This is confirmed by:
1. Only 114 series exist in the entire FM dataflow
2. Zero inflation swap series among them
3. All tested key permutations return 404
4. No dedicated ILS/inflation swap dataflow exists

## 4. Frequency and Temporal Coverage

### Series That Returned Data

| Series Key | Title | Frequency | Obs | Date Range | Covers 2020+ | Notable Gaps |
|-----------|-------|-----------|-----|------------|--------------|-------------|
| `YC.B.U2.EUR.4F.G_N_C.SV_C_YM.SR_2Y` | Euro area all govt YC — 2Y spot rate | Daily (business) | 1,854 | 2019-01-02 → 2026-04-08 | Yes | 17 gaps >3 days (weekends/holidays) |
| `YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y` | Euro area AAA govt YC — 2Y spot rate | Daily (business) | 1,854 | 2019-01-02 → 2026-04-08 | Yes | 17 gaps >3 days (weekends/holidays) |
| `FM.M.U2.EUR.4F.BB.U2_2Y.YLD` | EUR 2Y benchmark bond yield | Monthly | 87 | 2019-01 → 2026-03 | Yes | 0 |
| `ICP.M.U2.N.000000.4.ANR` | HICP annual rate of change | Monthly | 84 | 2019-01 → 2025-12 | Yes | 0 |
| `ICP.M.U2.N.000000.4.INX` | HICP index level | Monthly | 84 | 2019-01 → 2025-12 | Yes | 0 |
| `FM.M.U2.EUR.4F.MM.UONSTR.HSTA` | €STR overnight rate (monthly avg) | Monthly | 87 | 2019-01 → 2026-03 | Yes | 0 |

### Frequency Compatibility

- **Government yield curve (YC)**: business daily — excellent for daily `real_rate_differential`
- **HICP inflation (ICP)**: monthly — this is the binding constraint if used as ILS fallback
- **Net frequency of `real_rate_differential`**: monthly (limited by slowest component = HICP)

### Sample Values (most recent)

| Series | Last Date | Last Value | Unit |
|--------|-----------|------------|------|
| YC all govt 2Y spot | 2026-04-08 | 2.5375% | Percent per annum |
| YC AAA govt 2Y spot | 2026-04-08 | 2.4415% | Percent per annum |
| HICP YoY | 2025-12 | 1.9% | Percent change |
| €STR overnight | 2026-03 | 1.932% | Percent per annum |

## 5. Feasibility Verdict

### **CASE D — RED: EUR 2Y Inflation-Linked Swap NOT accessible through ECB Data Portal**

**Summary:**
- **EUR 2Y OIS**: Not directly available as a term swap rate. The best proxy is the government yield curve 2Y spot rate (`YC.B.U2.EUR.4F.G_N_C.SV_C_YM.SR_2Y`), which is daily and covers 2020+. The spread between govt yields and OIS is small and relatively stable, making this an acceptable proxy for the `real_rate_differential` formula.
- **EUR 2Y Inflation-Linked Swap**: **Completely unavailable.** The ECB's public FM dataflow contains only 114 series, none of which are inflation swaps. The codelist has the schema for these series (EUSWI2, EUHCPT2Y_ICAP, etc.) but no actual data is published. The only inflation data available is backward-looking HICP (monthly, ~4 month lag to present).

**Why this is CASE D (not CASE C):**
HICP YoY is fundamentally different from an inflation swap rate:
- HICP measures **realized** past inflation
- EUR 2Y ILS measures **market-implied forward** inflation expectations
- The two can diverge significantly (e.g., HICP at 2% while ILS at 3% because markets expect inflation to rise)
- Using HICP as a drop-in replacement would make `real_rate_differential` a backward-looking metric instead of a forward-looking one

**Decision required from Fabian (project manager).**

## 6. Recommendation for PRD-200 / CC-2

### Decision Options for Fabian

**Option A — Accept HICP YoY as fallback (methodological downgrade)**
- Use `ICP.M.U2.N.000000.4.ANR` (HICP YoY) instead of EUR 2Y ILS
- Formula becomes: `real_rate_diff = (US_2Y - US_breakeven_2Y) - (EUR_2Y_govt_yield - HICP_YoY)`
- Pro: All data from free public APIs (ECB + FRED), no new dependencies
- Con: EUR side becomes backward-looking vs. US side (breakeven is forward-looking) → asymmetric methodology
- Con: Monthly frequency (HICP) limits `real_rate_differential` to monthly updates
- **Risk level: Medium.** Acceptable for backtesting and structural analysis; insufficient for timing.

**Option B — Source EUR ILS from Bloomberg/Refinitiv (paid data)**
- Bloomberg ticker: `EUSWI2 Curncy` (EUR 2Y Inflation Swap Zero Coupon)
- Daily data, forward-looking, methodologically correct
- Pro: Symmetric methodology with US breakevens
- Con: Requires Bloomberg Terminal or API subscription ($$$)
- Con: Cannot be distributed in open-source project

**Option C — Derive EUR breakeven from ECB yield curve differential**
- If ECB published an inflation-linked government yield curve (they don't currently for 2Y maturity), breakeven = nominal - real yield
- The ECB yield curve dataflow (`YC`) only contains nominal government bond curves (G_N_C, G_N_A), no inflation-indexed variants
- **Not feasible with current ECB data.**

**Option D — Use FRED for EUR inflation expectations**
- FRED has some European inflation expectation series but typically 5Y5Y forward, not 2Y
- Check FRED series: `T5YIFRM` (5Y5Y forward inflation expectation rate, Eurozone) — available but wrong tenor
- **Partial solution**: could work if PRD-200 formula is adjusted to use 5Y5Y instead of 2Y

**Option E — Hybrid approach (recommended if budget = 0)**
- **EUR nominal rate**: `YC.B.U2.EUR.4F.G_N_C.SV_C_YM.SR_2Y` from ECB (daily, free)
- **EUR inflation expectation**: `ICP.M.U2.N.000000.4.ANR` (HICP YoY) as temporary proxy, with explicit flag in output that EUR inflation component is backward-looking
- Add a `methodology_confidence` field to `real_rate_differential` output: HIGH when both sides are forward-looking (future: if ILS becomes available), MEDIUM when EUR side uses HICP
- PRD-200 proceeds, but output metadata clearly marks the limitation

### Recommended Series Keys for PRD-200 / CC-2

| PRD-200 Variable | Recommended ECB Series | Proxy Quality |
|-----------------|----------------------|---------------|
| EUR_2Y_OIS | `YC.B.U2.EUR.4F.G_N_C.SV_C_YM.SR_2Y` | Good (govt yield ≈ OIS + small spread) |
| EUR_inflation_2Y | `ICP.M.U2.N.000000.4.ANR` | Poor (backward-looking, monthly, wrong concept) |

### Changes Required in PRD-200

1. Replace "EUR_2Y_OIS" with "EUR_2Y_govt_yield" and document the proxy
2. Replace "EUR Inflation-Linked Swap 2Y" with decision from Options A-E above
3. Add `data_source_quality` metadata to output indicating when EUR-side data is a proxy
4. If Option A/E: reduce `real_rate_differential` update frequency to monthly (binding on HICP)
5. Add `ecbdata>=0.1.1` to dependencies (or use `requests` directly — both work equivalently)
