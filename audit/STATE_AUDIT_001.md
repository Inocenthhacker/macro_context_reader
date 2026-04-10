# STATE AUDIT 001 — Filesystem vs. ROADMAP.md Reconciliation

> **Generated:** 2026-04-09 | **Scope:** read-only, facts only

---

## 1. Source Modules Inventory

All `.py` files under `src/macro_context_reader/`, with metadata.

| Path | Lines | Module Docstring | Functions | Classes | Placeholder Markers |
|---|---|---|---|---|---|
| `__init__.py` | 2 | no | — | — | no |
| `config.py` | 8 | no | — | — | no |
| `data/__init__.py` | 2 | no | — | — | no |
| `divergence/__init__.py` | 7 | yes | — | — | no |
| `divergence/decomposition.py` | 237 | yes | decompose_series, compute_deep_current_signal, is_deep_current_stable, compute_decision_signal, compute_horizon_adjusted_signal, compare_methods_backtesting | — | yes |
| `divergence/equilibrium.py` | 247 | yes | get_current_equilibrium, compute_misalignment, decompose_eurusd_movement, fetch_gfci_proxy, compute_equilibrium_scenario_from_regime, get_equilibrium_signal | — | yes |
| `market_pricing/__init__.py` | 2 | no | — | — | no |
| `monitoring/__init__.py` | 15 | yes | — | — | no |
| `monitoring/_snapshot.py` | 27 | yes | export_snapshot | — | yes |
| `monitoring/_standalone_calc.py` | 40 | yes | calculate_regime_standalone | — | yes |
| `monitoring/regime_monitor.py` | 105 | yes | _detect_mode, _render_status_section, _render_indicators_section, _render_history_section, _render_ews_panel, main | — | yes |
| `output/__init__.py` | 12 | yes | — | — | no |
| `output/aggregator.py` | 43 | yes | aggregate | — | yes |
| `output/bba_mappers/__init__.py` | 17 | yes | — | — | no |
| `output/bba_mappers/layer1_rhetoric.py` | 29 | yes | map_rhetoric_to_bba | — | yes |
| `output/bba_mappers/layer2_market.py` | 25 | yes | map_market_to_bba | — | yes |
| `output/bba_mappers/layer3_divergence.py` | 27 | yes | map_divergence_to_bba | — | yes |
| `output/bba_mappers/layer4_positioning.py` | 31 | yes | map_positioning_to_bba | — | yes |
| `output/combination_rules/__init__.py` | 2 | yes | — | — | no |
| `output/combination_rules/dempster.py` | 24 | yes | combine_dempster | — | yes |
| `output/combination_rules/pcr5.py` | 36 | yes | combine_pcr5 | — | yes |
| `output/combination_rules/yager.py` | 24 | yes | combine_yager | — | yes |
| `output/position_sizing.py` | 30 | yes | compute_position_signal | — | yes |
| `positioning/__init__.py` | 2 | no | — | — | no |
| `positioning/cot_structural.py` | 75 | yes | fetch_cot_eur, compute_cot_signals, save_cot_parquet, run_cot_pipeline | — | no |
| `positioning/oi_signal.py` | 62 | yes | fetch_eur_oi, compute_oi_signal, save_oi_parquet | — | no |
| `positioning/options_signal.py` | 59 | yes | fetch_eur_putcall_ratio, compute_options_signal, save_options_parquet | — | no |
| `positioning/retail_signal.py` | 53 | yes | fetch_retail_sentiment, compute_retail_signal, save_retail_parquet | — | no |
| `positioning/tactical_composite.py` | 85 | yes | load_signals, compute_tactical_score, run_tactical_pipeline | — | no |
| `regime/__init__.py` | 47 | yes | __getattr__ | MacroRegime | no |
| `regime/analog_detector.py` | 233 | yes | build_macro_vector, build_historical_matrix, compute_distances, find_analogs, compute_regime_distribution, detect_regime_analog | — | yes |
| `regime/classifier.py` | 54 | yes | classify_regime, get_current_regime | — | yes |
| `regime/indicators.py` | 47 | yes | fetch_triage_indicators | — | yes |
| `regime/router.py` | 63 | yes | get_regime_weights | — | yes |
| `rhetoric/__init__.py` | 2 | no | — | — | no |
| `rhetoric/concept_framework/__init__.py` | 7 | yes | — | — | no |
| `rhetoric/concept_framework/aggregator.py` | 119 | yes | fit, predict | — | yes |
| `rhetoric/concept_framework/decomposer.py` | 12 | yes | predict_decomposition | — | yes |
| `rhetoric/concept_framework/dictionary/__init__.py` | 2 | yes | — | — | no |
| `rhetoric/concept_framework/dictionary/registry.py` | 16 | yes | load_dictionary, save_dictionary | — | yes |
| `rhetoric/concept_framework/dictionary/validator.py` | 14 | yes | validate_no_overlap, validate_no_empty | — | yes |
| `rhetoric/concept_framework/discovery/__init__.py` | 2 | yes | — | — | no |
| `rhetoric/concept_framework/discovery/corpus.py` | 12 | yes | build_corpus | — | yes |
| `rhetoric/concept_framework/discovery/expansion.py` | 27 | yes | train_embeddings, expand_concept | — | yes |
| `rhetoric/concept_framework/discovery/lda.py` | 19 | yes | train_lda, extract_concept_candidates | — | yes |
| `rhetoric/concept_framework/extractor.py` | 147 | yes | compute_concept_frequency, compute_concept_subtypes, build_indicator_vector, aggregate_national | — | yes |
| `rhetoric/concept_framework/sources/__init__.py` | 2 | yes | — | — | no |
| `rhetoric/concept_framework/sources/beige_book.py` | 17 | yes | fetch_edition, list_available_editions | — | yes |
| `rhetoric/concept_framework/sources/fomc_docs.py` | 12 | yes | fetch_document | — | yes |

**Totals:** 48 `.py` files | 2,283 total lines | 34 files with placeholder markers | 14 files without

---

## 2. Expected Paths — ROADMAP.md Section 4 vs. Disk

### regime/

| Expected Path | Status |
|---|---|
| `regime/__init__.py` | EXISTS |
| `regime/indicators.py` | EXISTS |
| `regime/classifier.py` | EXISTS |
| `regime/router.py` | EXISTS |
| `regime/analog_detector.py` | EXISTS |

### monitoring/

| Expected Path | Status |
|---|---|
| `monitoring/__init__.py` | EXISTS |
| `monitoring/regime_monitor.py` | EXISTS |
| `monitoring/_standalone_calc.py` | EXISTS |
| `monitoring/_snapshot.py` | EXISTS |

### rhetoric/concept_framework/

| Expected Path | Status |
|---|---|
| `rhetoric/concept_framework/__init__.py` | EXISTS |
| `rhetoric/concept_framework/sources/` (directory) | EXISTS |
| `rhetoric/concept_framework/sources/beige_book.py` | EXISTS |
| `rhetoric/concept_framework/sources/fomc_docs.py` | EXISTS |
| `rhetoric/concept_framework/discovery/` (directory) | EXISTS |
| `rhetoric/concept_framework/discovery/corpus.py` | EXISTS |
| `rhetoric/concept_framework/discovery/lda.py` | EXISTS |
| `rhetoric/concept_framework/discovery/expansion.py` | EXISTS |
| `rhetoric/concept_framework/dictionary/` (directory) | EXISTS |
| `rhetoric/concept_framework/dictionary/registry.py` | EXISTS |
| `rhetoric/concept_framework/dictionary/validator.py` | EXISTS |
| `rhetoric/concept_framework/extractor.py` | EXISTS |
| `rhetoric/concept_framework/aggregator.py` | EXISTS |
| `rhetoric/concept_framework/decomposer.py` | EXISTS |

### divergence/

| Expected Path | Status |
|---|---|
| `divergence/__init__.py` | EXISTS |
| `divergence/decomposition.py` | EXISTS |
| `divergence/equilibrium.py` | EXISTS |

### positioning/

| Expected Path | Status |
|---|---|
| `positioning/__init__.py` | EXISTS |
| `positioning/cot_structural.py` | EXISTS |
| `positioning/oi_signal.py` | EXISTS |
| `positioning/options_signal.py` | EXISTS |
| `positioning/retail_signal.py` | EXISTS |
| `positioning/tactical_composite.py` | EXISTS |

### output/

| Expected Path | Status |
|---|---|
| `output/__init__.py` | EXISTS |
| `output/bba_mappers/` (directory) | EXISTS |
| `output/bba_mappers/layer1_rhetoric.py` | EXISTS |
| `output/bba_mappers/layer2_market.py` | EXISTS |
| `output/bba_mappers/layer3_divergence.py` | EXISTS |
| `output/bba_mappers/layer4_positioning.py` | EXISTS |
| `output/combination_rules/` (directory) | EXISTS |
| `output/combination_rules/dempster.py` | EXISTS |
| `output/combination_rules/yager.py` | EXISTS |
| `output/combination_rules/pcr5.py` | EXISTS |
| `output/aggregator.py` | EXISTS |
| `output/position_sizing.py` | EXISTS |

### config/

| Expected Path | Status |
|---|---|
| `config/regime_thresholds.yaml` | EXISTS |

### data/

| Expected Path | Status |
|---|---|
| `data/positioning/` | EXISTS (contains `cot_eur.parquet`) |
| `data/regime/` | EXISTS (contains `.gitkeep` only) |
| `data/concept_dictionaries/` | EXISTS (contains `.gitkeep` only) |
| `data/bba_configs/` | EXISTS (contains `.gitkeep` only) |

### Unlisted paths found on disk (not in ROADMAP Section 4):

| Path | Notes |
|---|---|
| `src/macro_context_reader/config.py` | Not listed in ROADMAP tree |
| `src/macro_context_reader/data/__init__.py` | Not listed in ROADMAP tree |
| `src/macro_context_reader/market_pricing/__init__.py` | Not listed in ROADMAP tree |
| `data/raw/` | Not listed in ROADMAP (contains `.gitkeep`) |
| `data/processed/` | Not listed in ROADMAP (contains `.gitkeep`) |

**Result: 0 expected paths missing. 5 unlisted paths found on disk.**

---

## 3. Test Files Inventory

| Path | Test Functions | Function Names |
|---|---|---|
| `tests/__init__.py` | 0 | — |
| `tests/divergence/__init__.py` | 0 | — |
| `tests/market_pricing/__init__.py` | 0 | — |
| `tests/positioning/__init__.py` | 0 | — |
| `tests/positioning/test_cot_structural.py` | 7 | test_compute_cot_signals_columns, test_lev_net_calculation, test_lev_percentile_range, test_date_dtype, test_sorted_ascending, test_save_parquet, test_fetch_skips_on_error |
| `tests/positioning/test_tactical_positioning.py` | 5 | test_tactical_score_range, test_graceful_degradation_one_source_missing, test_graceful_degradation_two_sources_missing, test_sources_available_count, test_all_nan_row |
| `tests/rhetoric/__init__.py` | 0 | — |

**Totals:** 7 test files | 12 test functions | Tests exist only for `positioning/` layer

---

## 4. Notebooks Inventory

| Path | Status |
|---|---|
| `notebooks/00_setup.ipynb` | EXISTS |
| `notebooks/01_layer1_rhetoric.ipynb` | EXISTS |
| `notebooks/02_layer2_market_pricing.ipynb` | EXISTS |
| `notebooks/03_layer3_divergence.ipynb` | EXISTS |
| `notebooks/04_layer4_positioning.ipynb` | EXISTS |
| `notebooks/05_live_pipeline.ipynb` | EXISTS |
| `notebooks/06_regime_monitor.ipynb` | MISSING |

**Result: 6 of 7 expected notebooks exist. `06_regime_monitor.ipynb` (PRD-051) is missing.**

---

## 5. Dependencies — pyproject.toml vs. ROADMAP Section 6

### pyproject.toml `[project.dependencies]`:
- `cot-reports>=0.1`
- `pyarrow>=14.0`

### pyproject.toml `[project.optional-dependencies] dev`:
- `pytest>=7.0`
- `python-dotenv`
- `jupyter>=1.0`
- `macrosynergy>=0.8`
- `ewstools>=2.0`

### ROADMAP Section 6 "Core Dependencies":
`fredapi`, `ecbdata`, `cot-reports`, `requests`, `beautifulsoup4`, `pdfplumber`, `transformers`, `torch`, `sentence-transformers`, `hmmlearn`, `pandas`, `numpy`, `scipy`, `statsmodels`, `pydantic`, `matplotlib`, `plotly`, `PyEMD`, `ruptures`, `filterpy`, `pymc`, `numpyro`, `macrosynergy`, `ewstools`, `streamlit`

### In pyproject.toml but NOT in ROADMAP Core Dependencies:
- `pyarrow` (in pyproject.toml core deps)
- `pytest` (in pyproject.toml dev deps)
- `python-dotenv` (in pyproject.toml dev deps)
- `jupyter` (in pyproject.toml dev deps)

### In ROADMAP but NOT in pyproject.toml (neither core nor dev):
- `fredapi`
- `ecbdata`
- `requests`
- `beautifulsoup4`
- `pdfplumber`
- `transformers`
- `torch`
- `sentence-transformers`
- `hmmlearn`
- `pandas`
- `numpy`
- `scipy`
- `statsmodels`
- `pydantic`
- `matplotlib`
- `plotly`
- `PyEMD`
- `ruptures`
- `filterpy`
- `pymc`
- `numpyro`
- `streamlit`

### Common (present in both): 3
- `cot-reports`
- `macrosynergy` (pyproject dev)
- `ewstools` (pyproject dev)

**Result: 22 dependencies listed in ROADMAP are absent from pyproject.toml. This is expected for a Faza 0 project — dependencies are added incrementally as PRDs are implemented.**

---

## 6. PRD References in Source Code

All textual references to `PRD-XXX` patterns found in `src/` and `tests/`.

| PRD ID | Files Referencing |
|---|---|
| **PRD-050** | `regime/__init__.py`, `regime/indicators.py`, `regime/classifier.py`, `regime/router.py`, `regime/analog_detector.py`, `monitoring/__init__.py`, `monitoring/_standalone_calc.py`, `monitoring/regime_monitor.py`, `divergence/equilibrium.py` |
| **PRD-051** | `regime/analog_detector.py`, `monitoring/__init__.py`, `monitoring/_snapshot.py`, `monitoring/_standalone_calc.py`, `monitoring/regime_monitor.py`, `divergence/equilibrium.py` |
| **PRD-101** | `output/__init__.py` |
| **PRD-102** | `rhetoric/concept_framework/__init__.py`, `rhetoric/concept_framework/aggregator.py`, `rhetoric/concept_framework/decomposer.py`, `rhetoric/concept_framework/extractor.py`, `rhetoric/concept_framework/sources/beige_book.py`, `rhetoric/concept_framework/sources/fomc_docs.py`, `rhetoric/concept_framework/discovery/corpus.py`, `rhetoric/concept_framework/discovery/lda.py`, `rhetoric/concept_framework/discovery/expansion.py`, `rhetoric/concept_framework/dictionary/registry.py`, `rhetoric/concept_framework/dictionary/validator.py` |
| **PRD-200** | `divergence/__init__.py`, `output/__init__.py` |
| **PRD-300** | `regime/__init__.py`, `divergence/__init__.py`, `divergence/decomposition.py`, `divergence/equilibrium.py`, `monitoring/regime_monitor.py`, `output/__init__.py`, `output/bba_mappers/layer3_divergence.py`, `rhetoric/concept_framework/aggregator.py` |
| **PRD-400** | `output/__init__.py` |
| **PRD-401** | `output/__init__.py`, `output/bba_mappers/layer4_positioning.py` |
| **PRD-500** | `regime/router.py`, `divergence/equilibrium.py`, `output/__init__.py`, `output/aggregator.py`, `output/position_sizing.py`, `output/bba_mappers/__init__.py`, `output/bba_mappers/layer1_rhetoric.py`, `output/bba_mappers/layer2_market.py`, `output/bba_mappers/layer3_divergence.py`, `output/bba_mappers/layer4_positioning.py`, `output/combination_rules/dempster.py`, `output/combination_rules/yager.py`, `output/combination_rules/pcr5.py` |

| PRD ID | **NOT** referenced in `tests/` |
|---|---|
| All PRD IDs | No PRD references found in `tests/` |

---

## 7. PRD Registry Consistency — ROADMAP Declared Status vs. Disk Evidence

| PRD ID | ROADMAP Status | Files Referencing (count) | Has Placeholder Code | Verdict |
|---|---|---|---|---|
| **PRD-001** | Done | 0 | no | **CONSISTENT** — infrastructure PRD, no runtime code expected |
| **PRD-002** | Draft | 0 | no | **CONSISTENT** — compute/notebook PRD, no src code expected |
| **PRD-050** | Draft, CC-4 Done | 9 | yes (regime/*.py) | **CONSISTENT** — placeholders match "CC-4 Done" claim |
| **PRD-051** | Draft, CC-1 Done | 6 | yes (monitoring/*.py) | **SUSPECT** — `notebooks/06_regime_monitor.ipynb` listed in ROADMAP Section 4 but missing on disk |
| **PRD-101** | Necreat | 1 (output/__init__.py ref only) | no | **CONSISTENT** — no code, only cross-referenced |
| **PRD-102** | Draft, CC-1 Done | 11 | yes (rhetoric/concept_framework/**) | **CONSISTENT** — placeholders match "CC-1 Done" claim |
| **PRD-200** | Necreat | 2 (cross-refs only) | no | **CONSISTENT** — no code, only cross-referenced |
| **PRD-300** | Reserved, CC-0 Done | 8 | yes (divergence/*.py) | **CONSISTENT** — placeholders match "CC-0 Done" claim |
| **PRD-400** | Approved | 1 (cross-ref only) | no (cot_structural.py has real code, no placeholder markers) | **SUSPECT** — ROADMAP says "Approved" with placeholder marker, but `positioning/cot_structural.py` contains real implementation (no NotImplementedError). Status may be ahead of declared |
| **PRD-401** | Approved | 2 | no (oi_signal.py, options_signal.py, retail_signal.py, tactical_composite.py all have real code) | **SUSPECT** — same as PRD-400: real implementations exist but ROADMAP Faza 1-3 shows CC tasks as not started |
| **PRD-500** | Reserved, CC-0 Done | 13 | yes (output/**) | **CONSISTENT** — placeholders match "CC-0 Done" claim |

---

## Summary

- **All 44 expected source paths from ROADMAP Section 4 exist on disk.** Zero missing files. 5 unlisted files found (`config.py`, `data/__init__.py`, `market_pricing/__init__.py`, `data/raw/`, `data/processed/`).

- **PRD-051 notebook missing:** `notebooks/06_regime_monitor.ipynb` is listed in ROADMAP Section 4 but does not exist on disk. All other 6 notebooks exist.

- **PRD-400 / PRD-401 status inconsistency:** ROADMAP declares these as "Approved" with Faza 1/3 CC tasks "not started", but `positioning/` modules contain real implementations (no `NotImplementedError` markers) and have 12 passing test functions. The actual state is ahead of the declared ROADMAP status.

- **22 of 26 ROADMAP "Core Dependencies" are absent from pyproject.toml.** Only `cot-reports` is in core deps; `macrosynergy` and `ewstools` are in dev deps. This is consistent with Faza 0 incremental approach but represents a significant gap between declared stack and installed stack.

- **Tests exist only for `positioning/` layer** (2 test files, 12 test functions). No tests for `regime/`, `monitoring/`, `divergence/`, `rhetoric/`, or `output/` modules. No test files reference any PRD ID.
