# CC-1.5.5 Pre-Flight Audit
Generated: 2026-04-21T16:24:23.474413

## 1. NLP Scores (CC-1.5.1)
Path: `data/rhetoric/fomc_scores.parquet`
- Shape: (126, 12)
- Columns: ['date', 'doc_type', 'doc_url', 'doc_title', 'n_sentences', 'ensemble_net', 'cosine_sim', 'weighted_score', 'agreement_rate', 'confidence', 'fomc_roberta_net', 'llama_deepinfra_net']
- Date range: 2021-01-27 00:00:00 -> 2026-03-18 00:00:00
- Date dtype: datetime64[ns]
- Unique dates: 42
- doc_type distribution:
  - minutes: 84
  - statement: 42
- Duplicate (date, doc_type): 42
- Duplicate (date, doc_type, doc_url): 0
- Score columns: ['ensemble_net', 'weighted_score', 'fomc_roberta_net', 'llama_deepinfra_net']
  - ensemble_net: 0 nulls, range [-0.500, 0.375]
  - weighted_score: 0 nulls, range [-0.250, 0.188]
  - fomc_roberta_net: 0 nulls, range [-0.500, 0.375]
  - llama_deepinfra_net: 0 nulls, range [-0.389, 0.353]

## 2. FedWatch Surprise (CC-1.5.2b-IMPL-2)
Path: `data/market_pricing/fedwatch_surprise.parquet`
- Shape: (125, 4)
- Columns: ['market_implied_change_bps', 'actual_change_bps', 'surprise_bps', 'surprise_zscore']
- Index type: DatetimeIndex
- Index date range: 2010-08-10 00:00:00 -> 2026-03-18 00:00:00
- Null counts:

## 3. Real Rate Differential (CC-1.5.3)
Path: `data/market_pricing/real_rate_differential.parquet`
- Shape: (2720, 6)
- Columns: ['date', 'us_5y_real', 'eu_5y_nominal_aaa', 'eu_inflation_expectations_5y', 'eu_5y_real', 'real_rate_differential']
- Index type: RangeIndex
- Date range: 2015-04-01 00:00:00 -> 2026-04-14 00:00:00
- Null counts per column:
  - date: 0 nulls
  - us_5y_real: 0 nulls
  - eu_5y_nominal_aaa: 0 nulls
  - eu_inflation_expectations_5y: 0 nulls
  - eu_5y_real: 0 nulls
  - real_rate_differential: 0 nulls

## 4. Cleveland Fed Sentiment (CC-1.5.4)
Path: `data/economic_sentiment/cleveland_fed_indices.parquet`
- Shape: (482, 16)
- Columns: ['publication_date', 'national_score', 'consensus_score', 'national_consensus_divergence', 'Boston_score', 'New_York_score', 'Philadelphia_score', 'Cleveland_score', 'Richmond_score', 'Atlanta_score', 'Chicago_score', 'St_Louis_score', 'Minneapolis_score', 'Kansas_City_score', 'Dallas_score', 'San_Francisco_score']
- Index type: RangeIndex

## 5. Canonical FOMC Dates (CC-1.5.0)
- FOMC_MEETING_DATES loaded: 297 entries
- First date: 1990-02-07 00:00:00
- Last date: 2026-12-16 00:00:00
- Dates in 2021-01-01 to 2026-12-31: 48

## 6. Cross-Source Alignment Feasibility

- NLP unique meeting dates (2021+): 42
- FedWatch unique meeting dates (all): 125
- FedWatch unique meeting dates (2021+): 42
- NLP intersect FedWatch (2021+ intersection): 42
- NLP dates missing FedWatch: 0
- FedWatch dates missing NLP: 0

## 7. Implementation Notes for CC-1.5.5

Anchor: canonical FOMC dates from utils/canonical_fomc_dates.py.
Target meeting count in master table: 42 (meetings with NLP scores).

Per-meeting NLP aggregation strategy:
- NLP has 2 rows per meeting (statement + minutes)
- For each canonical FOMC date, pick/aggregate the right row(s)
- Statement = scored same day as meeting
- Minutes = scored ~3 weeks AFTER meeting, released as lag signal
- RECOMMENDATION: keep both as separate columns (statement_ensemble_net, minutes_ensemble_net)
  OR aggregate into single ensemble score per meeting

Daily/monthly -> meeting-date alignment:
- real_rate_differential is DAILY -> use value ON the FOMC meeting date (or prior business day)
- cleveland_fed_indices is MONTHLY -> forward-fill to FOMC meeting date
- fedwatch_surprise is PER-MEETING already -> direct join on meeting date

Master alignment schema (proposed):
- Index: canonical FOMC meeting date (datetime)
- statement_ensemble_net, statement_fomc_roberta_net, statement_llama_deepinfra_net
- minutes_ensemble_net, minutes_fomc_roberta_net, minutes_llama_deepinfra_net
- fedwatch_surprise_bps, fedwatch_implied_change_bps, fedwatch_actual_change_bps
- real_rate_diff_5y (value on meeting date)
- cleveland_fed_expinf1yr (latest available value before meeting)

Coverage expectations:
- Max rows: 42
- Full coverage (all 4 features): 42
- Partial coverage (NLP + other 2, missing FedWatch): 0