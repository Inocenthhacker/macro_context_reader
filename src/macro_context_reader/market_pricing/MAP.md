# market_pricing / MAP.md

## La ce folosește (în 1 propoziție)
Calculează diferențialul de rate reale US-Eurozone pe orizont 5Y — ancora fundamentală a semnalului de regim macro EUR/USD pentru Layer 2.

## Decizie critică documentată
**DEC-001 — Orizont 5Y în loc de 2Y.** US Treasury nu emite TIPS pe 2Y, deci `DFII2` nu există în FRED. 5Y e cea mai scurtă serie reliable pentru US real yield. Întreg modulul respectă această decizie: `DGS5`/`DFII5` pe partea US, ECB AAA `SR_5Y` pe partea EUR, ECB SPF longer-term (4-5Y) pentru inflation expectations EUR.

**DEC-002 — Dual yield curves EUR (AAA + All issuers).** ECB publică două variante: `G_N_A` = AAA-only (Germany/NL/LU), `G_N_C` = all issuers. AAA e input principal în diferențial (simetrie cu US Treasury); All issuers și spread-ul (`eu_credit_stress_5y`) sunt păstrate ca semnale paralele. Atenție la convenție: alfabetic ai zice opusul — verificare obligatorie prin `TITLE_COMPL` SDMX.

**DEC-004 — ECB SPF în loc de ILS.** Inflation-Linked Swaps EUR nu sunt disponibile pe ECB free Data Portal. SPF (Survey of Professional Forecasters) e quarterly, dar e singura sursă publică reliable pentru long-term EUR inflation expectations.

## Componente

### us_rates.py — "Aducătorul de rate US"
Descarcă `DGS5` (5Y nominal Treasury) și `DFII5` (5Y TIPS real yield) din FRED. Calculează `us_5y_breakeven = DGS5 - DFII5` automat. Funcție publică: `fetch_us_rates(start, end, client=None)` → `DataFrame[date, us_5y_nominal, us_5y_real, us_5y_breakeven]`. Pipeline complet: `run_us_rates_pipeline()` → Parquet în `data/market_pricing/us_rates.parquet`. Validare row-by-row prin `USRatesRow`.
**SE STRICĂ DACĂ:** `FRED_API_KEY` lipsește/expirat în `.env`; FRED redenumește `DGS5` sau `DFII5`; FRED returnează serie goală pentru intervalul cerut; orice rând conține NaN și trece de `dropna` (Pydantic ridică).

### fx.py — "Aducătorul de curs EUR/USD"
Descarcă `DEXUSEU` (EUR/USD spot, noon NY buying rates) din FRED. Funcție publică: `fetch_fx_eurusd(start, end, client=None)` → `DataFrame[date, eurusd]`. Pipeline: `run_fx_pipeline()` → `data/market_pricing/fx.parquet`. Filtrează NaN (holidays). Validare prin `FXRow`.
**SE STRICĂ DACĂ:** `FRED_API_KEY` lipsește; FRED schimbă ID `DEXUSEU`; întreaga serie e NaN (după `dropna` rămâne goală).

### eu_rates.py — "Aducătorul de rate EUR"
Descarcă două serii ECB Yield Curve 5Y: `YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_5Y` (AAA) și `YC.B.U2.EUR.4F.G_N_C.SV_C_YM.SR_5Y` (All issuers). Calculează `eu_credit_stress_5y = all - aaa`. Funcție publică: `fetch_eu_rates(start, end, client=None)` → `DataFrame[date, eu_5y_nominal_aaa, eu_5y_nominal_all, eu_credit_stress_5y]`. Pipeline: `run_eu_rates_pipeline()` → `data/market_pricing/eu_rates.parquet`.
**SE STRICĂ DACĂ:** ECB Data Portal e indisponibil; ECB schimbă schema SDMX (lipsesc `TIME_PERIOD`/`OBS_VALUE`); inversezi din greșeală `G_N_A` cu `G_N_C` (vezi DEC-002 — verificare prin `TITLE_COMPL` obligatorie); inner join AAA ⋈ All produce gol (puțin probabil, ambele daily TARGET).

### eu_inflation.py — "Aducătorul de inflație EUR"
Descarcă `SPF.Q.U2.HICP.POINT.LT.Q.AVG` (ECB Survey of Professional Forecasters, longer-term HICP point forecast average). Frecvență nativă: quarterly. Convertește `TIME_PERIOD` "YYYY-QN" la `datetime` (sfârșit de trimestru). Funcție publică: `fetch_eu_inflation_5y(start, end, client=None)` → `DataFrame[date, eu_inflation_expectations_5y]`. Pipeline: `run_eu_inflation_pipeline()` → `data/market_pricing/eu_inflation_5y.parquet`. Forward-fill la daily NU se face aici — e responsabilitatea `real_rate_differential.py`.
**SE STRICĂ DACĂ:** ECB schimbă codul SPF; format `TIME_PERIOD` se schimbă (nu mai e parsabil ca `PeriodIndex` quarterly); seria publicată cu lag mai mare de 95 zile (default `forward_fill_limit_days`) la momentul rulării.

### real_rate_differential.py — "Calculatorul ancoră"
Combină cele trei surse. Inner join `us_rates` ⋈ `eu_rates` pe dată (ambele daily business days), apoi `merge_asof backward` cu SPF quarterly și forward-fill cu limită implicită 95 zile. Formula: `eu_5y_real = eu_5y_nominal_aaa - eu_inflation_expectations_5y`; `real_rate_differential = us_5y_real - eu_5y_real`. Funcție publică: `compute_real_rate_differential(start, end, us_rates_df=None, eu_rates_df=None, eu_inflation_df=None, forward_fill_limit_days=95)`. Pipeline: `run_real_rate_differential_pipeline()` → `data/market_pricing/real_rate_differential.parquet`. Validare prin `RealRateDifferentialRow`.
**SE STRICĂ DACĂ:** Inner join US ⋈ EU produce gol (calendare divergente, ex: range trecut total în holidays); SPF lag > 95 zile → trailing rows aruncate cu warning; SPF începe după primele date daily → leading rows aruncate; vreo serie upstream nu poate fi fetched (bubble-up din `us_rates`/`eu_rates`/`eu_inflation`).

### schemas.py — "Dicționarul"
Modele Pydantic frozen (`ConfigDict(frozen=True)`): `MethodMetadata`, `InflationExpectationRow`, `USRatesRow`, `EURRatesRow`, `EUInflationRow`, `RealRateDifferentialRow`, `FXRow`, `RealRateDiffRow`. Toate timestamp-urile sunt timezone-naive (convenție FRED/ECB), rate-urile în procente (2.5 = 2.5%, nu 0.025). NaN explicit interzis prin `model_validator` pe modelele cu rate.
**SE STRICĂ DACĂ:** Adaugi serie nouă într-un fetcher dar uiți schema corespondentă; schimbi semantica unei coloane (procent vs fracție) fără să actualizezi `description` și consumerii.

### inflation_expectations/ — "Submodul de pluggability"
Conține `base.py` cu `Protocol InflationExpectationsMethod` (`@runtime_checkable`). Definește contractul pentru orice metodă viitoare de EUR inflation expectations (PRD-203 OATei, PRD-204 DNS, etc.): proprietățile `name`/`frequency`/`source` + metodele `fetch()`, `get_at_date()`, `get_metadata()`. Permite înlocuirea SPF în `real_rate_differential.py` fără modificări upstream.
**SE STRICĂ DACĂ:** Modifici signature-ul Protocol-ului fără să actualizezi implementările; o implementare nu returnează coloanele obligatorii (`date`, `expected_inflation`, `horizon_years`).

## Lanțul de dependențe

```
                 FRED API
                ┌────┴────┐
                ▼         ▼
          us_rates.py   fx.py
                │         │
                │         └─→ DataFrame[date, eurusd]
                ▼
       (us_5y_real)
                │
                ▼
   ┌── real_rate_differential.py ──┐
   │  inner join + merge_asof SPF  │
   │  formula: us_real - eu_real   │
   └───────────────────────────────┘
                ▲          ▲
                │          │
       (eu_5y_nominal_aaa) (eu_inflation_expectations_5y)
                │          │
        eu_rates.py   eu_inflation.py
                │          │
                └──┬───────┘
                   ▼
              ECB Data Portal (ecbdata)

schemas.py ←── validează toate DataFrame-urile la fiecare nivel
inflation_expectations/base.py ←── contract pluggable pentru metode alternative SPF
```

Output final → consumat de PRD-300 (divergence) și PRD-500 (DST fusion).

## Când ceva nu merge, întrebări de diagnostic

1. **`ValueError: FRED_API_KEY nu e configurat în .env`?** → Verifică `.env` din root; cheia trebuie să nu înceapă cu `REPLACE_` și să nu fie `your_fred_api_key_here`. Pe Colab: secret stocat și injectat în env înainte de import.
2. **`ValueError: FRED series DGS5 returned empty`?** → Interval cerut e prea recent (FRED publică cu lag de 1 zi business) sau `start > end`. Testează interactiv: `Fred(api_key=...).get_series("DGS5", observation_start="2024-01-01")`.
3. **`ValueError: Inner join US ⋈ EU produced empty result`?** → Calendarele FRED și ECB nu se suprapun pe intervalul cerut. Cel mai des: ai pus `start` într-un weekend sau o săptămână plină de holidays mixte. Lărgește intervalul.
4. **`UserWarning: Dropped N rows where SPF forward-fill limit (95 days) was exceeded`?** → SPF e quarterly și ECB l-a publicat cu lag mai mare decât limita. Acceptabil dacă N e mic; investighează dacă pierzi luni întregi. Opțiune: crește `forward_fill_limit_days` în `compute_real_rate_differential`.
5. **`pydantic.ValidationError: us_5y_real must not be NaN`?** → FRED a returnat NaN într-o zi pe care `dropna(how="all")` nu a prins-o (un singur câmp NaN, nu ambele). Investighează seria brută în jurul datei eșuate; posibil holiday FRED.
6. **Coloana ECB returnează valori prost convertite (toate NaN după `_normalize_ecb_response`)?** → Schema ECB s-a schimbat sau seria are coloana valoare cu alt nume. Inspectează direct: `ecbdata.get_series("YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_5Y")[0:1]` și verifică dacă `OBS_VALUE` și `TIME_PERIOD` mai există.
7. **Spread `eu_credit_stress_5y` negativ persistent?** → AAA și All sunt inversate (G_N_A vs G_N_C inversat). Aplică DEC-002 și verifică `TITLE_COMPL` din metadata SDMX.

## Legătura cu restul proiectului
- **Consumer:** PRD-300 (divergence signal) consumă `real_rate_differential` ca input pentru calculul de surprise/divergență.
- **Consumer:** PRD-500 (DST fusion) folosește `real_rate_differential` ca evidență primară fundamentală.
- **Consumer indirect:** `fx.py` (`eurusd`) e folosit pentru cross-validation vizuală a corelației real_rate_diff vs preț.
- **Nu depinde de:** niciun alt modul intern. Layer-ul fundamental — toți ceilalți depind de el, nu invers.

## Limitări cunoscute
- **5Y horizon e impus de absența DFII2** (DEC-001). Nu e alegerea ideală pentru semnale tactice scurte (1-3 luni); e adecvat pentru regim structural (luni-trimestre).
- **SPF e quarterly cu publicare lag.** Forward-fill la daily introduce stale data între publicări. Limita 95 zile e safety net, dar 1-2 luni de SPF stale e norma, nu excepția.
- **ECB Yield Curve exclude obligațiunile indexate la inflație** — curba EUR e strict nominal. Nu există echivalent direct DFII5 pe partea EUR; de aceea se folosește SPF pentru inflation expectations EUR (nu breakeven-style).
- **FRED `DEXUSEU` e noon buying rates NY** — nu spot intraday. Suficient pentru semnal de regim, insuficient pentru execuție.
- **Niciun caching incremental.** Fiecare `fetch_*` re-descarcă tot intervalul cerut. Pe Colab cu re-rulări frecvente, latență cumulativă vizibilă; nu critic.
- **Calendare divergente FRED ↔ ECB ↔ TARGET.** Inner join elimină zile fără ambele observații; pierderea tipică e ~5-8% din zile.
