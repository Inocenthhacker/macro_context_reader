# monitoring / MAP.md

## La ce folosește (în 1 propoziție)
Streamlit dashboard (Regime Monitor) care afișează regimul curent, indicatorii FRED, istoricul regimurilor, și (viitor) panoul Early Warning Signals — standalone, recalculează local fără a depinde de `regime/` pentru independence.

## Decizii critice documentate
- **D10 — Independence > DRY pentru monitoring.** PRD-051 standalone recalculează local; nu depinde de output-ul persistent al PRD-050. Justificare: dashboard trebuie să funcționeze chiar dacă pipeline-ul de regime nu a rulat recent.
- **D9 — Variance > autocorrelation ca EWS** (Guttal et al. 2016).
- **REQ-7** — Early Warning Signals panel (ewstools, Scheffer 2009).

## Componente

### regime_monitor.py — "Dashboard-ul principal"
`main()` — entry point Streamlit (`streamlit run regime_monitor.py`). `_detect_mode()` alege între live/cached. Secțiuni: `_render_status_section(regime_data)`, `_render_indicators_section(indicators)`, `_render_history_section(history_df, weights)`, `_render_ews_panel(...)`.
**SE STRICĂ DACĂ:** `streamlit` nu e instalat; `FRED_API_KEY` lipsește; `ewstools` incompatibil cu versiune pandas.

### _standalone_calc.py — "Calculul independent"
`calculate_regime_standalone(...)` — rulează indicators + HMM + analog direct, fără a citi din `data/regime/*.parquet`. Asigură că dashboard-ul funcționează inclusiv când pipeline-ul batch nu a rulat.
**SE STRICĂ DACĂ:** import circular cu `regime/` (nu se folosește `classify_regime_consensus` din exterior, se re-implementează minimal).

### _snapshot.py — "Exportatorul JSON"
`export_snapshot(...)` — serializează starea curentă (regim + indicatori + weights) în JSON pentru logging/debugging.
**SE STRICĂ DACĂ:** tipuri non-JSON-serializable în regime_data (numpy scalars fără `.item()`).

### `__init__.py` — namespace placeholder

## Lanțul de dependențe

```
                 FRED API
                     │
                     ▼
         _standalone_calc.py
         (local regime computation)
                     │
                     ▼
          regime_monitor.py
         (Streamlit UI)
         ├─ _render_status_section
         ├─ _render_indicators_section
         ├─ _render_history_section
         └─ _render_ews_panel (ewstools)
                     │
                     ▼
              _snapshot.py (JSON export)
```

## Când ceva nu merge — întrebări de diagnostic

1. **"ModuleNotFoundError: streamlit"** → instalare `dev` extras lipsă: `pip install -e ".[dev]"`.
2. **Dashboard gol / spinner infinit** → `FRED_API_KEY` lipsește sau invalid; verifică în terminal logs.
3. **EWS panel eroare** → `ewstools` cere numpy/pandas versiuni specifice; verifică compatibilitatea.
4. **History section gol** → interval cerut depășește istoria FRED disponibilă; lărgește.

## Legătura cu restul proiectului
- **Consumer:** utilizatorul (dashboard).
- **Depends on (soft):** indirect pe concepte din `regime/` (aceeași logică HMM+analog), dar implementare duplicată (by design, D10).
- **PRD:** PRD-051 (Draft, CC-1 Done; CC-2..CC-4 pending).

## Limitări cunoscute
- **Duplicare logică HMM** — dacă `regime/hmm_classifier.py` se schimbă semnificativ, `_standalone_calc.py` trebuie sincronizat manual (D10 tradeoff).
- **EWS panel** — ewstools e research-grade; poate avea breaking changes fără notice.
- **Fără authentication** — dashboard e local-only; nu deploy public fără auth layer.
- **Fără caching Streamlit** persistent — recalculează la fiecare refresh browser.
