# Data refresh — proceduri manuale

> Anumite dataset-uri nu au API public stabil. Aici sunt pașii concreți pentru refresh manual.

## Cleveland Fed Beige Book Sentiment Indices

**Frecvență:** la fiecare 6-8 săptămâni (după publicare Beige Book nouă)

**Pași:**
1. Mergi la https://www.openicpsr.org/openicpsr/project/205881/
2. Descarcă versiunea cea mai recentă (V13, V14, etc.)
3. Extrage CSV-ul principal cu sentiment indices
4. Înlocuiește `data/economic_sentiment/cleveland_fed_indices.csv`
5. Rulează: `pytest tests/economic_sentiment/ -v` — toate testele trebuie să treacă

**Verificare:**
```python
from macro_context_reader.economic_sentiment import load_cleveland_fed_indices
df = load_cleveland_fed_indices()
print(f"Latest date: {df['publication_date'].max()}")
# Expected: data publicării ultimei Beige Book
```

## CME FedWatch Probabilities

**Frecvență:** săptămânal (recomandat luni dimineața)

**Pași:**
1. Mergi la https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html
2. Click pe "Historical" tab
3. În secțiunea "Downloads", descarcă Excel/CSV "Fed Meeting History"
4. Salvează ca: `data/market_pricing/fedwatch_snapshots/FedMeetingHistory_YYYYMMDD.csv`
   - `YYYYMMDD` = data download-ului (ex: `20260415`)
5. Rulează:
   ```python
   from macro_context_reader.market_pricing.fedwatch import build_master_dataset
   build_master_dataset(verbose=True)
   ```

**Convenția de naming e CRITICĂ.** Format diferit → loader emite warning și ignoră fișierul (vezi commit `f49f91d`).

**Verificare:**
```python
from macro_context_reader.market_pricing.fedwatch import load_fedwatch_history
df = load_fedwatch_history(rebuild=True)
print(f"Snapshots: {df['source_snapshot_date'].nunique()}")
print(f"Date range: {df['observation_date'].min()} to {df['observation_date'].max()}")
```

## CFTC COT Reports

**Frecvență:** săptămânal (publicat vinerea pentru pozițiile de marți, lag 3 zile)

**Procedură:** folosită prin librăria `cot-reports` (automată). Pipeline:
```python
from macro_context_reader.positioning.cot_leveraged_funds import run_cot_pipeline
df = run_cot_pipeline(start_year=2020)
# Scrie în data/positioning/cot_eur.parquet
```

Dacă CFTC schimbă schema raportului TFF Futures-only, editează `cot_leveraged_funds.py` (coloanele target sunt documentate în `schemas.py`).

## FRED și ECB (automate)

- **FRED** (`fredapi`): rulează din cod; cheie în `.env` (`FRED_API_KEY`). Rate limit generos, refresh on-demand.
- **ECB Data Portal** (`ecbdata`): fără cheie. Verifică `TITLE_COMPL` pentru serii noi (vezi DEC-002 și regula CLAUDE.md despre SDMX).

## Troubleshooting

### CME FedWatch download lipsește
CME poate restructura site-ul. Dacă tab "Historical → Downloads" nu mai există:
- Verifică dacă au mutat la API
- Fallback: vezi TD-1 în [ROADMAP.md](../ROADMAP.md) (automation amânată)

### Cleveland Fed CSV schimbă schema
Schema actuală: coloane cu abrevieri district (KC, NY, SF, SL). Dacă ICPSR schimbă schema → vezi `src/macro_context_reader/economic_sentiment/loader.py` și `schemas.py`.

### FRED serie returnează gol
- Interval prea recent (FRED publică cu lag de 1 zi business)
- `start > end` accidental
- Testează interactiv: `Fred(api_key=...).get_series("DGS5", observation_start="2024-01-01")`
