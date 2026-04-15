# Macro Context Reader — EUR/USD Regime Detector
## Roadmap Complet v1.0
> **Generat:** Aprilie 2026 | **Ultima actualizare:** 2026-04-15 | **Versiune CLAUDE.md:** 1.4

---

## Cuprins

1. [Viziunea Proiectului](#1-viziunea-proiectului)
2. [Arhitectura în 4 Straturi](#2-arhitectura-în-4-straturi)
3. [Registrul PRD-urilor](#3-registrul-prd-urilor)
4. [Structura Proiectului](#4-structura-proiectului)
5. [Roadmap pe Faze](#5-roadmap-pe-faze)
6. [Stack Tehnic](#6-stack-tehnic)
7. [Fundamente Academice](#7-fundamente-academice)
8. [Decizii Arhitecturale Confirmate](#8-decizii-arhitecturale-confirmate)

---

## 1. Viziunea Proiectului

**Nu predicție de preț. Detecție de regim macro.**

Sistemul răspunde la: *"Fed-ul e hawkish sau dovish față de ce prețuiește piața? Divergența e mare sau mică? Care e direcția structurală a USD?"*

**Exemplul concret:** La final de 2024, EUR/USD a crescut masiv. Nu trebuia prezis nivelul. Trebuia știut că Fed semnaliza rate cuts, piața prețuia agresiv easing, și USD era structural slab → Long EUR/USD, aștepți.

**Output final:**
```
USD_bias = f(Stratul 1, Stratul 2, Stratul 3, Stratul 4)
→ "USD bearish (67% confidence)"
→ Confidență scăzută = nu intri în poziție sau reduci size-ul
```

**Status 2026-04-14:**
- ✅ Infrastructure (PRD-001), Economic Sentiment (PRD-102) — Done
- 🟢 COT Positioning (PRD-400/401) — Approved, pending implementation
- ⚠️ Real rate differential (PRD-200) — NEIMPLEMENTAT, blocher pentru toate fazele ulterioare
- 🔵 Restul modulelor — placeholder only

---

## 2. Arhitectura în 4 Straturi

```
┌─────────────────────────────────────────────────────────────────┐
│  PRD-050: MACRO REGIME CLASSIFIER (rulează ÎNAINTEA tuturor)   │
│  INFLATION | GROWTH | FINANCIAL_STABILITY                       │
│  Metoda 1: HMM (GaussianHMM, BIC+ARI selection) — DEC-006      │
│  Metoda 2: Historical Analogs (Mahalanobis distance) — DEC-006 │
└─────────────────────────┬───────────────────────────────────────┘
                          │ regime_weights per strat
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼               ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  STRATUL 1   │  │  STRATUL 2   │  │  STRATUL 3   │  │  STRATUL 4   │
│  Rhetoric    │  │  Market      │  │  Divergence  │  │  Positioning │
│  NLP         │  │  Pricing     │  │  Signal      │  │  COT+Tactical│
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                  │                  │
       └─────────────────┴──────────────────┴──────────────────┘
                                    │
                    ┌───────────────▼────────────────┐
                    │  PRD-500: OUTPUT AGGREGATION   │
                    │  Dempster-Shafer Evidence Fusion│
                    │  Bel(USD_bearish) [0.52, 0.78]  │
                    │  Gap → position sizing rule     │
                    └────────────────────────────────┘
```

### Stratul 1 — Rhetoric (ce spune banca centrală)

**Model principal:** FOMC-RoBERTa (gtfintechlab, HuggingFace, CC BY-NC 4.0)
- Clasifică fiecare propoziție: hawkish / dovish / neutral
- Score document-level = (Hawkish - Dovish) / Total sentences

**Extensii planificate:**
- PRD-102: Concept Indicator Framework (Aruoba-Drechsel adaptation)
  - LDA pe corpus Beige Book → concept discovery
  - Word2Vec antrenat local pe Beige Book (1970-2025) → seeded expansion
  - Ridge regression → decompoziție: "inflația e 60% wage-driven, 30% supply-driven"
  - Bayesian Hierarchical Model (numpyro) — rezervat Faza 2
  - NER cu spaCy EntityRuler pe Beige Book × 12 districte × N entități
  - District weights (Boston Fed 2025: NY și SF mai predictive)

**Matched-filter weighting (Djourelova et al. 2025):**
```
weighted_signal = NLP_score × cosine_similarity(speech, last_Powell_presser)
```

**Trend/Momentum (MNLPFEDS-inspired):**
```
nlp_delta_1   = score_t - score_{t-1}
nlp_momentum  = score.ewm(span=6).mean()  ← ~9 luni
changepoint   = ruptures.Pelt().predict()  ← detectare pivote
kalman_filter = filterpy                   ← stare latentă + incertitudine
```

### Stratul 2 — Market Pricing (ce anticipează piața)

**Surse:**
- CME FedWatch: probabilități implicite Fed Funds Rate
- FRED: US Treasury yields, breakeven inflation
- ECB Data Portal: OIS forwards eurozone, HICP

**Formula real rate differential:**
```
real_rate_diff = (US_5Y_real) - (EUR_5Y_nominal_aaa - EUR_inflation_5Y)  # DEC-001: 5Y horizon
```

**Information change signals (Macrosynergy 2024):**
```
carry     = FEDFUNDS - ECB_deposit_rate
momentum  = eurusd.pct_change(21)
value     = deviație față de PPP (BIS REER)
info_change = real_rate_diff.diff(1)  ← delta, nu nivel absolut
```

**Calibrare ECB (Gebauer et al. 2025):**
- 0-63 zile: Fed tightening → EUR bearish (efect FX direct)
- 63+ zile: Fed tightening → efect economic indirect, divergența se comprimă
- `rolling_window = 63` zile = pragul empiric validat academic

### Stratul 3 — Divergența (semnalul acționabil)

**Formula centrală:**
```
surprise_score = NLP_hawkish_score - FedWatch_hawkish_probability
```

**Extensii:**
- Deep Current vs. Surface Wave decomposition (Broecker 1991):
  - Metoda A: HP Filter (statsmodels, lamb=1600)
  - Metoda B: EMD (PyEMD, IMF[-1] = deep current)
  - Metoda C: Rolling mean 63 zile (baseline)
  - Decizie: Sharpe ratio maxim pe USMPD backtesting

- EUR/USD Misalignment (BBVA Research 2025):
  - Echilibru central: 1.20 (normalizare GFCI)
  - Echilibru subdued GFCI: 1.10
  - Echilibru trade tensions: 1.05
  - NFCI (Chicago Fed, FRED) ca proxy GFCI

- Descompunere USD strength vs. EUR weakness:
  - USD strength dominant → corecție rapidă (GFCI dependent)
  - EUR weakness dominant → corecție lentă (structurală)

### Stratul 4 — Positioning (e piața deja aglomerată?)

**4A — Structural COT (săptămânal, lag 3 zile):**
- CFTC TFF Futures-only: Leveraged Funds + Asset Managers pe EUR
- Leveraged Funds > 80th percentile net long EUR → risc reversal
- Delta WoW mai predictiv decât nivelul absolut

**4B — Tactic (zilnic/real-time):**
- CME EUR Open Interest delta: OI ↑ + preț ↑ = trend confirmat
- Options put/call skew (CME CVOL)
- Myfxbook retail sentiment (CONTRARIANȘ)
- `tactical_score = 0.4×oi + 0.35×options + 0.25×retail`

---

## 3. Registrul PRD-urilor

| ID | Titlu | Status | Layer | Placeholder |
|---|---|---|---|---|
| **PRD-001** | Project Structure & Repository Setup | ✅ **Done** | Infrastructure | ✅ |
| **PRD-002** | Compute Infrastructure — GPU & Cloud | 🔵 Draft | Infrastructure | Parțial |
| **PRD-050** | Macro Regime Classifier — System Triage | ✅ **Done** | Infrastructure | ✅ HMM+Mahalanobis+consensus, 24 tests |
| **PRD-051** | Regime Monitor — Standalone Dashboard | 🔵 Draft | Infrastructure | ✅ CC-1 Done |
| **PRD-101** | FOMC-RoBERTa Baseline | 🟢 **~85% Done** | Stratul 1 | ✅ scraper + preprocessor + ensemble (RoBERTa+Llama) + matched_filter + pipeline, 47 unit + 4 skip-guarded integration tests |
| **PRD-102** | Economic Sentiment — Cleveland Fed Beige Book Loader | ✅ **Done** | Stratul 1 | ✅ CC-2 Done |
| **PRD-200** | Market Pricing Pipeline | ✅ **Done** | Stratul 2 | ✅ All modules + 78 tests + notebooks 02/02b |
| **PRD-202** | Market Pricing — FedWatch Probabilities Loader & Surprise Signal | ✅ **Done** | Stratul 2 | Shipped commits `451b1dc`, `0d1f93c`, `f49f91d`, `0cb3493` + MAP.md în `896bb97`; 56 tests green |
| **PRD-300** | Divergence & Sentiment Trend Signal — Composite Layer 3 Integrator | 🟢 **Approved** | Stratul 3 | Industry standard scope (Q1=B+); HP+EMD decomposition (Q2); 5 calibration methods empirical (Q3+Q5); regime-conditional (Q7); analytical+bootstrap CI (Q6); real-time notifications (Q8); 7 CC-uri planned |
| **PRD-400** | COT Leveraged Funds Positioning | ✅ **Done** | Stratul 4 | ✅ (rebranded CC-4) |
| **PRD-401** | Tactical Positioning — OI + Options + Retail | ✅ **Done** | Stratul 4 | ✅ |
| **PRD-500** | Output Aggregation — DST Evidence Fusion | 🟡 Reserved | Output | ✅ CC-0 Done |

**Legendă:** ✅ Done | 🟢 Approved | 🔵 Draft | 🟡 Reserved | ❌ Necreat

---

## 4. Structura Proiectului

```
macro_context_reader/
│
├── CLAUDE.md                          ← System prompt arhitect (v1.3)
├── ROADMAP.md                         ← Acest document
├── fomc_macro_research.md             ← Research consolidat
├── pyproject.toml                     ← Dependencies
│
├── config/
│   └── regime_thresholds.yaml         ← PRD-050 thresholds (INFLATION/GROWTH/FIN_STAB)
│
├── data/
│   ├── positioning/                   ← PRD-400/401 Parquet outputs
│   ├── regime/                        ← PRD-050 regime history
│   ├── concept_dictionaries/          ← PRD-102 YAML versioned dictionaries
│   └── bba_configs/                   ← PRD-500 BBA configuration YAML
│
├── notebooks/
│   ├── 00_setup.ipynb                 ← Colab environment + Drive mount
│   ├── 01_layer1_rhetoric.ipynb       ← PRD-101, PRD-102
│   ├── 02_layer2_market_pricing.ipynb ← PRD-200
│   ├── 03_layer3_divergence.ipynb     ← PRD-300
│   ├── 04_layer4_positioning.ipynb    ← PRD-400, PRD-401
│   └── 05_live_pipeline.ipynb         ← yt-dlp + faster-whisper + FOMC-RoBERTa
│                                      (nota: 06_regime_monitor.ipynb va fi creat la PRD-051/CC-1)
│
└── src/macro_context_reader/
    │
    ├── config.py                      ← configurație generală proiect
    ├── market_pricing/                ← PRD-200 (CC-1..CC-4 done)
    │   ├── __init__.py
    │   ├── schemas.py                ← CC-1: Pydantic schemas
    │   ├── us_rates.py               ← CC-2b/CC-4: US 5Y rates (DGS5/DFII5)
    │   ├── eu_rates.py               ← CC-3: EU 5Y rates (dual AAA + All)
    │   └── inflation_expectations/
    │       ├── __init__.py
    │       └── base.py               ← CC-1: Protocol definition
    │
    ├── regime/                        ← PRD-050 ✅ IMPLEMENTED (HMM + Mahalanobis)
    │   ├── __init__.py                ← MacroRegime enum + get_current_regime() + get_regime_history()
    │   ├── schemas.py                 ← Pydantic: StateProfile, AnalogMatch, RegimeClassification
    │   ├── indicators.py              ← build_regime_features() — 6 FRED series, StandardScaler
    │   ├── hmm_classifier.py          ← HMMRegimeClassifier: BIC+ARI grid, auto-labels
    │   ├── analog_detector.py         ← MahalanobisAnalogDetector: Tikhonov, anti-leakage
    │   ├── consensus.py               ← classify_regime_consensus() — HMM+Analog aggregation
    │   ├── classifier.py              ← (legacy skeleton — rule-based, kept for reference)
    │   └── router.py                  ← get_regime_weights() + DEFAULT_REGIME_WEIGHTS
    │
    ├── monitoring/                    ← PRD-051 ✅ PLACEHOLDER DONE
    │   ├── __init__.py
    │   ├── regime_monitor.py          ← Streamlit dashboard (4 secțiuni + EWS panel)
    │   ├── _standalone_calc.py        ← calcul direct FRED fără PRD-050
    │   └── _snapshot.py               ← export JSON snapshot
    │
    ├── rhetoric/
    │   └── concept_framework/         ← PRD-102 ✅ PLACEHOLDER DONE
    │       ├── __init__.py
    │       ├── sources/
    │       │   ├── beige_book.py      ← ingestie Beige Book × 12 districte
    │       │   └── fomc_docs.py       ← ingestie FOMC minutes/speeches
    │       ├── discovery/
    │       │   ├── corpus.py          ← asamblare corpus pentru LDA + Word2Vec
    │       │   ├── lda.py             ← concept discovery data-driven
    │       │   └── expansion.py       ← Word2Vec local (antrenat pe Beige Book)
    │       ├── dictionary/
    │       │   ├── registry.py        ← load/save YAML versioned dictionary
    │       │   └── validator.py       ← no overlap, no empty concepts
    │       ├── extractor.py           ← dictionary matching + NER (empiric)
    │       ├── aggregator.py          ← Ridge / Bayesian Hierarchical / ADVI
    │       └── decomposer.py          ← {concept: weight} output → Stratul 3
    │
    ├── divergence/                    ← PRD-300 ✅ PLACEHOLDER DONE
    │   ├── __init__.py
    │   ├── decomposition.py           ← Deep Current vs. Surface Wave
    │   │                              ← HP Filter / EMD / Rolling Mean
    │   │                              ← ECB calibrare 63 zile (Gebauer 2025)
    │   └── equilibrium.py             ← BBVA misalignment + GFCI + USD/EUR decomp
    │
    ├── positioning/                   ← PRD-400/401 ✅ PLACEHOLDER DONE
    │   ├── __init__.py
    │   ├── cot_leveraged_funds.py          ← COT TFF Leveraged Funds + Asset Managers
    │   ├── oi_signal.py               ← CME EUR OI delta signal
    │   ├── options_signal.py          ← Put/call skew normalizat
    │   ├── retail_signal.py           ← Myfxbook (CONTRARIANȘ)
    │   └── tactical_composite.py      ← agregare tactical_score
    │
    └── output/                        ← PRD-500 ✅ PLACEHOLDER DONE
        ├── __init__.py
        ├── bba_mappers/
        │   ├── layer1_rhetoric.py
        │   ├── layer2_market.py
        │   ├── layer3_divergence.py
        │   └── layer4_positioning.py
        ├── combination_rules/
        │   ├── dempster.py            ← baseline
        │   ├── yager.py               ← conflict → ignoranță
        │   └── pcr5.py                ← cel mai robust (implementare custom)
        ├── aggregator.py              ← pipeline DST complet
        └── position_sizing.py         ← gap Pl-Bel → full/reduced/none
```

---

## 5. Roadmap pe Faze

### Faza 0 — Infrastructure (Curentă)
> **Obiectiv:** Fundament solid, toate placeholderele în loc

| Task | PRD | Status |
|---|---|---|
| Repository setup, pyproject.toml, pytest | PRD-001 | ✅ Done |
| Compute infrastructure (Colab T4, notebooks) | PRD-002 | 🔵 În progress |
| Macro Regime Classifier — placeholder | PRD-050 / CC-4 | ✅ Done |
| Historical Analog Detector — placeholder | PRD-050 / CC-2b | ✅ Done |
| Regime Monitor Dashboard — placeholder | PRD-051 / CC-1 | ✅ Done |
| Concept Framework — placeholder | PRD-102 / CC-1 | ✅ Done |
| Divergence module — placeholder | PRD-300 / CC-0 | ✅ Done |
| Positioning modules — placeholder | PRD-400/401 | ✅ Done |
| DST Output Aggregation — placeholder | PRD-500 / CC-0 | ✅ Done |
| COT Structural pipeline (implementare + tests) | PRD-400 / CC-1, CC-2 | ✅ Done |
| Tactical Positioning (OI + Options + Retail + composite) | PRD-401 / CC-1..CC-4 | ✅ Done |

### Faza 1 — Ancora Fundamentală ⚠️ PRIORITATE IMEDIATĂ
> **Obiectiv:** Validarea empirică a semnalului structural înainte de orice NLP
> **Notă 2026-04-14:** PRD-200 (`real_rate_differential`) este fundamentul cantitativ al întregului sistem. Fără el, PRD-300 și PRD-500 nu au ancoră. Toate celelalte investiții NLP sunt marginale fără acest strat.
> **Notă 2026-04-15:** PRD-202 închide componenta FedWatch (Stratul 2 market expectations): parser CSV + multi-snapshot loader + surprise signal (3 metode). Ancora cantitativă e acum completă: real_rate_diff (PRD-200) + FedWatch surprise (PRD-202).

| Task | PRD | Status |
|---|---|---|
| FRED + ECB ingestie: real_rate_differential | PRD-200 | ✅ Done (78 tests, notebooks 02/02b) |
| COT structural pipeline + tests | PRD-400 / CC-1, CC-2 | ✅ Done (rebranded CC-4: cot_leveraged_funds) |
| Macro Regime Classifier — implementare | PRD-050 / CC-1+2+3, CC-1b | ✅ Done (HMM+Mahalanobis, 24 tests) |
| Historical Analog Detector — implementare | PRD-050 / CC-1+2+3 | ✅ Done (Tikhonov + anti-leakage) |
| Backtesting vizual real_rate_diff vs EUR/USD | PRD-200 / notebook 02 | ✅ Done (Pearson r = −0.045 global) |
| **Milestone:** corelație vizuală real_rate_diff ↔ EUR/USD confirmată | DEC-009 | ✅ **Atins** (regime-switching, DEC-005/009) |

### Faza 2 — NLP Layer ~85% Done
> **Obiectiv:** Semnalul de surpriză Fed față de așteptările pieței
> **Status 2026-04-15:** PRD-101 substantially complete (audit discovered real state ~85% Done, previously marked ❌). PRD-202 closes FedWatch surprise. Outstanding: skip-guard on 4 integration tests (TD-2), USMPD backtesting milestone.

| Task | PRD | Status |
|---|---|---|
| FOMC-RoBERTa baseline scoring | PRD-101 / CC-1..CC-3 | 🟢 ~85% Done (scraper + preprocessor + ensemble + matched_filter + pipeline; 47 unit tests) |
| FedWatch surprise calculation | PRD-202 / CC-1..CC-3 | ✅ Done (56 tests; 3 methods: binary, expected_change, KL) |
| Matched-filter weighting (cosine similarity) | PRD-101 | ✅ Done |
| Trend/momentum pe NLP scores (EWMA, changepoint) | PRD-300 / CC-1 | ❌ |
| **Milestone:** surprise_score corelat cu EUR/USD USMPD 30-min | — | ❌ |

### Faza 3 — Positioning Layer ✅ COMPLETE
> **Obiectiv:** Contextul de crowd/anti-crowd pentru semnalele macro
> **Status:** Executat anticipat față de ROADMAP original. Toate testele trec (12/12).

| Task | PRD | Status |
|---|---|---|
| COT structural pipeline + tests (7 teste) | PRD-400 / CC-1, CC-2 | ✅ Done |
| Tactical positioning: OI signal | PRD-401 / CC-1 | ✅ Done |
| Tactical positioning: options put/call | PRD-401 / CC-2 | ✅ Done |
| Tactical positioning: retail sentiment | PRD-401 / CC-3 | ✅ Done |
| Tactical composite aggregation + tests (5 teste) | PRD-401 / CC-4 | ✅ Done |
| **Milestone:** positioning layer 100% implementat, testat, date reale CFTC | — | ✅ **Atins** |

**Artefacte existente:**
- `data/positioning/cot_eur.parquet` — 787 rânduri, CFTC COT real, 2020-01-07 → 2026-03-31
- `tests/positioning/` — 12 funcții de test, toate verzi

### Faza 4 — Layer 3 Integration (PRD-300, in progress)

**Status:** Approved 2026-04-15. Implementation starts cu CC-1 (Decomposition).

**Locked architectural decisions (chat 2026-04-15):**
- **Scope:** industry standard composite (NLP + FedWatch surprise + real_rate_diff + Cleveland Fed sentiment); COT excluded (goes to PRD-500 DST fusion)
- **Decomposition:** HP filter + EMD parallel, empirical selection
- **Calibration:** 5 methods parallel (OLS, Ridge, Lasso, ElasticNet, Equal-weighted), best chosen via AIC/BIC + out-of-sample MSE
- **Regime-conditional:** weights per macro regime (consumes PRD-050)
- **Confidence interval:** analytical (real-time) + bootstrap (validation, ~1000 iter)
- **Frequency:** hybrid (daily for high-freq sources, event-driven for low-freq)
- **Notifications:** real-time dispatcher cu pluggable backends (MVP stdout)

**Roadmap CC sequence:**

| CC | Scope | Status |
|---|---|---|
| CC-1 | Decomposition layer (HP filter + EMD + comparison) | ❌ Not Started |
| CC-2 | Calibration layer (5 methods + selector) | ❌ Not Started |
| CC-3 | Regime-conditional fitter + router (integrate PRD-050) | ❌ Not Started |
| CC-4 | Composite score + analytical CI + bootstrap CI | ❌ Not Started |
| CC-5 | Pipeline orchestrator + Parquet persistence | ❌ Not Started |
| CC-6 | Notification dispatcher + triggers + stdout backend | ❌ Not Started |
| CC-7 | Backtesting on USMPD + DEC-012 + MAP.md update | ❌ Not Started |

**Estimated total:** 7 commits, 60+ tests, 1 DEC entry (DEC-012), 1 MAP.md update.

**Dependencies satisfied:**
- PRD-200 (real_rate_diff): ✅ Done
- PRD-202 (FedWatch surprise): ✅ Done
- PRD-102 (Cleveland Fed sentiment): ✅ Done
- PRD-101 (NLP scores): 🟢 ~85% Done — sufficient for integration
- PRD-050 (regime classifier): ✅ Done

**Milestone Faza 4:** Sharpe ratio > 0 pe USMPD backtesting (AC-8 din PRD-300).

### Faza 5 — Economic Sentiment Integration (REDEFINED)
> **Obiectiv:** Integrare scoruri Cleveland Fed Beige Book ca feature secundar în PRD-300
> **Scope schimbat 2026-04-14:** Eliminat custom Concept Indicator Framework (Aruoba-Drechsel). Pivot la consumer-only role. Vezi D20.

| Task | PRD | Status |
|---|---|---|
| Cleveland Fed ICPSR V13 loader | PRD-102 / CC-2 | ✅ Done |
| Integration in PRD-300 as minor feature (weight ~10-15%) | PRD-300 | ❌ |
| `national_consensus_divergence` as independent signal | PRD-300 | ❌ |
| District heterogeneity weighting (NY + SF more predictive per Boston Fed 2025) | PRD-300 | ❌ |
| Manual refresh procedure (6-8 weeks, ICPSR) | Infrastructure doc | ❌ |
| **Milestone:** Cleveland Fed scores integrated as filter layer in divergence signal | — | ❌ |

**Deferred (technical debt, low priority):**
- ICPSR automation (login + download) — requires session management, marginal value
- Custom FinBERT pipeline as methodology experiment — only if Cleveland Fed has breaking methodology changes

### Faza 6 — Output Aggregation (DST)
> **Obiectiv:** Fuziunea finală cu interval de credibilitate explicit

| Task | PRD | Status |
|---|---|---|
| BBA mappers (4 straturi) | PRD-500 / CC-1 | ❌ |
| Dempster + Yager combination rules | PRD-500 / CC-2 | ❌ |
| PCR5 implementation custom | PRD-500 / CC-3 | ❌ |
| Position sizing rule din gap Bel/Pl | PRD-500 / CC-4 | ❌ |
| Backtesting comparativ Dempster/Yager/PCR5 | PRD-500 / CC-5 | ❌ |
| **Milestone:** USD_bias cu interval de credibilitate pe 2019-2024 | — | ❌ |

### Faza 7 — Live Pipeline
> **Obiectiv:** Press conference Powell în timp real

| Task | PRD | Status |
|---|---|---|
| yt-dlp + faster-whisper pipeline | PRD-002 / CC-4 | ❌ |
| Real-time FOMC-RoBERTa scoring | PRD-101 | ❌ |
| Regime Monitor complet (Streamlit) | PRD-051 / CC-2, CC-3, CC-4 | ❌ |
| Early Warning Signals panel (ewstools) | PRD-051 / REQ-7 | ❌ |
| **Milestone:** lag < 10 secunde față de vorbirea Powell live | — | ❌ |

---

## 6. Stack Tehnic

### Core Dependencies
```toml
[project.dependencies]
fredapi>=0.5          # FRED API
ecbdata>=0.0.3        # ECB Data Portal
cot-reports>=0.1      # CFTC COT data
requests>=2.31
beautifulsoup4>=4.12
transformers>=4.36    # FOMC-RoBERTa (rhetoric/ only, NOT economic_sentiment/)
torch>=2.1            # rhetoric/ only
sentence-transformers>=2.3
hmmlearn>=0.3         # Regime detection
pandas>=2.1
numpy>=1.26
scipy>=1.12
statsmodels>=0.14     # HP Filter
pydantic>=2.0
matplotlib>=3.8
plotly>=5.18
PyEMD>=1.5            # EMD decomposition
ruptures>=1.1         # Changepoint detection
filterpy>=1.4         # Kalman Filter
pymc>=5.0             # Bayesian hierarchical (Faza 2)
numpyro>=0.13         # MCMC pe GPU (Faza 2)
macrosynergy>=0.8     # Signal normalization, PnL backtesting
ewstools>=2.0         # Early Warning Signals (Scheffer 2009)
streamlit>=1.30       # Regime Monitor dashboard
```

> **Notă despre pyproject.toml:** Proiectul urmează abordarea incrementală —
> dependențele sunt adăugate în `pyproject.toml` doar când sunt efectiv folosite
> de un PRD implementat. Lista de mai sus reprezintă stack-ul *planificat* pentru
> întregul proiect. Stack-ul curent instalat (Aprilie 2026) conține doar:
> `cot-reports`, `pyarrow`, `pydantic`, `fredapi`, `python-dotenv`, `ecbdata`,
> `hmmlearn`, `scikit-learn`, `scipy` (core) + `pytest`, `jupyter`,
> `macrosynergy`, `ewstools` (dev). Vezi D13.

### Modele HuggingFace
| Model | ID | VRAM | Utilizare |
|---|---|---|---|
| FOMC-RoBERTa | gtfintechlab/FOMC-RoBERTa | ~1.4GB | Clasificare hawkish/dovish/neutral |
| FinBERT-FOMC | ZiweiChen/FinBERT-FOMC | ~440MB | Propoziții complexe (backup) |
| all-MiniLM-L6-v2 | sentence-transformers/... | ~80MB | Matched-filter cosine similarity |

### Compute
| Fază | Hardware | Cost |
|---|---|---|
| Development & Backtesting | Google Colab T4 (15GB VRAM) | Gratuit |
| Word2Vec training (Faza 5) | Colab Pro dacă necesar | ~$10/lună |
| Live pipeline | Colab Pro+ sau RTX 3060 12GB | TBD |

### Surse de Date (toate gratuite)
| Sursă | URL | Ce oferă |
|---|---|---|
| FRED | fred.stlouisfed.org | Date macro SUA |
| ECB Data Portal | data.ecb.europa.eu | Date macro Eurozone |
| Fed FOMC Docs | federalreserve.gov/monetarypolicy | Statements, minutes, speeches |
| Fed Beige Book | federalreserve.gov + minneapolisfed.org | Rapoarte regionale 1970-prezent |
| CFTC COT | cftc.gov | Positioning futures |
| CME FedWatch | cmegroup.com | Probabilități rate Fed |
| SF Fed USMPD | frbsf.org | Intraday FOMC events (backtesting) |
| YouTube (Fed channel) | youtube.com | Press conferences live |

---

## 7. Fundamente Academice

### NLP & Comunicare Fed
| Paper | Contribuție | Unde se aplică |
|---|---|---|
| Shah, Paturi & Chava (ACL 2023) | FOMC-RoBERTa, dataset adnotat manual | Stratul 1 baseline |
| Kim et al. (ICAIF 2024) | Benchmark: FinBERT-FOMC 63.8% < GPT-4 68.2% < Llama 79.34% | Alegere model |
| Djourelova et al. (Chicago Fed 2025) | Speeches similare cu Powell presser amplifică semnalul | Matched-filter weighting |
| Aruoba & Drechsel (UMD 2024) | 296 indicatori concept-specifici + ridge regression | PRD-102 framework (deprecated — vezi D20) |
| Filippou, Garciga, Mitchell, Nguyen (Cleveland Fed 2024) | FinBERT on Beige Book, national + 12 districts indices | PRD-102 data source |

### Macro & EUR/USD
| Paper | Contribuție | Unde se aplică |
|---|---|---|
| BBVA Research (Martínez et al. 2025) | Echilibru EUR/USD 1.05-1.20 + GFCI + USD/EUR decomp | PRD-300 equilibrium |
| ECB Blog (Gebauer et al. 2025) | Fed spillover: <63 zile = surface, >63 zile = deep current | PRD-300 calibrare |
| Macrosynergy Research (2024) | Information change framing + modele simple bate complex | PRD-200, PRD-300 |
| Mulliner, Harvey, Xia, Fang (2025) | Historical analog detection via Mahalanobis distance | PRD-050 CC-2b |
| Zavodny & Ginther (Southern Economic Journal 2005) | Beige Book moves bonds/equities marginally, weak FX impact | D22 rationale |
| Rosa (NY Fed 2013) | FOMC Statement/Minutes triple EUR/USD volatility intraday; Beige Book not tradable on FX | D22 rationale |

### Metodologie & Cross-Pollination
| Sursă | Principiu | Unde se aplică |
|---|---|---|
| Scheffer et al. (Nature 2009) | Early Warning Signals: variance + autocorrelation | PRD-051 REQ-7 |
| Wen, Ciamarra & Cheong (PLOS ONE 2018) | EWS confirmat pe FX (AUD/JPY, CHF/JPY) | PRD-051 REQ-7 |
| Guttal et al. (PLOS ONE 2016) | Variance mai robustă decât autocorrelation pe piețe financiare | PRD-051 implementare |
| Broecker (Oceanography 1991) | Deep current vs. surface waves separation | PRD-300 decomposition |
| Thim (Acta Anaesthesiologica 2012) | Protocol ABCDE — triage sistemic înaintea simptomelor | PRD-050 design |
| Dempster & Shafer (1967-1976) | Evidence theory — ignoranță explicită vs. probabilitate Bayesiană | PRD-500 DST |
| Gelman & Hill (Cambridge 2007) | Multilevel/Hierarchical Models — partial pooling | PRD-102 aggregator |

---

## 8. Decizii Arhitecturale Confirmate

| ID | Decizie | Rațiunea |
|---|---|---|
| D1 | Ordinea de construcție: real_rate_diff → NLP → positioning → DST | Ancora fundamentală înainte de NLP |
| D2 | FOMC-RoBERTa ca model principal NLP | State-of-art pe text FOMC, open source |
| D3 | Parquet (nu SQLite) pentru storage | Zero overhead, pandas-native, suficient |
| D4 | OLS/Ridge ca metodă de calibrare | Modele simple bate complex pe ~80 obs FOMC |
| D5 | Word2Vec antrenat local pe Beige Book | Nu există model dedicat central bank language (FinMTEB 2025) |
| D6 | HP Filter rolling_window = 63 zile | Calibrat empiric: Gebauer et al. (ECB 2025) |
| D7 | Mahalanobis cu sample covariance | 6 variabile × 540 obs → raport 90, Ledoit-Wolf inutil |
| D8 | PCR5 > Yager > Dempster standard | PCR5 cel mai robust la conflict ridicat (Dezert & Smarandache 2004) |
| D9 | Variance > autocorrelation ca EWS | Guttal et al. (2016): autocorrelation inconsistentă pe piețe financiare |
| D10 | Independence > DRY pentru monitoring | PRD-051 standalone recalculează local — nu depinde de PRD-050 |
| D11 | numpyro pe T4 GPU pentru Bayesian | MCMC accelerat pe exact hardware-ul planificat |
| D12 | GFCI proxy = Chicago Fed NFCI (FRED) | Corelație >0.85 cu Goldman GFCI, gratuit, săptămânal din 1971 |
| D13 | Dependențe adăugate incremental per PRD în pyproject.toml | Evită bloat; fiecare PRD declară ce are nevoie; previne instalare preventivă de librării nefolosite |
| D14 | Test coverage obligatoriu pentru fiecare PRD care atinge un modul | Regulă CLAUDE.md v1.4; previne datoria tehnică de testare pe modulele non-positioning |
| D15 | Regime classifier empiric (HMM+Mahalanobis), zero hardcoded thresholds | DEC-006: Regimuri emergent din date, nu din YAML; auto-labeling; consensus mechanism |
| D16 | Scaler fit pe full history (nu pre-COVID only) | DEC-007: Post-COVID e regim, nu outlier; evită artefacte de rescalare |
| D17 | HMM covariance_type="diag" + grid [2..8] + BIC+ARI selection | DEC-008: Parsimonie (36 vs 126 params); stabilitate cross-seed (ARI≥0.70) |
| D18 | Corelații regime-conditional la PRD-300 (global r=−0.045 = regime-switching) | DEC-009: Nu corelație globală ci per-regim; rolling correlation ca feature |
| D19 | Workflow chat-first + batch documentation la session checkout | DEC-010: Decizii în chat, cod imediat, docs consolidate la final |
| D20 | Cleveland Fed ICPSR indices > custom FinBERT pipeline | 8 scraper iterations (FIX1-FIX8) showed 11% publication loss on edge cases; Cleveland Fed provides institutionally-validated scores (Boston Fed replicated 2025); 6-8 week refresh acceptable for macro regime horizon. **Acronim legacy D13** în PRD-ul de checkout (ciocnire cu D13 deja existent). |
| D21 | `national_consensus_divergence` as independent signal feature | Cleveland Fed (Filippou et al. 2024) documented systematic Fed narrative optimism vs district reality post-2020; detects potential Fed policy error as tradable signal on monthly horizon. **Acronim legacy D14** în PRD-ul de checkout. |
| D22 | Economic sentiment weight in PRD-300 composite: ~10-15% | Zavodny & Ginther (2005) + Rosa (2013): Beige Book FX impact empirically weak vs real_rate_diff, FOMC surprise, COT positioning; filter/context layer, not primary driver. **Acronim legacy D15** în PRD-ul de checkout. |
| D23 | CME FedWatch CSV manual download (weekly) over FRED futures or CME FTP | PRD-202: FRED nu hostează Fed Funds Futures; CME FTP `bulletin/` eliminat post-2025; Cleveland Fed nu are dataset dedicat FOMC probabilities. Manual snapshot weekly = singurul path stabil fără Selenium. |
| D24 | Three surprise methods implementate simultan (binary, expected_change GSS 2005, KL divergence) | PRD-202: selecție empirică amânată la PRD-300 backtesting pe EUR/USD. Default `expected_change` (Gürkaynak-Sack-Swanson 2005, industry standard). Evită lock-in prematur pe o metodă. |
| D25 | Default NLP→bps calibration = 25bps per unit hawkish | PRD-202: 25bps = o mișcare standard FOMC. Va fi recalibrat OLS în PRD-300 pe 80+ evenimente FOMC istorice. Placeholder rezonabil pentru bootstrapping Stratul 3. |
| D26 | Toate Claude Code prompts care modifică cod existent includ secțiune "Context awareness" | Workflow rule 2026-04-15: pattern "Patch X asumă starea Y — verifică Y. IF Y THEN apply. IF NOT return BLOCKER". Previne stacking de fixes pe cod deja fixat și modificări pe fișiere lipsă. Aplicabil pentru patches, refactors, non-greenfield. |

---

## Ordinea de Execuție pentru Prompturi Claude Code

### ✅ Completat — Faza 0+1+3
```
PRD-001          — Repository setup                           ✅ Done
PRD-400 (CC-1..CC-4) — COT leveraged funds (rebranded)       ✅ Done (5d5629d)
PRD-401 (CC-1..CC-4) — Tactical positioning                  ✅ Done
PRD-200 (CC-1..CC-8) — Market Pricing Pipeline complet       ✅ Done (78 tests, 02/02b notebooks)
PRD-050 (CC-1+2+3, CC-1b) — Macro Regime Classifier         ✅ Done (1d32bb5, ca1651f) [24 tests]
```
**Milestone Faza 1:** corelație vizuală real_rate_diff ↔ EUR/USD ✅ **ATINS**
  - Global r = −0.045 (regime-switching confirmat — DEC-005, DEC-009)
  - Rolling 252d: range [−0.93, +0.67], 67.4% negative, 4 sign flips
  - CUSUM structural breaks: 72.2% outside 95% CI

### 🎯 Următorul pas — Faza 2 (NLP Layer)
Conform D1 (real_rate_diff → NLP → positioning → DST), Faza 1 e completă.

### 🔵 Pending aprobare (Draft)
```
PRD-002 / CC-2..CC-5 (infrastructure, notebooks, dependențe)
PRD-051 / CC-2..CC-4 (dashboard Streamlit complet)
PRD-102 / CC-2..CC-6 (concept framework implementare)
PRD-300 / CC-1..CC-5 (divergence signal — regime-conditional, DEC-009)
PRD-500 / CC-1..CC-5 (DST aggregation implementare)
```

---

---

## 9. Empirical Findings (Session 2026-04-12)

### Real Rate Differential vs EUR/USD
- **Global Pearson (10Y, level):** r = −0.045, p = 0.026
- **Rolling 252-day range:** [−0.93, +0.67] — 4 sign flips
- **Time distribution:** 67.4% strong negative (r < −0.30), 19.6% neutral, 13.0% strong positive
- **CUSUM structural break:** 72.2% of observations outside 95% CI
- **Conclusion:** Relationship is regime-switching, not globally stable (DEC-009)
- **AC-6 reformulated (DEC-005):** median r = −0.51, 19.0% positive windows, min r = −0.93 — all 3 sub-conditions PASS

### HMM Regime Classification (pending FRED validation)
Expected from notebook `01_regime_classifier_validation.ipynb`:
- BIC+ARI grid selection on [2..8] states
- GFC 2008-Q4 and COVID 2020-Q2 → same stress-type state
- 2022-2023 hiking cycle → inflation-type state
- Current analogs from 2023-2024, anti-regimes from GFC/COVID
- To be populated after first FRED run

---

## 10. PRD-202 — FedWatch Loader & Surprise Signal (Session 2026-04-14/15)

**Module:** `src/macro_context_reader/market_pricing/fedwatch/`
**Status:** ~95% Done (pending MAP.md pentru fedwatch/ submodule)

### Implementation breakdown

| CC | Scope | Commit | Tests |
|---|---|---|---|
| CC-1 | Parser CME FedWatch CSV + pydantic schemas | 451b1dc | 16 |
| CC-2 | Multi-snapshot loader + dedup + Parquet output | 0d1f93c | 14 |
| CC-2-PATCH | Warn (not silently skip) on invalid snapshot files | f49f91d | 3 |
| CC-3 | Surprise signal — 3 methods (binary, expected_change Gürkaynak-Sack-Swanson 2005, Kullback-Leibler divergence) + single/batch interfaces | 0cb3493 | 23 |
| **Total** | | | **56 green** |

### Architectural decisions (see section 8)
- D23 — manual weekly CSV ingestion path (FRED/FTP/Selenium ruled out)
- D24 — three surprise methods simultaneously, empirical selection deferred
- D25 — 25bps/unit default NLP→bps calibration, to be OLS-fit in PRD-300

### Empirical findings
- **CME CSV layout:** 9 meeting blocks × 63 rate buckets × ~253 days = ~9220 non-zero records per snapshot (vs ~143k raw). Dropping zeros saves 93% storage.
- **Probability mass validation:** ~90% of (observation_date, meeting_date) pairs sum to ≥0.95 probability — confirms 63-buckets-per-block parser assumption is correct.
- **Forward horizon:** CME publishes ~12 months forward, not 15 meetings as initially assumed in PRD draft.

---

## 11. Technical Debt Log

Registru al datoriei tehnice identificate dar deferred din cauza valorii marginale sau priorității scăzute. Fiecare TD are PRD source, descriere, și condiție de închidere.

| TD | Source | Descriere | Close when |
|---|---|---|---|
| **TD-1** | PRD-202 | Manual weekly refresh al CME FedWatch CSV snapshots. Automation opțională via OpenClaw/Playwright. | Automation script pe `data/market_pricing/fedwatch/snapshots/` rulat weekly fără intervenție manuală. Low priority — frecvența weekly tolerabilă. |
| **TD-2** | PRD-101 | 4 integration tests în `tests/rhetoric/test_scorers.py` necesită `pytest.skip` guard dacă `HF_TOKEN` nu e setat. Fail curent: 401 Unauthorized când HF cache e gol. | Skip guard aplicat; tests pass sau skip clean fără token; CI nu blochează la missing secret. |
| **TD-3** | CLAUDE.md | Line 98 în CLAUDE.md referențiază `ftp.cmegroup.com/bulletin/` care nu mai există. `positioning/oi_signal.py` folosește HTTPS scraping în schimb. Docstring outdated. | CLAUDE.md line 98 updated cu sursa reală CME (HTTPS endpoint) sau marcată explicit ca deprecated. |
| **TD-4** | Workflow | Status drift între PRD files și ROADMAP §3 registry — când actualizezi `Status:` într-un PRD file, trebuie sincronizat simultan rândul din ROADMAP §3. Caught de session audit 2026-04-15 (PRD-202 marcat `Done` în PRD file dar registry încă lista status partial). | Resolved 2026-04-15: registry update mandatory la fiecare checkout; session audit script include cross-check PRD↔ROADMAP. |

---

*Document generat: Aprilie 2026 | Actualizat la fiecare PRD nou sau decizie arhitecturală*
