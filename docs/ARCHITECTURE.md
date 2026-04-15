# Arhitectură — 4 straturi

## Principiul central

**Nu predicție de preț. Detecție de regim.**

Sistemul răspunde la: *"Fed-ul e hawkish sau dovish față de ce prețuiește piața? Care e direcția structurală a USD?"*

Output: `USD_bias` cu interval de credibilitate (Dempster-Shafer). Gap-ul între belief și plausibility → regula de position sizing.

## Diagrama de fluxuri

```
┌──────────────────────────┐  ┌──────────────────────────┐
│ Stratul 1 — RHETORIC     │  │ Stratul 2 — MARKET       │
│ NLP Fed (FOMC-RoBERTa +  │  │ FRED rates + CME         │
│ Llama Ensemble)          │  │ FedWatch + ECB           │
│ → nlp_hawkish_score      │  │ → real_rate_diff,        │
│                          │  │   fedwatch_probabilities │
└────────────┬─────────────┘  └────────────┬─────────────┘
             │                              │
             └──────────────┬───────────────┘
                            ↓
              ┌──────────────────────────┐
              │ Stratul 3 — DIVERGENCE   │
              │ surprise_signal +        │
              │ deep_current vs surface  │
              │ regime_conditional corr  │
              └────────────┬─────────────┘
                           │
              ┌────────────┴─────────────┐
              ↓                           ↓
┌──────────────────────────┐  ┌──────────────────────────┐
│ Stratul 4 — POSITIONING  │  │ Economic Sentiment       │
│ COT + OI + Options       │  │ (Cleveland Fed Beige     │
│ → tactical_score         │  │ Book) — context filter   │
└────────────┬─────────────┘  └────────────┬─────────────┘
             │                              │
             └──────────────┬───────────────┘
                            ↓
              ┌──────────────────────────┐
              │ OUTPUT — DST Fusion      │
              │ Dempster-Shafer evidence │
              │ → USD_bias [confidence]  │
              └──────────────────────────┘
```

## Stratul 1 — Rhetoric (`rhetoric/`)

NLP pe comunicatele Fed: statements, minutes, press conferences, speeches. Scorere multiple (FOMC-RoBERTa, Llama via DeepInfra, FinBERT-FOMC ca backup), agregare prin ensemble cu agreement-based confidence. Matched-filter (cosine similarity cu Powell presser) amplifică semnalele din speeches aliniate cu mesajul oficial.

Vezi [MAP](../src/macro_context_reader/rhetoric/MAP.md).

## Stratul 2 — Market Pricing (`market_pricing/`)

Două componente:
- **Rate differential:** `real_rate_differential = us_5y_real - eu_5y_real` (US TIPS DFII5 + ECB AAA yield curve + SPF inflation expectations). Ancora fundamentală.
- **FedWatch:** probabilități implicite de schimbare Fed Funds Rate din CME snapshots săptămânale.

Vezi [market_pricing/MAP](../src/macro_context_reader/market_pricing/MAP.md) și [fedwatch/MAP](../src/macro_context_reader/market_pricing/fedwatch/MAP.md).

## Stratul 3 — Divergence (`divergence/`)

Formula centrală: `surprise_score = NLP_hawkish - FedWatch_hawkish_prob`. Descompunere deep current vs surface wave (HP filter, EMD, rolling mean). BBVA misalignment. Corelații regime-conditional (DEC-009).

Vezi [MAP](../src/macro_context_reader/divergence/MAP.md).

## Stratul 4 — Positioning (`positioning/`)

- **4A Structural:** CFTC COT Leveraged Funds (săptămânal, lag 3 zile)
- **4B Tactical:** CME EUR Open Interest delta + options put/call skew + Myfxbook retail (contrarian)
- Formula agregare: `tactical_score = 0.4×oi + 0.35×options + 0.25×retail`

Vezi [MAP](../src/macro_context_reader/positioning/MAP.md).

## Cross-cutting modules

- **`regime/`** — Macro regime classifier (HMM + Mahalanobis analog). Rulează ÎNAINTEA celorlalte straturi și generează `regime_weights`.
- **`monitoring/`** — Streamlit dashboard (Regime Monitor).
- **`output/`** — DST evidence fusion (Dempster/Yager/PCR5) + position sizing.
- **`economic_sentiment/`** — Cleveland Fed Beige Book indices (filter layer, ~10-15% weight în PRD-300).

## Design rationale

### De ce 4 straturi separate?
Decoupling. Fiecare strat poate fi:
- Recalibrat independent (ex: schimbi modelul NLP fără să afectezi Stratul 2)
- Validat empiric separat (Sharpe ratio per strat)
- Combinat alternativ (DST permite multiple combination rules)

### De ce DST în loc de Bayesian?
DST permite ignoranță explicită ([Bel, Pl]) când evidența e insuficientă. Bayesian forțează o prior subiectivă și nu distinge "nu știu" de "50-50".

### De ce empirical-first vs theory-first?
Vezi [ROADMAP.md](../ROADMAP.md) secțiunea 8 (Decisions): metodele competing sunt implementate paralel (HP/EMD/rolling, Dempster/Yager/PCR5, 3 surprise methods), selecția e empirică pe backtesting. 80+ FOMC events suficiente pentru OLS calibration.

## Surse de date

| Strat | Sursă | Format | Refresh |
|---|---|---|---|
| 1 | federalreserve.gov (statements, minutes, presser, speeches) | HTML scraping | Per FOMC event |
| 2 | FRED (yields, breakeven, EUR/USD), ECB Data Portal (yield curve, SPF), CME FedWatch CSV | API + manual CSV | Daily / weekly manual |
| 3 | Composite intern (din 1+2) | DataFrame | On demand |
| 4 | CFTC COT (`cot-reports`), CME OI HTML | API + HTTPS scraping | Weekly |
| Sentiment | Cleveland Fed ICPSR (Beige Book FinBERT scores) | CSV manual | 6-8 săptămâni |

## Troubleshooting

### "ModuleNotFoundError: macro_context_reader"
Instalare incompletă. Rulează `pip install -e ".[dev]"` din root.

### Notebook 02 nu plotează nimic
- Verifică `FRED_API_KEY` în `.env`
- Rulează `pytest tests/market_pricing/ -v --tb=short` — dacă fail → setup problem

### "FedWatch data missing for date X"
Snapshot CSV nu acoperă acea dată. Vezi [DATA_REFRESH.md](DATA_REFRESH.md) pentru download manual.

### 401 Unauthorized pe FOMC-RoBERTa / Llama
`HF_TOKEN` / `DEEPINFRA_API_KEY` lipsește sau expirat. Testele de integrare din `tests/rhetoric/test_scorers.py` trebuie să fie skip-guarded (vezi TD-2 în ROADMAP).

### Inner join US ⋈ EU gol
Calendarele FRED și ECB nu se suprapun pe interval (weekend sau holidays mixte). Lărgește `start`/`end`.
