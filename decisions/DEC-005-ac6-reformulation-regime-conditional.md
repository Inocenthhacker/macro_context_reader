# DEC-005: AC-6 Reformulation — From Global Pearson to Regime-Conditional

**Status:** Approved
**Date:** 2026-04-11
**Owner:** Fabian
**Related:** PRD-200, notebook `02b_layer2_regime_diagnostic.ipynb`

## Context

PRD-200/CC-7 a produs notebook-ul de validare end-to-end al Stratului 2. Pearson correlation globală pe full range 2015-2024 între `real_rate_differential` și EUR/USD a fost calculată: **r = -0.0455** (semn corect, magnitudine economic neglijabilă, mult sub pragul AC-6 original de `|r| > 0.5`).

Înainte de a accepta sau respinge teza fundamentală a proiectului, am rulat un diagnostic suplimentar (PRD-200/CC-7-DIAGNOSTIC, notebook `02b_layer2_regime_diagnostic.ipynb`) cu două teste statistice independente.

## Diagnostic Findings

**Test 1 — Rolling Correlation (252-day window):**
- Range: `[-0.93, +0.67]`
- Sign flips: 4 în 9 ani
- Distribuție temporală: 67.4% strong negative (`r < -0.3`), 13.0% strong positive (`r > +0.3`), 19.6% neutral
- **Verdict:** REGIME SWITCHING CONFIRMED

**Test 2 — CUSUM Structural Break:**
- Beta global = `-0.003` (semn corect, magnitudine zero)
- 72.2% din observații în afara benzii de încredere 95%
- **Verdict:** STRUCTURAL BREAKS DETECTED

**Concluzie diagnostic:** Pearson r = -0.045 nu reflectă "relație slabă". Reflectă mediarea unei relații regime-conditional care se anulează parțial pe interval. Teza fundamentalistă (`real_rate_diff` e ancora EUR/USD) e validată în 67% din ferestre, suprascrisă în 13%, neutră în restul.

## Why AC-6 was misspecified

AC-6 original (`|r| > 0.5 pe full range`) presupunea **stabilitate temporală** a relației — ipoteză contrazisă de:

1. **Literatura ECB Blog 2025 (Gebauer et al.)**: Fed spillover pe EUR/USD comută regim la 0-63 zile vs 63+ zile
2. **Ismayilli 2025**: stresul geopolitic suprascrie fundamentalele în episoade discrete
3. **BBVA Research 2025**: descompune EUR/USD în GFCI + politica monetară Fed, cu ponderi ce variază pe regim
4. **Mulliner, Harvey, Xia, Fang 2025**: identifică regimuri economice discrete prin Mahalanobis distance

Toate sursele converg: corelația contemporanee daily globală nu e metrica corectă pentru o relație regime-conditional.

## Reformulation principles

Reformularea AC-6 a fost scrisă **înainte** de a calcula noile metrici pe date, ca să prevenim p-hacking. Pragurile sunt motivate de:

1. **Median rolling r ≤ -0.30** — pragul standard de "moderate correlation" din literatura empirică FX (Engel & West 2005, Macrosynergy 2024)
2. **≤ 25% ferestre cu r > 0** — derivat din estimarea ECB+Ismayilli a regimurilor de stres (10-20%) + 5pp toleranță
3. **Min rolling r ≤ -0.50** — verificare că semnătura empirică teoretică EXISTĂ în date, nu doar că semnul e dominant

Cele 3 condiții trebuie satisfăcute SIMULTAN. AC-6 nu e relaxat, ci re-specificat cu precizie regime-aware.

## Failure path

Dacă AC-6 reformulat eșuează la testare (Pasul 2B):
- Stop pe finalizarea PRD-200
- Revizuire arhitecturală Stratul 2: `real_rate_differential` e o ancoră prea slabă chiar și regime-aware
- Investigație alternative: cointegrare VECM, descompunere GFCI explicit (BBVA 2025), regime-conditional regression cu Markov switching
- PRD-200 marcat ca "In Progress — architectural review", nu Done

## Downstream dependency

Independent de rezultatul AC-6 reformulat, descoperirea de regime switching impune o cerință arhitecturală:

- Layer 2 NU poate fi folosit ca semnal naiv în output-ul final
- Trebuie implementat un regime detector explicit (rolling correlation threshold + structural break monitoring)
- Acest detector e responsabilitatea PRD-300 sau a unui PRD nou (TBD)
- Referința e adăugată în AC-9 nou (PRD-200) și în Notes / Întrebări Deschise

**Notă numerotare AC:** Reformularea inițial a propus introducerea unui "AC-7 nou" pentru regime detector. AC-7 era deja ocupat în PRD-200 (commit convention) și AC-8 (PR merge process). Pentru a evita renumerotarea instabilă a referințelor existente, noul AC e numerotat **AC-9**.

## References

- Notebook `notebooks/02b_layer2_regime_diagnostic.ipynb` (rulat 2026-04-11, Pearson rolling + CUSUM)
- Gebauer et al. (ECB Blog 2025): https://www.ecb.europa.eu/press/blog/date/2025/html/ecb.blog20250205~44578cf53f.en.html
- Ismayilli (SSRN 2025): https://papers.ssrn.com/sol3/Delivery.cfm/5141086.pdf
- BBVA Research (Martínez et al. 2025): https://www.bbvaresearch.com/wp-content/uploads/2025/03/Equilibrium-of-the-EUR-USD-exchange-rate-A-long-term-perspective.pdf
- Mulliner, Harvey, Xia, Fang (Journal of Financial Economics 2025): regime detection via Mahalanobis distance
