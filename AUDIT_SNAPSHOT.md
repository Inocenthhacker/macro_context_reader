# Project State Snapshot — 2026-04-15 15:20

Read-only audit. No source files modified.

## 1. Git State

- **HEAD:** `2253776 | 2026-04-15 | feat(fedwatch): Atlanta Fed MPT loader (2023-2026 coverage) [INFRA/MPT-INGEST]`
- **Branch:** `main`
- **Working tree:** 2 files modified/untracked
- **Remote branches:**
  - `* main`
  - `remotes/origin/HEAD -> origin/main`
  - `remotes/origin/main`

<details><summary>Last 30 commits</summary>

```
2253776 feat(fedwatch): Atlanta Fed MPT loader (2023-2026 coverage) [INFRA/MPT-INGEST]
68a0f21 feat(market-pricing): persist EUR/USD history to Parquet [INFRA/FX-BACKFILL]
c60638b feat(prd-300): refactor divergence + decomposition layer (HP+EMD) [PRD-300/CC-1]
5bffd8b docs(prd-300): approve PRD-300 Divergence & Sentiment Trend Signal [INFRA/PRD-300-CREATE]
30b9371 docs(roadmap): fix PRD-202 status drift flagged by session audit [INFRA/ROADMAP-FIX-PRD202]
5ba60ad docs(citations): add CITATION.md + CITATION.cff with full academic attribution [INFRA/CITATIONS]
78dbe5b docs(prd-202): mark Done after MAP.md verification + sync CHANGELOG [INFRA/FINAL-SYNC]
dc12431 docs(prds): create 8 missing PRD standalone files [INFRA/PRD-FILES-MISSING]
8d98b08 docs(prds): archive old PRD-202 + create new PRD-202 + standardize PRD-400 [INFRA/PRD-CONFLICT-RESOLUTION-v2]
896bb97 docs(onboarding): comprehensive onboarding scaffold for new collaborators [INFRA/ONBOARDING-SCAFFOLD-1]
d83156b docs(roadmap): checkout 2026-04-15 — PRD-202 done, PRD-101 audit, 4 new decisions
0cb3493 feat(prd-202): surprise signal — 3 methods + single/batch interfaces [PRD-202/CC-3]
f49f91d fix(prd-202): warn instead of silently skipping invalid snapshot files [PRD-202/CC-2-PATCH]
0d1f93c feat(prd-202): multi-snapshot loader with dedup + Parquet [PRD-202/CC-2]
451b1dc feat(prd-202): CME FedWatch CSV parser + pydantic schemas [PRD-202/CC-1]
fbdc589 docs(prd-200): add MAP.md documenting actual market_pricing/ structure [PRD-200/CC-MAP]
06a5282 docs(roadmap): checkout 2026-04-14 - PRD-102 complete, D20-D22 added, Faza 5 redefined [INFRA/CHECKOUT-2026-04-14]
0763795 fix(prd-102): update CELL-02 bootstrap import after pipeline.py deletion [PRD-102/CC-2-FIX]
3c1fe3d refactor(prd-102): replace local scraper+FinBERT with Cleveland Fed pre-computed indices [PRD-102/CC-2]
93d1003 fix(prd-102): switch to PyMuPDF + fallback regex for multi-column PDFs [PRD-102/CC-1-FIX9]
e254528 fix(prd-102): make 05_economic_sentiment_validation runnable on fresh Colab [PRD-102/NOTEBOOK-05-FIX]
c416240 fix(infra): self-sufficient inline bootstrap in CELL-01 for Python 3.12 Colab [INFRA/BOOTSTRAP-INLINE-FIX]
a70979d fix(infra): force sys.path injection in bootstrap for Python 3.12 Colab kernel [INFRA/BOOTSTRAP-PATH-FIX]
42a7813 fix(prd-102): self-contained debug notebook with PDF auto-download [PRD-102/DEBUG-1-FIX2]
ce19ccf fix(prd-102): update debug notebook for transformers API change [PRD-102/DEBUG-1-FIX]
8a7ade5 infra(notebooks): extend CELL ID protocol with output print statement [INFRA/CELL-ID-V2]
b7d836b fix(prd-102): clamp FinBERT softmax probabilities to handle float32 precision [PRD-102/CC-FIX-PYDANTIC]
20d8c40 infra(notebooks): standardize CELL-<NN> ID protocol across all notebooks [INFRA/CELL-ID-STANDARD]
9d1eced debug(prd-102): standalone FinBERT inspection notebook for fast iteration [PRD-102/DEBUG-1]
6b4cdb2 feat(prd-102): rewrite Beige Book scraper on PDF source — single parser for all years [PRD-102/CC-1-FIX8]
```
</details>

## 2. PRD Registry

| ID | Title | Status | Layer | Owner | CC Done/Total | Updated |
|----|-------|--------|-------|-------|---------------|---------|
| PRD-001 | Project Structure & Repository Setup | Done | Infrastructure | Hrimiuc | 1/1 | 2026-04-15 |
| PRD-002 | Compute Infrastructure — GPU & Cloud | Draft | Infrastructure | Hrimiuc | 0/5 | 2026-04-15 |
| PRD-050 | Macro Regime Classifier — System Triage | Done | Infrastructure / Cro | Fabian | 2/2 | 2026-04-12 |
| PRD-051 | Regime Monitor — Standalone Dashboard | Draft (CC-1 Done placehol | Infrastructure — Das | Hrimiuc | 3/7 | 2026-04-15 |
| PRD-101 | FOMC NLP Pipeline — Ensemble (FOMC-RoBERTa + Llama | ~85% Done | Stratul 1 — Rhetoric | Hrimiuc | 0/10 | 2026-04-15 |
| PRD-102 | Economic Sentiment — Cleveland Fed Beige Book Load | Done | Stratul 1 (consumer- | Hrimiuc | 1/3 | 2026-04-15 |
| PRD-200 | Real Rate Differential — Ancora Fundamentală EUR/U | Done (cu AC-9 outstanding | Stratul 2 — Market P | Fabian | 8/41 | 2026-04-11 |
| PRD-202 | Market Pricing — FedWatch Probabilities Loader & S | Done | Stratul 2 — Market P | Hrimiuc | 1/5 | 2026-04-15 |
| PRD-300 | Divergence & Sentiment Trend Signal — Composite La | Approved | Stratul 3 — Divergen | Hrimiuc | 0/11 | 2026-04-15 |
| PRD-400 | COT Structural Positioning — Dual Signal Architect | Approved | Stratul 4A — Structu | Fabian | 7/21 | 2026-04-15 |
| PRD-401 | Tactical Positioning — OI + Options + Retail | Done | Stratul 4B — Tactica | Hrimiuc | 4/4 | 2026-04-15 |
| PRD-500 | Output Aggregation — Dempster-Shafer Evidence Fusi | Reserved (CC-0 Done — pla | Output | Hrimiuc | 3/9 | 2026-04-15 |

## 3. Module Inventory

### `src/macro_context_reader/data/`
- **Status:** EMPTY
- **Files:** 0 | **Lines:** 0 | **Stubs:** 0 | **TODOs:** 0

### `src/macro_context_reader/divergence/`
- **Status:** PARTIAL
- **Files:** 6 | **Lines:** 803 | **Stubs:** 6 | **TODOs:** 0

  | File | Lines | defs/classes | stubs | TODOs |
  |---|---|---|---|---|
  | `decomposition/compare.py` | 49 | 2 | 0 | 0 |
  | `decomposition/emd.py` | 82 | 1 | 0 | 0 |
  | `decomposition/hp_filter.py` | 72 | 1 | 0 | 0 |
  | `decomposition/schemas.py` | 39 | 1 | 0 | 0 |
  | `equilibrium.py` | 246 | 6 | 6 | 0 |
  | `regime_conditional.py` | 315 | 7 | 0 | 0 |

### `src/macro_context_reader/economic_sentiment/`
- **Status:** IMPLEMENTED
- **Files:** 2 | **Lines:** 117 | **Stubs:** 0 | **TODOs:** 0

  | File | Lines | defs/classes | stubs | TODOs |
  |---|---|---|---|---|
  | `loader.py` | 93 | 3 | 0 | 0 |
  | `schemas.py` | 24 | 0 | 0 | 0 |

### `src/macro_context_reader/market_pricing/`
- **Status:** IMPLEMENTED
- **Files:** 13 | **Lines:** 2079 | **Stubs:** 0 | **TODOs:** 0

  | File | Lines | defs/classes | stubs | TODOs |
  |---|---|---|---|---|
  | `eu_inflation.py` | 163 | 7 | 0 | 0 |
  | `eu_rates.py` | 181 | 6 | 0 | 0 |
  | `fedwatch/loader.py` | 135 | 4 | 0 | 0 |
  | `fedwatch/parser.py` | 164 | 5 | 0 | 0 |
  | `fedwatch/schemas.py` | 35 | 2 | 0 | 0 |
  | `fedwatch/surprise.py` | 298 | 11 | 0 | 0 |
  | `fedwatch/synthetic/mpt_loader.py` | 154 | 6 | 0 | 0 |
  | `fedwatch/synthetic/schemas.py` | 19 | 1 | 0 | 0 |
  | `fx.py` | 196 | 6 | 0 | 0 |
  | `inflation_expectations/base.py` | 77 | 1 | 0 | 0 |
  | `real_rate_differential.py` | 257 | 8 | 0 | 0 |
  | `schemas.py` | 241 | 8 | 0 | 0 |
  | `us_rates.py` | 159 | 5 | 0 | 0 |

### `src/macro_context_reader/monitoring/`
- **Status:** PLACEHOLDER
- **Files:** 3 | **Lines:** 169 | **Stubs:** 8 | **TODOs:** 0

  | File | Lines | defs/classes | stubs | TODOs |
  |---|---|---|---|---|
  | `_snapshot.py` | 26 | 1 | 1 | 0 |
  | `_standalone_calc.py` | 39 | 1 | 1 | 0 |
  | `regime_monitor.py` | 104 | 6 | 6 | 0 |

### `src/macro_context_reader/output/`
- **Status:** PLACEHOLDER
- **Files:** 9 | **Lines:** 260 | **Stubs:** 9 | **TODOs:** 0

  | File | Lines | defs/classes | stubs | TODOs |
  |---|---|---|---|---|
  | `aggregator.py` | 42 | 1 | 1 | 0 |
  | `bba_mappers/layer1_rhetoric.py` | 28 | 1 | 1 | 0 |
  | `bba_mappers/layer2_market.py` | 24 | 1 | 1 | 0 |
  | `bba_mappers/layer3_divergence.py` | 26 | 1 | 1 | 0 |
  | `bba_mappers/layer4_positioning.py` | 30 | 1 | 1 | 0 |
  | `combination_rules/dempster.py` | 23 | 1 | 1 | 0 |
  | `combination_rules/pcr5.py` | 35 | 1 | 1 | 0 |
  | `combination_rules/yager.py` | 23 | 1 | 1 | 0 |
  | `position_sizing.py` | 29 | 1 | 1 | 0 |

### `src/macro_context_reader/positioning/`
- **Status:** IMPLEMENTED
- **Files:** 6 | **Lines:** 418 | **Stubs:** 0 | **TODOs:** 0

  | File | Lines | defs/classes | stubs | TODOs |
  |---|---|---|---|---|
  | `cot_leveraged_funds.py` | 111 | 5 | 0 | 0 |
  | `oi_signal.py` | 61 | 3 | 0 | 0 |
  | `options_signal.py` | 58 | 3 | 0 | 0 |
  | `retail_signal.py` | 52 | 3 | 0 | 0 |
  | `schemas.py` | 52 | 1 | 0 | 0 |
  | `tactical_composite.py` | 84 | 3 | 0 | 0 |

### `src/macro_context_reader/regime/`
- **Status:** PARTIAL
- **Files:** 7 | **Lines:** 1124 | **Stubs:** 3 | **TODOs:** 0

  | File | Lines | defs/classes | stubs | TODOs |
  |---|---|---|---|---|
  | `analog_detector.py` | 200 | 1 | 0 | 0 |
  | `classifier.py` | 53 | 2 | 2 | 0 |
  | `consensus.py` | 204 | 4 | 0 | 0 |
  | `hmm_classifier.py` | 350 | 1 | 0 | 0 |
  | `indicators.py` | 169 | 3 | 0 | 0 |
  | `router.py` | 62 | 1 | 1 | 0 |
  | `schemas.py` | 86 | 4 | 0 | 0 |

### `src/macro_context_reader/rhetoric/`
- **Status:** PARTIAL
- **Files:** 20 | **Lines:** 1859 | **Stubs:** 19 | **TODOs:** 0

  | File | Lines | defs/classes | stubs | TODOs |
  |---|---|---|---|---|
  | `concept_framework/aggregator.py` | 118 | 2 | 2 | 0 |
  | `concept_framework/decomposer.py` | 11 | 1 | 1 | 0 |
  | `concept_framework/dictionary/registry.py` | 15 | 2 | 2 | 0 |
  | `concept_framework/dictionary/validator.py` | 13 | 2 | 2 | 0 |
  | `concept_framework/discovery/corpus.py` | 11 | 1 | 1 | 0 |
  | `concept_framework/discovery/expansion.py` | 26 | 2 | 2 | 0 |
  | `concept_framework/discovery/lda.py` | 18 | 2 | 2 | 0 |
  | `concept_framework/extractor.py` | 146 | 4 | 4 | 0 |
  | `concept_framework/sources/beige_book.py` | 16 | 2 | 2 | 0 |
  | `concept_framework/sources/fomc_docs.py` | 11 | 1 | 1 | 0 |
  | `ensemble.py` | 149 | 3 | 0 | 0 |
  | `matched_filter.py` | 84 | 5 | 0 | 0 |
  | `pipeline.py` | 198 | 2 | 0 | 0 |
  | `preprocessor.py` | 88 | 5 | 0 | 0 |
  | `schemas.py` | 88 | 4 | 0 | 0 |
  | `scorers/base.py` | 27 | 1 | 0 | 0 |
  | `scorers/finbert_fomc.py` | 175 | 1 | 0 | 0 |
  | `scorers/fomc_roberta.py` | 110 | 1 | 0 | 0 |
  | `scorers/llama_deepinfra.py` | 188 | 3 | 0 | 0 |
  | `scraper.py` | 367 | 10 | 0 | 0 |

## 4. Test Coverage

### Collection
```
tests/rhetoric/test_scraper.py::test_extract_statement_rejects_empty_content
tests/rhetoric/test_scraper.py::test_extract_statement_rejects_too_short
tests/rhetoric/test_scraper.py::test_fetch_statements_filters_strategy_docs

302 tests collected in 5.98s
```

### Smoke run (unit only, no integration, first-failure)
```
C:\Users\Hrimiuc\Desktop\macro_context_reader\tests\regime\test_hmm_classifier.py:134: UserWarning: No n_states has ARI >= 0.7. Selected n=2 with ARI=0.289.
    diag = hmm.fit(noisy, n_states_grid=[2, 3], n_seeds=5)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
278 passed, 24 deselected, 4 warnings in 33.13s
```

### Test files per module
| Module | Test files |
|---|---|
| `divergence` | 4 |
| `economic_sentiment` | 1 |
| `market_pricing` | 11 |
| `positioning` | 2 |
| `regime` | 3 |
| `rhetoric` | 5 |

## 5. Data Artifacts

| Path | Size (KB) | Modified |
|---|---|---|
| `data/market_pricing/fedwatch_history.parquet` | 87.0 | 2026-04-15 15:20 |
| `data/market_pricing/fedwatch_mpt.parquet` | 109.2 | 2026-04-15 14:20 |
| `data/market_pricing/fx.parquet` | 38.2 | 2026-04-15 14:01 |
| `data/positioning/cot_eur.parquet` | 15.4 | 2026-04-11 16:46 |

### Top 3 most-recent parquet shapes
- **`data/market_pricing/fedwatch_history.parquet`**: shape=(9220, 6), cols=['observation_date', 'meeting_date', 'rate_bucket_low', 'rate_bucket_high', 'probability', 'source_snapshot_date'], range=2025-04-14 00:00:00 -> 2026-04-13 00:00:00
- **`data/market_pricing/fedwatch_mpt.parquet`**: shape=(36203, 6), cols=['observation_date', 'meeting_date', 'rate_bucket_low', 'rate_bucket_high', 'probability', 'source'], range=2023-03-29 00:00:00 -> 2026-04-13 00:00:00
- **`data/market_pricing/fx.parquet`**: shape=(2756, 1), cols=['eurusd'], range=index 2015-04-01 00:00:00 -> 2026-04-10 00:00:00

## 6. Notebooks

| File | Title (first md cell) | Cells | Modified |
|---|---|---|---|
| `00_setup.ipynb` | Colab Setup & Drive Mount | 6 | 2026-04-13 |
| `01_layer1_rhetoric.ipynb` | Layer 1: Rhetoric / NLP | 4 | 2026-04-13 |
| `01_regime_classifier_validation.ipynb` | Macro Regime Classifier — Empirical Validation | 10 | 2026-04-13 |
| `02_layer2_market_pricing.ipynb` | Layer 2 - Market Pricing Pipeline | 11 | 2026-04-13 |
| `02b_layer2_regime_diagnostic.ipynb` | Layer 2 - Regime Switching Diagnostic | 13 | 2026-04-13 |
| `03_layer3_divergence.ipynb` | Layer 3: Divergence Signal | 4 | 2026-04-13 |
| `03_regime_conditional_diagnostic.ipynb` | PRD-300 / CC-0d — Regime-Conditional Correlation Diagnostic | 9 | 2026-04-13 |
| `04_layer4_positioning.ipynb` | Layer 4: Positioning | 4 | 2026-04-13 |
| `04_rhetoric_scoring_validation.ipynb` | PRD-101 / CC-1 — FOMC Rhetoric Scoring Validation | 9 | 2026-04-13 |
| `04a_layer4_cot_leveraged_funds_diagnostic.ipynb` | Layer 4A — COT Structural Positioning Diagnostic | 14 | 2026-04-13 |
| `05_economic_sentiment_validation.ipynb` | PRD-102: Economic Sentiment Validation (Cleveland Fed Beige  | 10 | 2026-04-14 |
| `05_live_pipeline.ipynb` | Live Pipeline: Press Conference Real-Time | 4 | 2026-04-13 |
| `debug_finbert_inspection.ipynb` | DEBUG: FinBERT-FOMC + Beige Book Pipeline Inspection | 11 | 2026-04-13 |

## 7. Secrets & Env

- **`.env.example`:** exists, 4 keys
  - `DEEPINFRA_API_KEY`
  - `FRED_API_KEY`
  - `GITHUB_TOKEN`
  - `HF_TOKEN`
- **`.env`:** exists (NOT READ)
- **`python-dotenv` in pyproject.toml:** yes

## 8. Known Blockers / TODOs in code

| File:Line | Marker | Context |
|---|---|---|
| `src/macro_context_reader/divergence/equilibrium.py:94` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-300")` |
| `src/macro_context_reader/divergence/equilibrium.py:125` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-300")` |
| `src/macro_context_reader/divergence/equilibrium.py:162` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-300")` |
| `src/macro_context_reader/divergence/equilibrium.py:186` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-300")` |
| `src/macro_context_reader/divergence/equilibrium.py:213` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-300")` |
| `src/macro_context_reader/divergence/equilibrium.py:246` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-300")` |
| `src/macro_context_reader/monitoring/regime_monitor.py:26` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-051")` |
| `src/macro_context_reader/monitoring/regime_monitor.py:35` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-051")` |
| `src/macro_context_reader/monitoring/regime_monitor.py:44` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-051")` |
| `src/macro_context_reader/monitoring/regime_monitor.py:53` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-051")` |
| `src/macro_context_reader/monitoring/regime_monitor.py:93` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-051")` |
| `src/macro_context_reader/monitoring/regime_monitor.py:104` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-051")` |
| `src/macro_context_reader/monitoring/_snapshot.py:26` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-051")` |
| `src/macro_context_reader/monitoring/_standalone_calc.py:39` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-051")` |
| `src/macro_context_reader/output/aggregator.py:42` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-500")` |
| `src/macro_context_reader/output/position_sizing.py:29` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-500")` |
| `src/macro_context_reader/output/bba_mappers/layer1_rhetoric.py:28` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-500")` |
| `src/macro_context_reader/output/bba_mappers/layer2_market.py:24` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-500")` |
| `src/macro_context_reader/output/bba_mappers/layer3_divergence.py:26` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-500")` |
| `src/macro_context_reader/output/bba_mappers/layer4_positioning.py:30` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-500")` |
| `src/macro_context_reader/output/combination_rules/dempster.py:23` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-500")` |
| `src/macro_context_reader/output/combination_rules/pcr5.py:35` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-500")` |
| `src/macro_context_reader/output/combination_rules/yager.py:23` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-500")` |
| `src/macro_context_reader/regime/classifier.py:40` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-050")` |
| `src/macro_context_reader/regime/classifier.py:53` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-050")` |
| `src/macro_context_reader/regime/router.py:62` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-050")` |
| `src/macro_context_reader/rhetoric/concept_framework/aggregator.py:89` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-102")` |
| `src/macro_context_reader/rhetoric/concept_framework/aggregator.py:118` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-102")` |
| `src/macro_context_reader/rhetoric/concept_framework/decomposer.py:11` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-102")` |
| `src/macro_context_reader/rhetoric/concept_framework/extractor.py:66` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-102")` |
| `src/macro_context_reader/rhetoric/concept_framework/extractor.py:95` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-102")` |
| `src/macro_context_reader/rhetoric/concept_framework/extractor.py:130` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-102")` |
| `src/macro_context_reader/rhetoric/concept_framework/extractor.py:146` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-102")` |
| `src/macro_context_reader/rhetoric/concept_framework/dictionary/registry.py:10` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-102")` |
| `src/macro_context_reader/rhetoric/concept_framework/dictionary/registry.py:15` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-102")` |
| `src/macro_context_reader/rhetoric/concept_framework/dictionary/validator.py:8` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-102")` |
| `src/macro_context_reader/rhetoric/concept_framework/dictionary/validator.py:13` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-102")` |
| `src/macro_context_reader/rhetoric/concept_framework/discovery/corpus.py:11` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-102")` |
| `src/macro_context_reader/rhetoric/concept_framework/discovery/expansion.py:21` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-102")` |
| `src/macro_context_reader/rhetoric/concept_framework/discovery/expansion.py:26` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-102")` |
| `src/macro_context_reader/rhetoric/concept_framework/discovery/lda.py:13` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-102")` |
| `src/macro_context_reader/rhetoric/concept_framework/discovery/lda.py:18` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-102")` |
| `src/macro_context_reader/rhetoric/concept_framework/sources/beige_book.py:11` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-102")` |
| `src/macro_context_reader/rhetoric/concept_framework/sources/beige_book.py:16` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-102")` |
| `src/macro_context_reader/rhetoric/concept_framework/sources/fomc_docs.py:11` | `raise NotImplementedError` | `raise NotImplementedError("TODO: PRD-102")` |

## 9. Recent Activity (14 days)

- **Commits in last 14 days:** 111

<details><summary>Commit list</summary>

```
2253776 2026-04-15 feat(fedwatch): Atlanta Fed MPT loader (2023-2026 coverage) [INFRA/MPT-INGEST]
68a0f21 2026-04-15 feat(market-pricing): persist EUR/USD history to Parquet [INFRA/FX-BACKFILL]
c60638b 2026-04-15 feat(prd-300): refactor divergence + decomposition layer (HP+EMD) [PRD-300/CC-1]
5bffd8b 2026-04-15 docs(prd-300): approve PRD-300 Divergence & Sentiment Trend Signal [INFRA/PRD-300-CREATE]
30b9371 2026-04-15 docs(roadmap): fix PRD-202 status drift flagged by session audit [INFRA/ROADMAP-FIX-PRD202]
5ba60ad 2026-04-15 docs(citations): add CITATION.md + CITATION.cff with full academic attribution [INFRA/CITATIONS]
78dbe5b 2026-04-15 docs(prd-202): mark Done after MAP.md verification + sync CHANGELOG [INFRA/FINAL-SYNC]
dc12431 2026-04-15 docs(prds): create 8 missing PRD standalone files [INFRA/PRD-FILES-MISSING]
8d98b08 2026-04-15 docs(prds): archive old PRD-202 + create new PRD-202 + standardize PRD-400 [INFRA/PRD-CONFLICT-RESOLUTION-v2]
896bb97 2026-04-15 docs(onboarding): comprehensive onboarding scaffold for new collaborators [INFRA/ONBOARDING-SCAFFOLD-1]
d83156b 2026-04-15 docs(roadmap): checkout 2026-04-15 — PRD-202 done, PRD-101 audit, 4 new decisions
0cb3493 2026-04-14 feat(prd-202): surprise signal — 3 methods + single/batch interfaces [PRD-202/CC-3]
f49f91d 2026-04-14 fix(prd-202): warn instead of silently skipping invalid snapshot files [PRD-202/CC-2-PATCH]
0d1f93c 2026-04-14 feat(prd-202): multi-snapshot loader with dedup + Parquet [PRD-202/CC-2]
451b1dc 2026-04-14 feat(prd-202): CME FedWatch CSV parser + pydantic schemas [PRD-202/CC-1]
fbdc589 2026-04-14 docs(prd-200): add MAP.md documenting actual market_pricing/ structure [PRD-200/CC-MAP]
06a5282 2026-04-14 docs(roadmap): checkout 2026-04-14 - PRD-102 complete, D20-D22 added, Faza 5 redefined [INFRA/CHECKOUT-2026-04-14]
0763795 2026-04-14 fix(prd-102): update CELL-02 bootstrap import after pipeline.py deletion [PRD-102/CC-2-FIX]
3c1fe3d 2026-04-14 refactor(prd-102): replace local scraper+FinBERT with Cleveland Fed pre-computed indices [PRD-102/CC-2]
93d1003 2026-04-13 fix(prd-102): switch to PyMuPDF + fallback regex for multi-column PDFs [PRD-102/CC-1-FIX9]
e254528 2026-04-13 fix(prd-102): make 05_economic_sentiment_validation runnable on fresh Colab [PRD-102/NOTEBOOK-05-FIX]
c416240 2026-04-13 fix(infra): self-sufficient inline bootstrap in CELL-01 for Python 3.12 Colab [INFRA/BOOTSTRAP-INLINE-FIX]
a70979d 2026-04-13 fix(infra): force sys.path injection in bootstrap for Python 3.12 Colab kernel [INFRA/BOOTSTRAP-PATH-FIX]
42a7813 2026-04-13 fix(prd-102): self-contained debug notebook with PDF auto-download [PRD-102/DEBUG-1-FIX2]
ce19ccf 2026-04-13 fix(prd-102): update debug notebook for transformers API change [PRD-102/DEBUG-1-FIX]
8a7ade5 2026-04-13 infra(notebooks): extend CELL ID protocol with output print statement [INFRA/CELL-ID-V2]
b7d836b 2026-04-13 fix(prd-102): clamp FinBERT softmax probabilities to handle float32 precision [PRD-102/CC-FIX-PYDANTIC]
20d8c40 2026-04-13 infra(notebooks): standardize CELL-<NN> ID protocol across all notebooks [INFRA/CELL-ID-STANDARD]
9d1eced 2026-04-13 debug(prd-102): standalone FinBERT inspection notebook for fast iteration [PRD-102/DEBUG-1]
6b4cdb2 2026-04-12 feat(prd-102): rewrite Beige Book scraper on PDF source — single parser for all years [PRD-102/CC-1-FIX8]
dbf79cd 2026-04-12 fix(prd-102): rewrite monolithic parser to use h4 "Federal Reserve Bank of X" headers [PRD-102/CC-1-FIX7]
24d5bc6 2026-04-12 fix(prd-102): MIN_SUPPORTED_YEAR=2017 guard + monolithic HTML parser for 2017-2023 districts [PRD-102/CC-1-FIX5, CC-1-FIX6]
c15ca09 2026-04-12 chore(notebooks): standardize bootstrap pattern across all notebooks
535d756 2026-04-12 chore: ignore data/economic_sentiment/ cache and parquet files
a95b73c 2026-04-12 fix(prd-102): discovery-based URL extraction — suffix is not calendar month [PRD-102/CC-1-FIX4]
2905586 2026-04-12 fix(prd-102): correct district URL slugs — dash-separated, empirically validated [PRD-102/CC-1-FIX3]
bf926f3 2026-04-12 fix(prd-102): rewrite Beige Book scraper with validated URL patterns [PRD-102/CC-1-FIX2]
a2adb70 2026-04-12 fix(prd-102): ensure cache dir exists before write in Beige Book scraper [PRD-102/CC-1-FIX1]
5a107ea 2026-04-12 fix(notebooks): replace userdata.get().or fallback with try/except (prevents SecretNotFoundError)
4757ad1 2026-04-12 feat(prd-102): add Economic Sentiment module — Beige Book + FinBERT [PRD-102/CC-1]
33adddf 2026-04-12 refactor(prd-101): remove FinBERT from FOMC ensemble (empirical validation 20%) [PRD-101/CC-1-FIX7]
7053ea3 2026-04-12 fix(prd-101): FOMC-RoBERTa LABEL_MAP inversion — 0=dovish, 1=hawkish per Shah et al. [PRD-101/CC-1-FIX6]
dad1e66 2026-04-12 debug(prd-101): add 3-scorer disagreement diagnostic script
dd98dac 2026-04-12 fix(prd-101): FinBERT label mapping — Positive->hawkish, Negative->dovish [PRD-101/CC-1-FIX5]
6a4e8a9 2026-04-12 fix(prd-101): normalize before clip + defensive asserts [PRD-101/CC-1-FIX4]
40a74ec 2026-04-12 Merge PRD-101/CC-1-FIX3: meeting statement filtering + clean text extraction
48d4bea 2026-04-12 fix(prd-101): filter meeting statements only + extract clean text [PRD-101/CC-1-FIX3]
00173d1 2026-04-12 Merge PRD-101/CC-1-FIX2: softmax precision clamp
436ae93 2026-04-12 fix(prd-101): clamp softmax output for Pydantic float precision [PRD-101/CC-1-FIX2]
5251ae7 2026-04-12 Merge PRD-101/CC-1-FIX1: scraper cache dir creation + absolute paths
939c501 2026-04-12 fix(prd-101): create cache dirs before write + absolute paths via __file__ [PRD-101/CC-1-FIX1]
34a5119 2026-04-12 test(prd-101): add 3 integration tests for real model inference + API call [PRD-101/CC-1]
9b82ef5 2026-04-12 Merge PRD-101/CC-1: FOMC rhetoric pipeline (tri-model ensemble + matched-filter)
3b50007 2026-04-12 feat(prd-101): FOMC rhetoric pipeline — tri-model ensemble + matched-filter [PRD-101/CC-1]
271b2d0 2026-04-12 Merge PRD-300/CC-0d-FIX1: align start date with T5YIE availability
c3fb8da 2026-04-12 fix(prd-300): align start date with T5YIE availability (2003-01-01) [PRD-300/CC-0d-FIX1]
5750888 2026-04-12 Merge INFRA/NOTEBOOK-BOOTSTRAP: idempotent Colab/local setup in all 10 notebooks
c3b41f1 2026-04-12 infra(notebooks): add idempotent bootstrap cells for Colab/local compat [INFRA/NOTEBOOK-BOOTSTRAP]
99dd8e3 2026-04-12 Merge PRD-300/CC-0d: regime-conditional correlation diagnostic
daf75af 2026-04-12 feat(prd-300): regime-conditional correlation diagnostic [PRD-300/CC-0d]
39d543d 2026-04-12 docs: session checkout 2026-04-12 — PRD-050 empirical validation + DEC-006..011
ca1651f 2026-04-12 Merge PRD-050/CC-1b: HMM fit strategy refactor (BIC+ARI+unique labels)
c778a5e 2026-04-12 refactor(prd-050): HMM fit strategy — full-history scaler, BIC+ARI grid, diag covariance, unique labels [PRD-050/CC-1b]
1d32bb5 2026-04-12 Merge PRD-050/CC-1+2+3: Macro Regime Classifier (HMM + Mahalanobis)
c69d73e 2026-04-12 feat(prd-050): implement Macro Regime Classifier with HMM + Mahalanobis analogs [PRD-050/CC-1+2+3]
5d5629d 2026-04-12 Merge PRD-400-RESTRUCTURE/CC-4: rebrand cot_structural → cot_leveraged_funds
846ae6d 2026-04-12 refactor(prd-400): rename cot_structural → cot_leveraged_funds [PRD-400-RESTRUCTURE/CC-4]
c545468 2026-04-11 Merge PRD-400 v2.0 restructure
734c0c5 2026-04-11 docs(prd-400): restructure to v2.0 dual signal architecture (Commercials+Leveraged) [PRD-400-RESTRUCTURE/CC-1]
3a221ae 2026-04-11 Merge PRD-400/CC-3: diagnostic notebook
84ca328 2026-04-11 feat(notebooks): add COT structural diagnostic notebook [PRD-400/CC-3]
379e2e7 2026-04-11 Merge PRD-400/CC-2: invariant tests
12f2b2f 2026-04-11 test(positioning): add temporal/dtype invariant tests for cot_structural [PRD-400/CC-2]
cd98809 2026-04-11 Merge PRD-400/CC-1: bugfix filter exact match
f1b3442 2026-04-11 fix(positioning): exact match filter EUR FX + Pydantic schemas + parquet regenerated [PRD-400/CC-1]
b9df21d 2026-04-11 docs(prd-400): approve Draft for execution [PRD-400-APPROVE/CC-1]
0d53eaa 2026-04-11 docs(prds): add PRD-400 Draft — COT Structural Positioning [PRD-400-DRAFT/CC-1]
f8f58dc 2026-04-11 chore(positioning): delete corrupt cot_eur.parquet — multi-contract pollution from substring filter [PRD-400-PREP]
dea013c 2026-04-11 docs(lessons): add LESSONS-001 PRD-200 retrospective + lessons/ index [DEBT-CLEANUP/CC-2]
16f67b1 2026-04-11 docs(decisions): add DEC-003 retroactive — US rates source DFII5 [DEBT-CLEANUP/CC-1]
bf6b94d 2026-04-11 docs(prd-200): mark PRD-200 Done after empirical validation [PRD-200/FINALIZE]
ac5a032 2026-04-11 feat(notebooks): layer 2 end-to-end pipeline + regime diagnostic [PRD-200/CC-7]
b38264e 2026-04-11 feat(notebooks): empirical AC-6 validation - all 3 sub-conditions PASS [PRD-200/AC6-VALIDATION]
0d11ac7 2026-04-11 docs(prd-200): reformulate AC-6 as regime-conditional + add DEC-005 [PRD-200/AC6-REFORMULATION]
c4346a2 2026-04-11 docs(prd-200): mark CC-8 + REQ-4 done after empirical validation [PRD-200-SYNC/CC-3]
8dd8fa7 2026-04-11 chore: add start_dev.bat for one-click venv activation
a81c100 2026-04-11 chore: gitignore local test outputs and Claude Code harness
bbeb6a4 2026-04-11 test(market_pricing): fix race condition in integration tests [PRD-200/CC-8b]
45ce478 2026-04-11 feat(market_pricing): add EUR/USD ingestion from FRED [PRD-200/CC-8]
2f65b23 2026-04-11 docs(prd-200): sync CC-5/CC-6 done + add CC-8 for orphan REQ-4 (fx.py) [PRD-200-SYNC/CC-1]
69c3b95 2026-04-10 Merge PRD-200/CC-6: real_rate_differential composite
38f1f01 2026-04-10 feat(market_pricing): add real_rate_differential composite [PRD-200/CC-6]
84a1acd 2026-04-10 Merge PRD-200/CC-5: EU 5Y inflation expectations from ECB SPF
f4cd669 2026-04-10 feat(market_pricing): add EU 5Y inflation expectations from ECB SPF [PRD-200/CC-5] [DEC-004]
257ab1b 2026-04-10 docs: sync PRD-200 status with code reality (CC-1..CC-4 done) [PRD-AUDIT/CC-2]
66f0e0d 2026-04-10 Merge PRD-200/CC-4: Pydantic validation + integration marker for us_rates
888ba69 2026-04-10 refactor(market_pricing): add Pydantic validation + integration marker to us_rates [PRD-200/CC-4]
325d544 2026-04-10 docs(CLAUDE.md): add ECB SDMX verification rule [DEC-002]
06ac4d4 2026-04-10 Merge PRD-200/CC-3: EU rates 5Y dual yield curves
a976684 2026-04-10 feat(market_pricing): add EU 5Y rates ingestion (dual AAA + All) [PRD-200/CC-3] [DEC-002]
1ff3085 2026-04-10 docs(prds): add PRD-202 draft - tactical short-horizon signal layer
e8548f7 2026-04-10 Merge PRD-200/CC-2b: switch to 5Y horizon
1a8c91a 2026-04-10 feat(market_pricing): switch US rates to 5Y horizon (DGS5/DFII5) [PRD-200/CC-2b] [DEC-001]
3ea5100 2026-04-10 Merge PRD-200/CC-2: US rates ingestion
15cbcee 2026-04-10 feat(market_pricing): add US rates ingestion from FRED [PRD-200/CC-2]
c4dbd56 2026-04-10 Merge pull request #1 from Inocenthhacker/feat/prd-200-cc1-protocol-base
fae3e85 2026-04-10 feat(market_pricing): add inflation expectations protocol + pydantic schemas [PRD-200/CC-1]
6721358 2026-04-10 docs(prds): promote PRD-200 to In Progress
626656b 2026-04-10 docs(prds): add PRD-200 draft - real rate differential SPF foundation
1397e3f 2026-04-10 chore: initial project snapshot
5b79054 2026-04-10 chore: initial git setup with .gitignore and commit template
```
</details>

### Most-touched files
| Count | File |
|---|---|
| 11 | `pyproject.toml` |
| 10 | `src/macro_context_reader/economic_sentiment/scraper.py` |
| 10 | `tests/economic_sentiment/test_scraper.py` |
| 8 | `.gitignore` |
| 8 | `ROADMAP.md` |
| 8 | `prds/PRD-200.md` |
| 7 | `notebooks/05_economic_sentiment_validation.ipynb` |
| 7 | `notebooks/01_regime_classifier_validation.ipynb` |
| 7 | `notebooks/02_layer2_market_pricing.ipynb` |
| 7 | `src/macro_context_reader/market_pricing/schemas.py` |
| 6 | `notebooks/debug_finbert_inspection.ipynb` |
| 6 | `notebooks/00_setup.ipynb` |
| 6 | `notebooks/01_layer1_rhetoric.ipynb` |
| 6 | `notebooks/02b_layer2_regime_diagnostic.ipynb` |
| 6 | `notebooks/03_layer3_divergence.ipynb` |

## 10. Architect Summary (auto-generated, descriptive only)

### Modules classified as IMPLEMENTED
- `economic_sentiment`
- `market_pricing`
- `positioning`

### Modules classified as PARTIAL
- `divergence`
- `monitoring`
- `output`
- `regime`
- `rhetoric`

### Modules classified as PLACEHOLDER / THIN

### Summary counts
- Parquet artifacts: 4
- Notebooks: 13
- Code markers (BLOCKER/TODO/stubs): 45
- Commits last 14 days: 111
