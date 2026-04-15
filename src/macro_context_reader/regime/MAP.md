# regime / MAP.md

## La ce folosește (în 1 propoziție)
Clasifică regimul macro curent (INFLATION / GROWTH / FINANCIAL_STABILITY / etc.) prin consensul între HMM pe features FRED și Mahalanobis analog detection — rulează ÎNAINTEA celorlalte straturi și emite `regime_weights` care modulează contribuțiile.

## Decizii critice documentate
- **DEC-006 — Regime classifier empiric (HMM + Mahalanobis)**, zero hardcoded thresholds. Regimuri emergent din date, nu din YAML.
- **DEC-007 — Scaler fit pe full history** (nu pre-COVID only). Post-COVID e regim, nu outlier.
- **DEC-008 — HMM `covariance_type="diag"` + grid [2..8] + BIC+ARI selection.** Parsimonie (36 vs 126 params); stabilitate cross-seed (ARI≥0.70).
- **D15/D16/D17** în ROADMAP § 8.

## Componente

### indicators.py — "Aducătorul de features"
Funcție publică: `build_regime_features(start, end, client=None) -> pd.DataFrame`. Descarcă 6 serii FRED (core macro: yields, spreads, inflation, unemployment etc.), resample consistent, `StandardScaler` fit pe full history.
**SE STRICĂ DACĂ:** `FRED_API_KEY` lipsește; FRED redenumește una din cele 6 serii; intervalul e prea scurt pentru scaler stabil.

### hmm_classifier.py — "Motorul probabilistic"
Clasa `HMMRegimeClassifier`: fit `GaussianHMM` pe features scalate, grid search [2..8] states, BIC + ARI cross-seed selection. Auto-labels per stare pe baza mediilor features.
**SE STRICĂ DACĂ:** features conțin NaN (scaler aplicat greșit); ARI < 0.70 pe toate configurațiile (instabilitate cross-seed → date insuficiente); `hmmlearn` API change.

### analog_detector.py — "Găsitorul de regimuri similare"
Clasa `MahalanobisAnalogDetector`: calculează distanțe Mahalanobis cu covariance regularizată (Tikhonov), returnează cele mai apropiate K perioade istorice. Anti-leakage: exclude fereastra ±N zile în jurul datei țintă.
**SE STRICĂ DACĂ:** covariance singular (insuficiente observații vs dimensiuni); date target prea aproape de capete istorice (anti-leakage window goală).

### consensus.py — "Arbitrul final"
`classify_regime_consensus(...)`: agregă HMM + Analog; `_determine_confidence(...)` → HIGH/MEDIUM/LOW pe baza acordului. `get_current_regime()` și `get_regime_history(start, end)` — API-ul public consumat de celelalte module.
**SE STRICĂ DACĂ:** HMM și Analog dau regimuri contradictorii sistematic (data drift); datele istorice lipsesc (first-run fără pre-fit).

### classifier.py — "Legacy (kept for reference)"
Skeleton rule-based vechi. Nu e în uz; păstrat pentru regressions.
**SE STRICĂ DACĂ:** ignorat — nu e chemat nicăieri.

### router.py — "Distribuitorul de greutăți"
`get_regime_weights(regime) -> dict` + `DEFAULT_REGIME_WEIGHTS`. Mapare regim → weight-uri per strat (cât contează Stratul 1 vs 2 vs 3 vs 4 într-un regim INFLATION vs FIN_STAB).
**SE STRICĂ DACĂ:** regim nou adăugat în `MacroRegime` enum fără update în `DEFAULT_REGIME_WEIGHTS`.

### schemas.py — "Dicționarul"
Pydantic: `StateProfile`, `HMMFitDiagnostics`, `AnalogMatch`, `RegimeClassification`. Serializare snapshot-uri + diagnostice.
**SE STRICĂ DACĂ:** adaugi câmp în clasificare fără update în schema.

### `__init__.py` — Surface API
Re-exportă `MacroRegime` enum, `get_current_regime`, `get_regime_history`.

## Lanțul de dependențe

```
       FRED API
           │
           ▼
   indicators.py (build_regime_features, scaler)
           │
           ▼
     ┌─────┴──────┐
     ▼            ▼
hmm_classifier  analog_detector
     │            │
     └──────┬─────┘
            ▼
       consensus.py (classify_regime_consensus)
            │
            ▼
        router.py (get_regime_weights) ──→ layers 1..4
```

## Când ceva nu merge — întrebări de diagnostic

1. **"Regime = UNKNOWN"** → features gol sau scaler nefittat. Verifică interval ≥ 5 ani.
2. **"ARI < 0.70 pe toate k"** → date insuficiente sau prea multe features vs obs. Verifică `build_regime_features` shape.
3. **Analog returnează zero matches** → fereastra anti-leakage consumă toată istoria. Interval prea scurt.
4. **Regim inconsistent cu realitatea economică** → HMM auto-label greșit; inspectează `HMMFitDiagnostics.state_profiles`.

## Legătura cu restul proiectului
- **Consumer:** `divergence/regime_conditional.py` (corelații per regim); `monitoring/regime_monitor.py` (dashboard); `output/aggregator.py` (DST weights per regim).
- **Depends on:** FRED API prin `fredapi`; `hmmlearn`, `scikit-learn`, `scipy`.
- **PRD:** PRD-050 (Done, 24 tests).

## Limitări cunoscute
- HMM GaussianHMM asumă gaussianitate per stare — post-COVID tails violate.
- 6 features fixe — nu se adaugă dinamic fără fit nou.
- Auto-labeling euristic pe medii features — poate confunda INFLATION cu GROWTH când corelate.
- Anti-leakage window hardcoded — nu parametrizat per caller.
