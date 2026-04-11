# DEC-003: US Rates Source — DFII5 (TIPS Real Yield) over T5YIE (Breakeven Inflation)

**Status:** Approved (retroactive documentation, 2026-04-11)
**Date:** 2026-04-11 (decision made implicitly during PRD-200/CC-2b implementation)
**Owner:** Fabian
**Related:** PRD-200, CC-2b, CC-4

## Context

PRD-200 necesită calculul `us_5y_real` (US 5-year real yield) pentru composite-ul `real_rate_differential`. Există două surse FRED echivalente matematic dar metodologic diferite:

**Opțiunea A — DFII5 (5-Year Treasury Inflation-Indexed Security)**
- Yield-ul observat direct pe piață al obligațiunilor TIPS (Treasury Inflation-Protected Securities) cu maturitate 5 ani
- Sursă: tranzacții reale de piață pe instrumente reale
- Calcul real yield: `us_5y_real = DFII5` (direct, fără manipulare)
- Calcul breakeven: `breakeven = DGS5 - DFII5` (derivat ca sub-produs)

**Opțiunea B — T5YIE (5-Year Breakeven Inflation Rate)**
- Rata breakeven publicată de FRED, calculată intern ca `DGS5 - DFII5` cu mici ajustări de liquidity premium
- Sursă: derivare FRED, nu observație directă
- Calcul real yield: `us_5y_real = DGS5 - T5YIE` (derivat din serie deja derivată)

## Decision

**Folosim DFII5 ca sursă primară pentru `us_5y_real`.**

Calculul breakeven (`us_5y_breakeven`) e derivat ca sub-produs: `us_5y_nominal - us_5y_real`.

Implementare: `src/macro_context_reader/market_pricing/us_rates.py`, funcția `fetch_us_rates`.

## Rationale

1. **Observabilitate directă peste derivare.** DFII5 reprezintă tranzacții reale de piață pe instrumente TIPS. T5YIE e o serie sintetică derivată de FRED. Când două surse sunt matematic echivalente, sursa care reflectă tranzacții reale e preferabilă fiindcă încorporează implicit liquidity premium, market sentiment, și flow effects pe care derivarea FRED le aproximează.

2. **Lanț de derivare scurt.** DFII5 → `real_rate_differential` e un singur pas de calcul. T5YIE → `real_rate_differential` introduce un pas intermediar (derivarea FRED a T5YIE din DGS5 + DFII5) care adaugă opacitate metodologică fără valoare adăugată.

3. **Auditabilitate.** DFII5 e direct verificabil pe Treasury auctions și pe trade data. T5YIE depinde de algoritmul intern FRED pentru ajustări (care poate fi modificat fără anunț). Pentru un sistem de research, dependențele auditabile sunt preferabile.

4. **Validation empirică.** PRD-200/CC-7-DIAGNOSTIC a confirmat că pipeline-ul cu DFII5 produce signal cu signature empirică corectă (median rolling correlation r = -0.51 cu EUR/USD pe 2015-2024). Înlocuirea cu T5YIE ar produce rezultate matematic identice pe full range, dar ar pierde robustețea metodologică.

## Alternatives Considered

**T5YIE direct.** Respins pentru motivele de mai sus. Echivalent matematic, inferior metodologic.

**Combinarea ambelor.** Considerat și respins. Adăugare de complexitate fără valoare informațională (sunt redundante).

**Treasury yield + alte horizons (DFII7, DFII10).** Respins pentru consistență cu `eu_rates` 5Y și cu logica PRD-200 centrată pe orizont 5 ani (vezi DEC-001).

## Implications

- Schema `USRatesRow` are câmpurile: `date`, `us_5y_nominal` (DGS5), `us_5y_real` (DFII5), `us_5y_breakeven` (computed = nominal - real)
- Naming: `us_5y_breakeven` (nu `us_5y_breakeven_implied` cum era inițial în CC-2b — patch-uit în CC-4 pentru consistență)
- Validarea empirică în PRD-200/CC-7 a folosit această sursă; orice schimbare viitoare a sursei invalidează rezultatele de validare AC-6 și necesită re-rulare diagnostic

## References

- PRD-200/CC-2b: implementarea inițială cu DFII5 (commit `1a8c91a`)
- PRD-200/CC-4 (patch): refactor naming + Pydantic validation, sursa rămâne DFII5 (commit `888ba69`)
- FRED DFII5: https://fred.stlouisfed.org/series/DFII5
- FRED T5YIE: https://fred.stlouisfed.org/series/T5YIE
- DEC-001: alegerea horizontului 5Y pentru întregul PRD-200

## Note on retroactive documentation

Acest DEC e scris retroactiv (2026-04-11) după ce a fost identificat ca datorie documentară în debt-cleanup post-PRD-200. Decizia tehnică e deja implementată în cod și validată empiric. Documentația retroactivă captează raționamentul pentru audit trail viitor, nu schimbă implementarea.
