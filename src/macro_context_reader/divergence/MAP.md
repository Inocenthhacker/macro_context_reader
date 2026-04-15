# divergence / MAP.md

## La ce folosește (în 1 propoziție)
Stratul 3 — semnalul acționabil: descompunere deep current vs surface wave (HP/EMD/rolling), BBVA misalignment cu scenarii GFCI, și corelații regime-conditional între `real_rate_differential` și EUR/USD.

## Decizii critice documentate
- **D6 — HP Filter rolling_window = 63 zile** (calibrat Gebauer et al. ECB 2025: Fed tightening <63 zile = surface, >63 zile = deep current).
- **D12 — GFCI proxy = Chicago Fed NFCI** (FRED, corelație >0.85 cu Goldman GFCI).
- **D18 (DEC-009) — Corelații regime-conditional.** Global r=−0.045 = regime-switching, nu relație stabilă. Folosim rolling correlation ca feature, nu coef global.
- **BBVA Research 2025** — echilibre EUR/USD: 1.20 central, 1.10 subdued GFCI, 1.05 trade tensions.

## Componente

### decomposition.py — "Separatorul deep vs surface"
Funcții publice: `decompose_series(series, method={'hp','emd','rolling'})`, `compute_deep_current_signal(...)`, `is_deep_current_stable(...)`, `compute_decision_signal(...)`, `compute_horizon_adjusted_signal(...)` (aplică D6 — 63 zile threshold), `compare_methods_backtesting(...)` (Sharpe ratio comparison per metodă).
**SE STRICĂ DACĂ:** `statsmodels.tsa.filters.hp_filter` API change; `PyEMD` IMF decomposition returnează zero IMFs (serie prea scurtă); metoda invalidă.

### equilibrium.py — "BBVA misalignment + GFCI"
`get_current_equilibrium(regime, gfci)` → {1.20, 1.10, 1.05}. `compute_misalignment(eurusd, equilibrium)` → deviație. `decompose_eurusd_movement(...)` → {USD_strength_pct, EUR_weakness_pct}. `fetch_gfci_proxy(...)` → NFCI din FRED (D12). `compute_equilibrium_scenario_from_regime(regime)`. `get_equilibrium_signal(...)` API top-level.
**SE STRICĂ DACĂ:** NFCI indisponibil în FRED (foarte puțin probabil, publicat din 1971); regime enum neumapabil la scenariu.

### regime_conditional.py — "Corelații per regim (DEC-009)"
Clase: `RegimeCorrelation`, `RegimeConditionalResults`. Funcții: `load_aligned_data(start)`, `_bootstrap_pearson_ci(...)`, `_permutation_pvalue(...)`, `compute_lead_lag(...)`, `compute_conditional_correlations(...)`. Evaluează corelația real_rate_diff ↔ EUR/USD PER REGIM cu bootstrap CI + permutation p-value.
**SE STRICĂ DACĂ:** date aliniate insuficiente (<30 obs per regim); regim cu o singură observație (bootstrap nu e relevant).

### `__init__.py` — namespace placeholder

## Lanțul de dependențe

```
market_pricing/real_rate_differential    regime/get_regime_history
             │                                       │
             └────────────┬──────────────────────────┘
                          ▼
              regime_conditional.py
              (Pearson per regim,
               bootstrap CI, lead-lag)
                          │
                          ▼
                  conditional_correlations_df

EUR/USD spot (FRED DEXUSEU)
             │
             ▼
     decomposition.py (HP/EMD/rolling, D6 63-day horizon)
             │
             ▼
     deep_current_signal → downstream

regime/get_current_regime    FRED NFCI
             │                   │
             └──────┬────────────┘
                    ▼
           equilibrium.py (BBVA, D12)
                    │
                    ▼
        misalignment + USD/EUR decomposition
```

## Când ceva nu merge — întrebări de diagnostic

1. **HP filter returnează trend flat** → lambda default inadecvat (statsmodels: 1600 quarterly, 129600 daily); verifică scalarea intrare.
2. **EMD zero IMFs** → serie prea scurtă (< ~100 obs) sau constantă.
3. **Regime conditional: toate corelațiile apropiate de zero** → regim nedefinit corect upstream; verifică `regime/consensus.py` output.
4. **NFCI gol** → FRED cere lag 1 săptămână; start prea recent.
5. **Misalignment permanent pozitiv** → echilibru statuat greșit pentru regimul curent.

## Legătura cu restul proiectului
- **Consumer:** `output/bba_mappers/layer3_divergence.py` (DST fusion input).
- **Depends on:** `market_pricing/` (real_rate_diff), `regime/` (regime_history), `statsmodels`, `PyEMD`, `scipy`, FRED prin `fredapi`.
- **PRD:** PRD-300 (Reserved — CC-0 Done, CC-1..CC-5 pending). Statusul actual: scheletul prezent, implementarea completă e Faza 4.

## Limitări cunoscute
- **PRD-300 e parțial implementat** — `decomposition.py`, `equilibrium.py`, `regime_conditional.py` există dar full integration în `composite_divergence_score` e pending (PRD-300 / CC-3, CC-4).
- **HP filter endpoint problem** — recent observations distorsionate; mitigație: folosire rolling 63-day window (D6).
- **EMD non-deterministic** — rezultate depind de seed; pentru prod folosește fixed seed.
- **BBVA equilibria hardcoded** — nu adaptive; regim exotic (ex: geopolitical shock) va greși.
- **NFCI** e weekly, daily feature necesită forward-fill.
