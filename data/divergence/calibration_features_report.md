# CC-1.5.5 — Master Alignment Table — Data Quality Report

Generated: 2026-04-21T17:06:31.152878
Output: `data/divergence/calibration_features.parquet`

## 1. Shape & Schema
- Rows: 42
- Columns: 17
- Date range: 2021-01-27 to 2026-03-18
- Index: `meeting_date` (DatetimeIndex, sorted ascending)

Column list:
  - `statement_ensemble_net` — dtype `float64`
  - `statement_fomc_roberta_net` — dtype `float64`
  - `statement_llama_deepinfra_net` — dtype `float64`
  - `minutes_lag_ensemble_net` — dtype `float64`
  - `minutes_lag_fomc_roberta_net` — dtype `float64`
  - `minutes_lag_llama_deepinfra_net` — dtype `float64`
  - `minutes_lag_source_date` — dtype `datetime64[ns]`
  - `fedwatch_implied_change_bps` — dtype `float64`
  - `fedwatch_actual_change_bps` — dtype `float64`
  - `fedwatch_surprise_bps` — dtype `float64`
  - `fedwatch_surprise_zscore` — dtype `float64`
  - `real_rate_diff_5y` — dtype `float64`
  - `real_rate_diff_source_date` — dtype `datetime64[ns]`
  - `cleveland_national_score` — dtype `float64`
  - `cleveland_consensus_score` — dtype `float64`
  - `cleveland_divergence` — dtype `float64`
  - `cleveland_source_date` — dtype `datetime64[ns]`

## 2. Minutes Aggregation — HTML vs PDF
- Correlation (HTML, PDF) on ensemble_net: **0.7332**
- Threshold: 0.85
- Strategy selected: **html_fallback**
- Meetings with both formats: 42
- Meetings HTML-only: 0
- Meetings PDF-only: 0
- |HTML − PDF| mean: 0.0968
- |HTML − PDF| max:  0.2350

> **Note:** correlation below threshold — HTML-only fallback used.
> PDF scores diverge enough from HTML that averaging would dilute signal.
> Likely root cause: PDF extraction introduces OCR/layout noise (boilerplate,
> line-break artifacts) vs cleaner HTML parse. HTML is the canonical source.

## 3. Coverage per Column (non-null counts)

| Column | Non-null | Null |
|---|---|---|
| `statement_ensemble_net` | 42 | 0 |
| `statement_fomc_roberta_net` | 42 | 0 |
| `statement_llama_deepinfra_net` | 42 | 0 |
| `minutes_lag_ensemble_net` | 41 | 1 |
| `minutes_lag_fomc_roberta_net` | 41 | 1 |
| `minutes_lag_llama_deepinfra_net` | 41 | 1 |
| `minutes_lag_source_date` | 41 | 1 |
| `fedwatch_implied_change_bps` | 42 | 0 |
| `fedwatch_actual_change_bps` | 42 | 0 |
| `fedwatch_surprise_bps` | 42 | 0 |
| `fedwatch_surprise_zscore` | 42 | 0 |
| `real_rate_diff_5y` | 42 | 0 |
| `real_rate_diff_source_date` | 42 | 0 |
| `cleveland_national_score` | 42 | 0 |
| `cleveland_consensus_score` | 42 | 0 |
| `cleveland_divergence` | 42 | 0 |
| `cleveland_source_date` | 42 | 0 |

## 4. Look-ahead Bias Verification

For each source-date audit column, we verify source_date < FOMC date T.

- `minutes_lag_source_date`: n=41, gap days min/mean/max = 41/45.8/56
  - OK: strictly positive gap (zero look-ahead bias verified)
- `real_rate_diff_source_date`: n=42, gap days min/mean/max = 1/1.0/2
  - OK: strictly positive gap (zero look-ahead bias verified)
- `cleveland_source_date`: n=42, gap days min/mean/max = 1/29.3/137
  - OK: strictly positive gap (zero look-ahead bias verified)

## 5. Summary Statistics — Numeric Columns

| Column | mean | std | min | max |
|---|---|---|---|---|
| `statement_ensemble_net` | 0.0707 | 0.233 | -0.5 | 0.375 |
| `statement_fomc_roberta_net` | 0.0707 | 0.233 | -0.5 | 0.375 |
| `statement_llama_deepinfra_net` | 0.0435 | 0.1942 | -0.3889 | 0.3529 |
| `minutes_lag_ensemble_net` | 0.1149 | 0.1185 | -0.1544 | 0.3529 |
| `minutes_lag_fomc_roberta_net` | 0.1149 | 0.1185 | -0.1544 | 0.3529 |
| `minutes_lag_llama_deepinfra_net` | 0.0421 | 0.0964 | -0.1201 | 0.2743 |
| `fedwatch_implied_change_bps` | 8.595 | 29.1468 | -42.0833 | 79.6429 |
| `fedwatch_actual_change_bps` | 8.3333 | 28.5133 | -50.0 | 75.0 |
| `fedwatch_surprise_bps` | -0.2617 | 3.8631 | -10.6364 | 15.5 |
| `fedwatch_surprise_zscore` | -0.0286 | 0.4643 | -1.2576 | 1.8844 |
| `real_rate_diff_5y` | 1.2632 | 0.446 | 0.533 | 2.0889 |
| `cleveland_national_score` | 0.0256 | 0.2244 | -0.3721 | 0.475 |
| `cleveland_consensus_score` | -0.0983 | 0.1429 | -0.2894 | 0.2217 |
| `cleveland_divergence` | 0.1239 | 0.111 | -0.1219 | 0.3365 |

## 6. Spot Checks

### 2022-03-16 — Hiking cycle start
- `statement_ensemble_net`: 0.3750
- `statement_fomc_roberta_net`: 0.3750
- `statement_llama_deepinfra_net`: 0.1875
- `minutes_lag_ensemble_net`: 0.1261
- `minutes_lag_fomc_roberta_net`: 0.1261
- `minutes_lag_llama_deepinfra_net`: 0.0757
- `minutes_lag_source_date`: 2022-01-26
- `fedwatch_implied_change_bps`: 28.5781
- `fedwatch_actual_change_bps`: 25.0000
- `fedwatch_surprise_bps`: -3.5781
- `fedwatch_surprise_zscore`: -0.4138
- `real_rate_diff_5y`: 0.5330
- `real_rate_diff_source_date`: 2022-03-15
- `cleveland_national_score`: 0.1410
- `cleveland_consensus_score`: 0.0072
- `cleveland_divergence`: 0.1339
- `cleveland_source_date`: 2022-03-01

### 2024-09-18 — Cutting cycle start
- `statement_ensemble_net`: 0.0556
- `statement_fomc_roberta_net`: 0.0556
- `statement_llama_deepinfra_net`: -0.0556
- `minutes_lag_ensemble_net`: 0.0335
- `minutes_lag_fomc_roberta_net`: 0.0335
- `minutes_lag_llama_deepinfra_net`: -0.0293
- `minutes_lag_source_date`: 2024-07-31
- `fedwatch_implied_change_bps`: -42.0833
- `fedwatch_actual_change_bps`: -50.0000
- `fedwatch_surprise_bps`: -7.9167
- `fedwatch_surprise_zscore`: -0.9711
- `real_rate_diff_5y`: 1.5112
- `real_rate_diff_source_date`: 2024-09-17
- `cleveland_national_score`: -0.3176
- `cleveland_consensus_score`: -0.1957
- `cleveland_divergence`: -0.1219
- `cleveland_source_date`: 2024-09-01

## 7. Warnings / Notes

- First meeting (2021-01-27): `minutes_lag_*` = NaN (no prior meeting in NLP set). Expected.
- All meetings have Cleveland Fed data available strictly before T.
- All meetings have real rate data at T-1 business day.
- 2024-09-18 statement wording near-neutral (ensemble_net=0.056) despite 50bp cut action: Fed balanced language while initiating easing cycle.