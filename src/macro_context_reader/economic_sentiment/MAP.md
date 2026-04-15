# economic_sentiment / MAP.md

## La ce folosește (în 1 propoziție)
Loader pentru indicii Cleveland Fed Beige Book Sentiment (Filippou, Garciga, Mitchell, Nguyen 2024) — scoruri FinBERT pre-computed, national + 12 districte, folosite ca filter layer secundar (~10-15% weight) în PRD-300.

## Decizii critice documentate
- **D20 — Cleveland Fed ICPSR indices > custom FinBERT pipeline.** După 8 iterații scraper (FIX1-FIX8) cu 11% publication loss pe edge cases, pivot la scoruri institutional-validated.
- **D21 — `national_consensus_divergence` ca feature independent.** Cleveland Fed documentează discrepanța Fed narrative vs district reality post-2020.
- **D22 — Economic sentiment weight ~10-15% în PRD-300.** Zavodny & Ginther (2005) + Rosa (2013): Beige Book FX impact empiric slab vs real_rate_diff/FOMC surprise/COT.
- **Sursa:** ICPSR project 205881, versiune V13 (la 2026-04).

## Componente

### loader.py — "Cititorul CSV Cleveland Fed"
Funcții publice: `load_cleveland_fed_indices(csv_path=None) -> pd.DataFrame` — parse CSV manual descărcat din ICPSR; `get_district_score(df, district, date)` — extrage scorul per district la o dată. Helper intern `_district_col(district)` pentru abrevieri (KC, NY, SF, SL etc.).
**SE STRICĂ DACĂ:** CSV lipsește (`data/economic_sentiment/cleveland_fed_indices.csv`); ICPSR schimbă schema coloanelor; abreviere district necunoscută; encoding CSV diferit de UTF-8.

### schemas.py — "Dicționarul"
Pydantic models + constantele de mapare (`CSV_COLUMN_TO_DISTRICT` etc.). Validează row-by-row output-ul loader-ului.
**SE STRICĂ DACĂ:** adaugi un district nou fără update la mapping; coloane CSV au type nou (ex: datetime în loc de string).

### `__init__.py` — Surface API
Re-exportă `load_cleveland_fed_indices`, `get_district_score`.

## Lanțul de dependențe

```
ICPSR V13 (manual download)
        │
        ▼
data/economic_sentiment/cleveland_fed_indices.csv
        │
        ▼
   loader.py (parse + validate via schemas)
        │
        ▼
  DataFrame[publication_date, national, boston, ny, philly, ...]
        │
        ▼
  Stratul 3 (divergence) — feature secundar ~10-15% weight
  Stratul 3 — `national_consensus_divergence` ca independent signal
```

## Când ceva nu merge — întrebări de diagnostic

1. **`FileNotFoundError: cleveland_fed_indices.csv`** → refresh manual necesar. Vezi [docs/DATA_REFRESH.md](../../../docs/DATA_REFRESH.md).
2. **`KeyError: district_col`** → abreviere nerecunoscută; verifică `_district_col()` vs ICPSR column headers.
3. **`publication_date` parse fail** → ICPSR a schimbat format date; ajustează `pd.to_datetime(...)` în loader.
4. **Valori NaN masiv** → versiune V necorespunzătoare cu cea așteptată de parser; re-download latest V.
5. **Scorul național divergent vs suma districtelor** → feature by design (`national_consensus_divergence`, D21) sau bug de parsing.

## Legătura cu restul proiectului
- **Consumer:** PRD-300 (divergence signal) ca filter secundar; viitor `divergence/regime_conditional.py` extension.
- **Depends on:** `pandas`, `pydantic`. NU depinde de HuggingFace/transformers (scorurile sunt pre-computed).
- **PRD:** PRD-102 (Done, CC-2 done). Pivot finalizat 2026-04-14.

## Limitări cunoscute
- **Refresh manual 6-8 săptămâni.** Frecvență dictată de ciclul Beige Book; automation ICPSR (login + download) = low-value TD.
- **FX impact empirically weak** (Zavodny 2005, Rosa 2013) — rolul e de filter, nu driver.
- **Schema lock-in** — dacă ICPSR schimbă versiunea major (V14+ cu coloane noi), necesită update la `schemas.py` + `loader.py`.
- **Fără fallback la custom FinBERT** — decizia D20 a deprecat pipeline-ul custom; dacă Cleveland Fed întrerupe publicarea, re-evaluare necesară.
- **12 districte + national hardcoded** — Fed nu adaugă districte, dar denumirea (`SF`, `KC`) e specifică ICPSR.
