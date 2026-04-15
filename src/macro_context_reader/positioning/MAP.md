# positioning / MAP.md

## La ce folosește (în 1 propoziție)
Stratul 4 — contextul de crowd/anti-crowd: structural (COT Leveraged Funds săptămânal) și tactic (OI + options put/call + retail sentiment contrarian), agregat în `tactical_score`.

## Decizii critice documentate
- **Relația 4A–4B:** 4A (COT structural) dă direcția, 4B (tactical) confirmă sau invalidează. Nu intra contra 4A bazat exclusiv pe 4B (CLAUDE.md).
- **Formula agregare:** `tactical_score = 0.4×oi + 0.35×options + 0.25×retail`.
- **Retail e CONTRARIANȘ:** 70%+ retail long EUR → semnal bearish EUR.
- **D14** — Test coverage obligatoriu (positioning respectă retroactiv regula v1.4).

## Componente

### cot_leveraged_funds.py — "Culegătorul COT structural"
Funcții publice: `fetch_cot_eur(start_year)` (prin `cot-reports`), `compute_cot_signals(df)` (percentile rank 80th, delta WoW), `save_cot_parquet(df, path)`, `run_cot_pipeline(start_year)`. Output: `data/positioning/cot_eur.parquet` (787 rânduri, 2020-2026).
**SE STRICĂ DACĂ:** CFTC schimbă schema raportului TFF; `cot-reports` library API break; interval început înainte de 2010 (schema veche).

### oi_signal.py — "Semnalul de Open Interest"
`fetch_eur_oi(start, end)` (scraping HTTPS de pe CME — nu FTP, care a fost retras post-2025 — TD-3 în ROADMAP), `compute_oi_signal(df_oi, df_price)` (OI↑ + preț↑ = trend confirmed; OI↓ = squeeze), `save_oi_parquet(...)`.
**SE STRICĂ DACĂ:** CME schimbă pagina HTML; data/price join gol pe holidays; docstring încă menționează `ftp.cmegroup.com/bulletin/` (TD-3).

### options_signal.py — "Semnalul put/call"
`fetch_eur_putcall_ratio(start, end)`, `compute_options_signal(df, window=52)` — normalizare vs rolling 52w, detectare skew `put/call > 1.2` (piața se hedgează pentru EUR weakness), `save_options_parquet(...)`.
**SE STRICĂ DACĂ:** sursa CME CVOL schimbă format; fereastra 52w depășește istoria disponibilă.

### retail_signal.py — "Semnalul retail contrarian"
`fetch_retail_sentiment(...)` (Myfxbook community outlook JSON), `compute_retail_signal(df)` — inversează semnul (retail long = bearish signal), `save_retail_parquet(...)`.
**SE STRICĂ DACĂ:** Myfxbook schimbă API (fără auth); JSON schema change; rate-limited.

### tactical_composite.py — "Agregatorul final"
`load_signals()` → tuple[oi_df, options_df, retail_df]. `compute_tactical_score(oi, options, retail)` — aplică ponderile 0.4/0.35/0.25. `run_tactical_pipeline()` → DataFrame consolidat.
**SE STRICĂ DACĂ:** vreun semnal lipsește (`load_signals` fail); intersecția datelor între cele 3 surse e goală pe perioada cerută.

### schemas.py — "Dicționarul"
Pydantic: `COTStructuralRow`. Schema validation pentru outputul COT.

### `__init__.py` — Surface API
Re-exportă funcțiile publice principale.

## Lanțul de dependențe

```
CFTC COT API          CME HTTPS           CME CVOL           Myfxbook JSON
     │                     │                  │                     │
     ▼                     ▼                  ▼                     ▼
cot_leveraged_funds    oi_signal         options_signal        retail_signal
     │                     │                  │                     │
     │                     └──────┬───────────┴──────┬──────────────┘
     │                            ▼                   │
     │                    tactical_composite.py ──────┘
     │                            │
     ▼                            ▼
COT parquet           tactical_score → Stratul 4B output
(4A structural)
```

## Când ceva nu merge — întrebări de diagnostic

1. **COT returnează <50 rânduri** → start_year prea recent sau CFTC a publicat cu lag.
2. **OI signal toate zero** → `df_oi` și `df_price` nu se intersectează pe date (calendare diferite).
3. **Retail signal lipsește** → Myfxbook API down sau JSON schema changed.
4. **`tactical_score` NaN** → cel puțin un semnal componentă lipsește în fereastra cerută.
5. **COT signals percentile rank suspect** → fereastra istorică prea scurtă (< 100 săptămâni).

## Legătura cu restul proiectului
- **Consumer:** `output/bba_mappers/layer4_positioning.py` (DST mapping), viitor PRD-300 (regime-conditional).
- **Depends on:** `cot-reports`, `requests`, `beautifulsoup4`, `pandas`, `pyarrow`.
- **PRD:** PRD-400 (COT structural, Done) + PRD-401 (Tactical OI/Options/Retail, Done).
- **Artefact:** `data/positioning/cot_eur.parquet` (committed for reproducibility).

## Limitări cunoscute
- **COT lag 3 zile** (publicat vineri pentru pozițiile de marți) — folosit pentru confirmare, nu timing.
- **OI CME — scraping HTTPS fragil**, schimbare de site poate sparge. CLAUDE.md line 98 încă referențiază FTP defunct (TD-3).
- **Options put/call skew** — necesită date intraday CVOL; sursa poate fi costisitoare în viitor.
- **Retail Myfxbook** — fără contract; pot schimba API fără notificare.
- **`tactical_score` weights fix** (0.4/0.35/0.25) — nu calibrate empiric, doar prior intuitiv.
