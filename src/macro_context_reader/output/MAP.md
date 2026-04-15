# output / MAP.md

## La ce folosește (în 1 propoziție)
Fuziunea finală Dempster-Shafer a celor 4 straturi → `USD_bias` cu interval de credibilitate [Bel, Pl], gap-ul → regula de position sizing (full/reduced/none).

## Decizii critice documentate
- **D8 — PCR5 > Yager > Dempster standard** (Dezert & Smarandache 2004). PCR5 cel mai robust la conflict ridicat; implementare custom.
- **Dempster & Shafer (1967-1976)** — evidence theory cu ignoranță explicită vs. probabilitate Bayesiană.
- **PRD-500** — output aggregation; Reserved, CC-0 Done (placeholder), CC-1..CC-5 pending.

## Componente

### bba_mappers/ — "Traducătorii layer → BBA"
Per strat, mapare output → Basic Belief Assignment peste frame `{USD_bullish, USD_bearish, Θ}` (unde Θ = ignoranță explicită). Fișiere:
- `layer1_rhetoric.py` — `map_rhetoric_to_bba(...)` (NLP score → BBA)
- `layer2_market.py` — `map_market_to_bba(...)` (real_rate_diff + FedWatch → BBA)
- `layer3_divergence.py` — `map_divergence_to_bba(...)` (surprise + misalignment → BBA)
- `layer4_positioning.py` — `map_positioning_to_bba(...)` (COT + tactical → BBA)

**SE STRICĂ DACĂ:** input-ul unui strat are format schimbat; BBA returnat nu sumează la 1 (violare axiomă); weights per layer nu sunt documentate.

### combination_rules/ — "Cele 3 reguli de combinație"
- `dempster.py` — `combine_dempster(bba_list)` — regula standard (baseline); normalizează prin (1 − K).
- `yager.py` — `combine_yager(bba_list)` — conflict K→ ignoranță (Θ), nu se normalizează.
- `pcr5.py` — `combine_pcr5(bba_list)` — Proportional Conflict Redistribution rule 5 (D8: cel mai robust, implementare custom).

**SE STRICĂ DACĂ:** BBA-urile intrare au frame diferit; Dempster cu K=1 (conflict total) → ZeroDivisionError; PCR5 implementare greșită la redistribuire.

### aggregator.py — "Pipeline-ul DST complet"
`aggregate(layer_outputs, rule='dempster')` — primește dict per layer, aplică mapper corespunzător, combină cu regula aleasă, returnează BBA final.
**SE STRICĂ DACĂ:** un layer lipsește din dict; regula invalidă.

### position_sizing.py — "Gap-ul Bel/Pl → decizie"
`compute_position_signal(bel, pl) -> str` — returnează `full` / `reduced` / `none` pe baza gap-ului și magnitudinii Bel.
**SE STRICĂ DACĂ:** Bel > Pl (violare); thresholds hardcoded incompatibile cu scale-ul BBA.

### `__init__.py` — namespace placeholder

## Lanțul de dependențe

```
Stratul 1    Stratul 2    Stratul 3    Stratul 4
  NLP         Market       Divergence   Positioning
    │            │             │             │
    ▼            ▼             ▼             ▼
bba_mappers/layer1  /layer2   /layer3    /layer4
    │            │             │             │
    └────────────┴──────┬──────┴─────────────┘
                        ▼ [BBA_1, BBA_2, BBA_3, BBA_4]
                   aggregator.py
                        │ (rule: dempster | yager | pcr5)
                        ▼
                combination_rules/*
                        │
                        ▼ BBA_final
                 position_sizing.py
                        │
                        ▼
              {full | reduced | none}
```

## Când ceva nu merge — întrebări de diagnostic

1. **Dempster ZeroDivisionError** → conflict K=1 (evidențe total contradictorii). Fallback: folosește Yager sau PCR5.
2. **BBA nu sumează la 1** → bug în mapper; verifică normalizarea în `bba_mappers/layer*.py`.
3. **position_signal mereu `none`** → thresholds prea strict; review la `position_sizing.py`.
4. **PCR5 lent** → implementare custom, nu vectorizată; pentru >4 surse, profile.
5. **Bel > Pl în rezultat** → violare axiomă DST; bug în combination rule.

## Legătura cu restul proiectului
- **Consumer:** utilizatorul final (decision layer); notebook `notebooks/` (nu există încă pentru output, viitor).
- **Depends on:** toate cele 4 straturi (Stratul 1-4) + `regime/router.py` (regime weights).
- **PRD:** PRD-500 (Reserved, majoritatea pending).

## Limitări cunoscute
- **PRD-500 majoritar placeholder** — `combine_pcr5` e semnătura, logica custom încă nu e fully validated.
- **Weights per layer** — nu sunt calibrate empiric; placeholder.
- **Frame `{bull, bear, Θ}` simplistă** — nu modelează intensitate (`strong_bull` vs `mild_bull`).
- **Position sizing thresholds hardcoded** — nu regime-adaptive.
- **Backtesting Dempster/Yager/PCR5 comparison** pending (PRD-500 / CC-5).
