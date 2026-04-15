# market_pricing/fedwatch / MAP.md

## La ce folosește (în 1 propoziție)
Sub-modul pentru CME FedWatch: parse snapshot-uri CSV săptămânale (probabilități implicite per meeting × bucket), construiește master dataset Parquet, și calculează surprise signal față de NLP score-uri prin 3 metode (binary, expected_change, KL divergence).

## Decizii critice documentate
- **D23 — CME FedWatch CSV manual snapshots** > FRED Fed Funds Futures > CME FTP. FRED nu hostează futures; CME FTP `bulletin/` eliminat post-2025; manual = singurul path stabil fără Selenium.
- **D24 — 3 surprise methods simultaneous** (binary, expected_change Gürkaynak-Sack-Swanson 2005, Kullback-Leibler divergence). Selecție empirică amânată la PRD-300 backtesting. Default: `expected_change` (industry standard).
- **D25 — Default NLP→bps calibration = 25bps per unit hawkish** (una standard FOMC move). Va fi recalibrat OLS în PRD-300 pe 80+ evenimente FOMC istorice.
- **TD-1** — manual refresh săptămânal; automation opțională (OpenClaw/Playwright) amânată.

## Componente

### parser.py — "Spărgătorul de CSV"
Funcții publice: `parse_fedwatch_csv(csv_path) -> pd.DataFrame` — parse un snapshot CME (9 meeting blocks × 63 rate buckets × ~253 days), drop zeros (93% saving). `get_snapshot_metadata(csv_path) -> FedWatchSnapshot`. Helpers: `_parse_meeting_date(label)`, `_parse_snapshot_date_from_filename(path)` (convenție naming `FedMeetingHistory_YYYYMMDD.csv`), `_identify_meeting_blocks(header_row)`.
**SE STRICĂ DACĂ:** filename nu respectă convenția `FedMeetingHistory_YYYYMMDD.csv` (warning + skip, commit `f49f91d`); CME schimbă structura CSV (număr meetings ≠ 9, buckets ≠ 63); header parse fail.

### loader.py — "Asamblorul multi-snapshot"
Funcții publice: `list_available_snapshots(snapshots_dir=None)`, `load_all_snapshots(...)` (parse all + dedup pe `(observation_date, meeting_date, rate_bucket_low)` latest-wins), `build_master_dataset(...)` (persist Parquet), `load_fedwatch_history(rebuild=False)` (read Parquet sau rebuild).
**SE STRICĂ DACĂ:** folder `data/market_pricing/fedwatch/snapshots/` lipsește; un snapshot corupt → loader warn + skip (by design); Parquet scris incomplet (disk full).

### surprise.py — "Calculatorul de surpriză"
Funcții publice: `compute_surprise_signal(nlp_score, observation_date, meeting_date, method='expected_change', ...)` — single event; `compute_surprise_timeseries(nlp_df, method=...)` — batch pe DataFrame. Helpers interne: `_fetch_current_fed_funds_midpoint(...)` (FRED DFEDTARU/DFEDTARL), `_get_buckets_for_date(...)`, `_market_expected_change_bps(...)`, `_market_prob_hike(...)`, `_compute_nlp_distribution(...)`. Metode: `_surprise_binary(...)`, `_surprise_expected_change(...)`, `_surprise_kl_divergence(...)`.
**SE STRICĂ DACĂ:** `FRED_API_KEY` lipsește (necesar pentru Fed Funds midpoint); NLP score out-of-range [-1, 1]; meeting_date fără buckets în snapshot; `method` invalid; fereastra KL cu mass=0 într-un bucket.

### schemas.py — "Dicționarul"
Pydantic: `FedWatchRow` (per bucket: observation_date, meeting_date, rate_bucket_low, rate_bucket_high, probability), `FedWatchSnapshot` (metadata: snapshot_date, n_meetings, n_observations, range dates).
**SE STRICĂ DACĂ:** schema schimbată în parser/loader fără update here.

### `__init__.py` — Surface API
Re-exportă `parse_fedwatch_csv`, `build_master_dataset`, `load_fedwatch_history`, `compute_surprise_signal`, `compute_surprise_timeseries`.

## Lanțul de dependențe

```
CME FedWatch website (manual download săptămânal)
                │
                ▼
data/market_pricing/fedwatch/snapshots/FedMeetingHistory_YYYYMMDD.csv
                │
                ▼
          parser.py (per snapshot)
                │
                ▼ FedWatchRow stream
          loader.py (dedup latest-wins, Parquet)
                │
                ▼
data/market_pricing/fedwatch/master.parquet
                │
                ▼
         surprise.py ←── FRED DFEDTARU/DFEDTARL (current rate)
                │         ←── NLP hawkish score (Stratul 1)
                ▼
         surprise_signal (bps sau nats, după metodă) → Stratul 3
```

## Când ceva nu merge — întrebări de diagnostic

1. **"No snapshots found"** → folder `data/market_pricing/fedwatch/snapshots/` gol; refresh manual (vezi DATA_REFRESH.md).
2. **Warning "invalid filename, skipping"** → fișier nu respectă `FedMeetingHistory_YYYYMMDD.csv`; redenumește.
3. **`KeyError: meeting_date`** în surprise → meeting selectat nu există în snapshot la observation_date; alege un meeting în viitor față de observation_date.
4. **KL divergence = inf** → un bucket are market_prob=0 și NLP_prob>0 (sau invers); adaugă epsilon smoothing.
5. **Probabilities nu sumează la 1 per (obs_date, meeting)** → CME publica snapshot incomplet; `parse_fedwatch_csv` loguiește; ~90% din pairs ≥ 0.95 e norma.

## Legătura cu restul proiectului
- **Consumer:** `divergence/` (PRD-300) pentru `surprise_score`, `output/bba_mappers/layer2_market.py` (DST mapping).
- **Depends on:** `pandas`, `pyarrow`, `pydantic`, `fredapi` (pentru current Fed Funds midpoint), FS local pentru snapshots.
- **PRD:** PRD-202 (~95% Done — parser, loader, surprise + 56 tests; pending MAP.md aceasta).

## Empirical findings (sesiune 2026-04-14/15)
- **~9220 non-zero records per snapshot** (drop zeros saves 93% vs ~143k raw).
- **~90% pairs (obs_date, meeting_date) sum to ≥0.95** — validează asumpția 63-buckets-per-block.
- **CME publishes ~12 months forward** (nu 15 meetings cum asumam inițial).

## Limitări cunoscute
- **Manual refresh săptămânal** (TD-1). Automation posibilă dar amânată.
- **Default NLP→bps = 25bps** (D25) — placeholder, OLS recalibrat în PRD-300.
- **CME CSV schema poate schimba** fără notice — TD posibil.
- **Surprise method selection** nu e finalizată; toate 3 implementate paralel (D24), empirical selection e PRD-300 / CC-3..CC-5.
- **KL divergence** sensibil la zeros → epsilon smoothing parametric.
