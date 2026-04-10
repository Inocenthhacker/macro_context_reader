# PROJECT_STATE.md — Macro Context Reader
## Snapshot stare reală

> **Ultima actualizare:** 2026-04-11
> **Sursa adevărului:** generat pe baza `audit/STATE_AUDIT_001.md` + `audit/STATE_AUDIT_002.md`
> **Rol:** complementar cu `ROADMAP.md`. ROADMAP = plan. PROJECT_STATE = realitate.
> **Regenerare:** la fiecare milestone sau schimbare de status PRD.

---

## Status Two-Line

**Faza 0 complete.** Positioning layer (PRD-400 + PRD-401) 100% implementat și testat cu date reale CFTC.
**PRD-200 (Market Pricing) In Progress.** CC-1..CC-4 done: US 5Y rates (FRED), EU 5Y rates dual (ECB), Pydantic schemas + validation. CC-5 (SPF inflation expectations) în PHASE 1 discovery complete, PHASE 2 pending.
**Restul layerelor** (regime, monitoring, divergence, rhetoric, output) sunt schelet disciplinat cu 55 funcții `NotImplementedError`, gata de implementare.

---

## 1. Completare per Modul

| Modul | Fișiere | COMPLETE | SKELETON | % | Status PRD |
|---|---|---|---|---|---|
| `positioning/` | 5 | 5 | 0 | **100%** | PRD-400, PRD-401 — ✅ Done |
| `market_pricing/` | 5 | 4 | 1 | **80%** | PRD-200 — 🟢 In Progress (CC-1..CC-4 ✅) |
| `regime/` | 4 | 0 | 4 | 0% | PRD-050 — Draft |
| `monitoring/` | 3 | 0 | 3 | 0% | PRD-051 — Draft |
| `divergence/` | 2 | 0 | 2 | 0% | PRD-300 — Reserved |
| `rhetoric/concept_framework/` | 3 | 0 | 3 | 0% | PRD-102 — Draft |
| `output/` | 9 | 0 | 9 | 0% | PRD-500 — Reserved |

**Overall:** 10 / 32 fișiere COMPLETE = **31% file-level completion**
**Funcții schelet rămase:** 55

---

## 2. Fișiere COMPLETE (Implementare Reală)

| Fișier | Linii | Descriere |
|---|---|---|
| `positioning/cot_structural.py` | 75 | Ingestie COT CFTC Leveraged Funds + Asset Managers, calcul net positions, delta WoW, percentilă 52W |
| `positioning/oi_signal.py` | 62 | Fetch EUR futures Open Interest, calcul semnal OI delta |
| `positioning/options_signal.py` | 59 | Fetch EUR put/call ratio, normalizare, semnal options skew |
| `positioning/retail_signal.py` | 53 | Fetch Myfxbook retail sentiment, semnal contrarianș |
| `positioning/tactical_composite.py` | 85 | Agregare OI + Options + Retail cu graceful degradation la surse lipsă |
| `market_pricing/schemas.py` | ~120 | Pydantic schemas: USRatesRow, EURRatesRow, InflationExpectationRow, MethodMetadata, RealRateDiffRow |
| `market_pricing/us_rates.py` | ~130 | US 5Y rates ingestion FRED (DGS5/DFII5), Pydantic validation, Parquet output |
| `market_pricing/eu_rates.py` | ~180 | EU 5Y rates dual ECB (AAA + All issuers), credit stress spread, Parquet output |
| `market_pricing/inflation_expectations/base.py` | ~60 | Protocol `InflationExpectationsMethod` + base schemas |

---

## 3. Fișiere SKELETON — Grupate pe PRD

### PRD-050 — Macro Regime Classifier (`regime/`)
- `regime/indicators.py` — fetch_triage_indicators
- `regime/classifier.py` — classify_regime, get_current_regime
- `regime/router.py` — get_regime_weights
- `regime/analog_detector.py` — build_macro_vector, build_historical_matrix, compute_distances, find_analogs, compute_regime_distribution, detect_regime_analog

### PRD-051 — Regime Monitor (`monitoring/`)
- `monitoring/_snapshot.py` — export_snapshot
- `monitoring/_standalone_calc.py` — calculate_regime_standalone
- `monitoring/regime_monitor.py` — _detect_mode, _render_status_section, _render_indicators_section, _render_history_section, _render_ews_panel, main

### PRD-102 — Concept Framework (`rhetoric/concept_framework/`)
- `rhetoric/concept_framework/extractor.py` — compute_concept_frequency, compute_concept_subtypes, build_indicator_vector, aggregate_national
- `rhetoric/concept_framework/aggregator.py` — fit, predict
- `rhetoric/concept_framework/discovery/expansion.py` — train_embeddings, expand_concept

### PRD-300 — Divergence Signal (`divergence/`)
- `divergence/decomposition.py` — decompose_series, compute_deep_current_signal, is_deep_current_stable, compute_decision_signal, compute_horizon_adjusted_signal, compare_methods_backtesting
- `divergence/equilibrium.py` — get_current_equilibrium, compute_misalignment, decompose_eurusd_movement, fetch_gfci_proxy, compute_equilibrium_scenario_from_regime, get_equilibrium_signal

### PRD-500 — Output Aggregation (`output/`)
- `output/bba_mappers/layer1_rhetoric.py` — map_rhetoric_to_bba
- `output/bba_mappers/layer2_market.py` — map_market_to_bba
- `output/bba_mappers/layer3_divergence.py` — map_divergence_to_bba
- `output/bba_mappers/layer4_positioning.py` — map_positioning_to_bba
- `output/combination_rules/dempster.py` — combine_dempster
- `output/combination_rules/yager.py` — combine_yager
- `output/combination_rules/pcr5.py` — combine_pcr5
- `output/aggregator.py` — aggregate
- `output/position_sizing.py` — compute_position_signal

---

## 4. Artefacte de Date Existente

| Path | Dimensiune | Rânduri | Perioada | Observații |
|---|---|---|---|---|
| `data/positioning/cot_eur.parquet` | 21.9 KB | 787 | 2020-01-07 → 2026-03-31 | Date CFTC reale, dtypes corecte, percentile normalizate în [0, 1] |
| `data/market_pricing/us_rates.parquet` | ~55 KB | 2817 | 2015-01-02 → 2026-04-08 | DGS5 + DFII5 reale FRED. Coloane: date, us_5y_nominal, us_5y_real, us_5y_breakeven |
| `data/market_pricing/eu_rates.parquet` | ~65 KB | 2874 | 2015-01-02 → 2026-04-09 | ECB Yield Curve AAA + All. Coloane: date, eu_5y_nominal_aaa, eu_5y_nominal_all, eu_credit_stress_5y |

**Directoare data/ goale (cu `.gitkeep`):** `data/regime/`, `data/concept_dictionaries/`, `data/bba_configs/`, `data/raw/`, `data/processed/`

---

## 5. Test Coverage Map

| Modul | Test files | Funcții test | Status | Acoperire |
|---|---|---|---|---|
| `positioning/` | 2 | 12 | ✅ Verde (12/12 pass) | Completă |
| `market_pricing/` | 3 | 30 | ✅ Verde (30/30 pass) | CC-1..CC-4 complete |
| `regime/` | 0 | 0 | ❌ Zero | Datorie tehnică |
| `monitoring/` | 0 | 0 | ❌ Zero | Datorie tehnică |
| `divergence/` | 0 | 0 | ❌ Zero | Datorie tehnică |
| `rhetoric/` | 0 | 0 | ❌ Zero | Datorie tehnică |
| `output/` | 0 | 0 | ❌ Zero | Datorie tehnică |

**Regulă activă (CLAUDE.md v1.4):** orice PRD viitor care atinge un modul cu coverage zero include obligatoriu CC de test. PRD-ul nu poate fi marcat Done până testele nu trec.

---

## 6. Stack Tehnic Instalat vs. Planificat

**Instalat în `pyproject.toml`:**
- Core: `cot-reports>=0.1`, `pyarrow>=14.0`, `pydantic>=2.0`, `fredapi>=0.5`, `python-dotenv>=1.0`, `ecbdata>=0.1.1`
- Dev: `pytest>=7.0`, `python-dotenv`, `jupyter>=1.0`, `macrosynergy>=0.8`, `ewstools>=2.0`

**Planificat (ROADMAP Secțiunea 6) — de adăugat incremental:**
`fredapi`, `ecbdata`, `requests`, `beautifulsoup4`, `pdfplumber`, `transformers`, `torch`, `sentence-transformers`, `hmmlearn`, `pandas`, `numpy`, `scipy`, `statsmodels`, `pydantic`, `matplotlib`, `plotly`, `PyEMD`, `ruptures`, `filterpy`, `pymc`, `numpyro`, `streamlit`

**Decizie:** D13 — dependențele se adaugă per PRD, nu upfront.

---

## 7. Următorul Pas Logic

**PRD-200 (Market Pricing Pipeline) — In Progress.** CC-1..CC-4 done. CC-5 PHASE 1 discovery complete, PHASE 2 pending decizia tenor inflation expectations (SPF.Q.U2.HICP.POINT.LT.Q.AVG ales ca sursă).

**Ordinea recomandată (pașii rămași):**
1. CC-5 PHASE 2: implementare `ecb_spf.py` + teste + DEC-004
2. CC-6: calcul `real_rate_differential` cu teste (dependency injection)
3. CC-7: notebook de validare — plot real_rate_diff vs EUR/USD pe 5 ani
4. Milestone Faza 1: corelație vizuală confirmată

**Faze pending după Faza 1:** Faza 2 (NLP), Faza 4 (Divergence), Faza 5 (Concept), Faza 6 (DST), Faza 7 (Live).

---

## 8. Referințe Audit

- `audit/STATE_AUDIT_001.md` — filesystem vs. ROADMAP Secțiunea 4 reconciliation
- `audit/STATE_AUDIT_002.md` — implementation depth + test execution

*Regenerat la fiecare milestone. Nu edita manual — generează prin Claude Code audit.*
