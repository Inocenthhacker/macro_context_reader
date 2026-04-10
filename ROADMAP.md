# Macro Context Reader — EUR/USD Regime Detector
## Roadmap Complet v1.0
> **Generat:** Aprilie 2026 | **Ultima actualizare:** 2026-04-09 | **Versiune CLAUDE.md:** 1.4

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

---

## 2. Arhitectura în 4 Straturi

```
┌─────────────────────────────────────────────────────────────────┐
│  PRD-050: MACRO REGIME CLASSIFIER (rulează ÎNAINTEA tuturor)   │
│  INFLATION | GROWTH | FINANCIAL_STABILITY                       │
│  Metoda 1: Rule-based (thresholds YAML)                        │
│  Metoda 2: Historical Analogs (Mahalanobis distance)           │
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
real_rate_diff = (US_2Y_yield - US_breakeven_2Y) - (EUR_2Y_OIS - EUR_inflation_2Y)
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
| **PRD-050** | Macro Regime Classifier — System Triage | 🔵 Draft | Infrastructure | ✅ CC-4 Done |
| **PRD-051** | Regime Monitor — Standalone Dashboard | 🔵 Draft | Infrastructure | ✅ CC-1 Done |
| **PRD-101** | FOMC-RoBERTa Baseline | ❌ Necreat | Stratul 1 | ❌ |
| **PRD-102** | Concept Indicator Framework (Aruoba-Drechsel) | 🔵 Draft | Stratul 1 | ✅ CC-1 Done |
| **PRD-200** | Market Pricing Pipeline | ❌ Necreat | Stratul 2 | ❌ |
| **PRD-300** | Divergence & Sentiment Trend Signal | 🟡 Reserved | Stratul 3 | ✅ CC-0 Done |
| **PRD-400** | COT Structural Positioning | ✅ **Done** | Stratul 4 | ✅ |
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
    ├── market_pricing/                ← PRD-200 (placeholder director, gol)
    │   └── __init__.py
    │
    ├── regime/                        ← PRD-050 ✅ PLACEHOLDER DONE
    │   ├── __init__.py                ← MacroRegime enum + lazy imports
    │   ├── indicators.py              ← fetch_triage_indicators() din FRED
    │   ├── classifier.py              ← classify_regime() + get_current_regime()
    │   ├── router.py                  ← get_regime_weights() + DEFAULT_REGIME_WEIGHTS
    │   └── analog_detector.py         ← PRD-050/CC-2b: Mahalanobis + historical analogs
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
    │   ├── cot_structural.py          ← COT TFF Leveraged Funds + Asset Managers
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

### Faza 1 — Ancora Fundamentală
> **Obiectiv:** Validarea empirică a semnalului structural înainte de orice NLP

| Task | PRD | Status |
|---|---|---|
| FRED + ECB ingestie: real_rate_differential | PRD-200 (de creat) | ❌ |
| COT structural pipeline + tests | PRD-400 / CC-1, CC-2 | ❌ |
| Macro Regime Classifier — implementare | PRD-050 / CC-1, CC-2, CC-3 | ❌ |
| Historical Analog Detector — implementare | PRD-050 / CC-2b | ❌ |
| Backtesting vizual real_rate_diff vs EUR/USD | PRD-002 | ❌ |
| **Milestone:** corelație vizuală real_rate_diff ↔ EUR/USD confirmată | — | ❌ |

### Faza 2 — NLP Layer
> **Obiectiv:** Semnalul de surpriză Fed față de așteptările pieței

| Task | PRD | Status |
|---|---|---|
| FOMC-RoBERTa baseline scoring | PRD-101 (de creat) | ❌ |
| FedWatch surprise calculation | PRD-200 | ❌ |
| Matched-filter weighting (cosine similarity) | PRD-101 | ❌ |
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

### Faza 4 — Divergence Signal Integration
> **Obiectiv:** Combinarea tuturor semnalelor în composite_divergence_score

| Task | PRD | Status |
|---|---|---|
| Deep Current decomposition (HP/EMD/rolling) | PRD-300 / CC-1, CC-2 | ❌ |
| EUR/USD Misalignment + GFCI (BBVA) | PRD-300 / CC-0c impl. | ❌ |
| composite_divergence_score cu Kalman Filter | PRD-300 / CC-3, CC-4 | ❌ |
| Backtesting comparativ metode pe USMPD | PRD-300 / CC-5 | ❌ |
| **Milestone:** Sharpe ratio > 0 pe USMPD backtesting | — | ❌ |

### Faza 5 — Concept Framework (Beige Book)
> **Obiectiv:** Sub-taxonomia inflației și cauzelor structurale

| Task | PRD | Status |
|---|---|---|
| Beige Book corpus ingestie (Minneapolis Fed archive) | PRD-102 / CC-2 | ❌ |
| Word2Vec antrenat local pe Beige Book | PRD-102 / CC-2 | ❌ |
| LDA concept discovery | PRD-102 / CC-3 | ❌ |
| Seeded expansion cu Word2Vec | PRD-102 / CC-4 | ❌ |
| Extractor + Dictionary YAML | PRD-102 / CC-5 | ❌ |
| Ridge regression aggregator | PRD-102 / CC-6 | ❌ |
| **Milestone:** inflation_decomposition validat pe FOMC cycles 2021-2024 | — | ❌ |

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
pdfplumber>=0.10
transformers>=4.36    # FOMC-RoBERTa
torch>=2.1
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
> `cot-reports`, `pyarrow` (core) + `pytest`, `python-dotenv`, `jupyter`,
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
| Aruoba & Drechsel (UMD 2024) | 296 indicatori concept-specifici + ridge regression | PRD-102 framework |

### Macro & EUR/USD
| Paper | Contribuție | Unde se aplică |
|---|---|---|
| BBVA Research (Martínez et al. 2025) | Echilibru EUR/USD 1.05-1.20 + GFCI + USD/EUR decomp | PRD-300 equilibrium |
| ECB Blog (Gebauer et al. 2025) | Fed spillover: <63 zile = surface, >63 zile = deep current | PRD-300 calibrare |
| Macrosynergy Research (2024) | Information change framing + modele simple bate complex | PRD-200, PRD-300 |
| Mulliner, Harvey, Xia, Fang (2025) | Historical analog detection via Mahalanobis distance | PRD-050 CC-2b |

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

---

## Ordinea de Execuție pentru Prompturi Claude Code

### ✅ Completat
PRD-400 (CC-1, CC-2) — COT structural ✅
PRD-401 (CC-1..CC-4) — Tactical positioning ✅

### 🎯 Următorul pas — Faza 1 (Ancora Fundamentală)
Conform D1 (real_rate_diff → NLP → positioning → DST), Faza 1 este următoarea.
Blocker: **PRD-200 nu există ca document PRD formal.**

Ordinea logică:
1. Creare PRD-200 Draft (Market Pricing Pipeline — FRED + ECB + real_rate_differential)
2. Aprobare PRD-200 → Approved
3. Generare prompturi Claude Code pentru PRD-200 (CC-1 FRED client → CC-2 ECB client → CC-3 real rate differential → CC-4 tests + validation plot)
4. Milestone Faza 1: corelație vizuală real_rate_diff ↔ EUR/USD confirmată

### 🔵 Pending aprobare (Draft)
```
PRD-002 / CC-2..CC-5 (infrastructure, notebooks, dependențe)
PRD-050 / CC-1, CC-2, CC-3 (implementare regime classifier)
PRD-050 / CC-2b implementare (analog detector Mahalanobis)
PRD-051 / CC-1 (notebooks/06_regime_monitor.ipynb creare)
PRD-051 / CC-2..CC-4 (dashboard Streamlit complet)
PRD-102 / CC-2..CC-6 (concept framework implementare)
PRD-300 / CC-1..CC-5 (divergence signal implementare)
PRD-500 / CC-1..CC-5 (DST aggregation implementare)
```

---

*Document generat: Aprilie 2026 | Actualizat la fiecare PRD nou sau decizie arhitecturală*
