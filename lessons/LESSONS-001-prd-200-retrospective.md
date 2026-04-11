# Lessons Learned 001 — PRD-200 Retrospective

**Source:** PRD-200 (Market Pricing Pipeline)
**Date:** 2026-04-11
**Status:** Active — applies to all PRDs going forward

---

## Context

PRD-200 a fost primul PRD complet end-to-end al proiectului Macro Context Reader. A livrat Stratul 2 (Market Pricing) cu pipeline complet pe date reale: us_rates, eu_rates, eu_inflation, real_rate_differential, fx. A trecut prin 9 CC-uri și a generat 5 decizii arhitecturale (DEC-001..DEC-005).

În timpul PRD-200, am descoperit prin AC-6 (Pearson correlation validation) un bug metodologic fundamental: relația `real_rate_differential ↔ EUR/USD` e regime-switching, nu lineară stabilă. Acest lucru a triggered diagnosticul empiric din notebook 02b și reformularea AC-6 prin DEC-005. Procesul de descoperire-reformulare-revalidare a generat aceste 5 lecții.

---

## Lecția 1 — AC-urile scrise *înainte* de a vedea datele sunt aproape garantat greșite

### Ce s-a întâmplat

AC-6 original a fost: *"Pearson correlation > |0.5| pe dataset trimestrial complet. Sub 0.5 = escalare obligatorie."*

Părea o cerință rezonabilă. Era complet greșită. Presupunea **stabilitate temporală** a unei relații care e regime-switching — fapt deja documentat în literatura academică pe care o aveam în research-ul proiectului (ECB Blog 2025, BBVA Research 2025, Ismayilli 2025), dar nu integrat conștient în formularea AC-ului.

Calculul empiric: `r = -0.0455` pe full range (semn corect, magnitudine zero). Aproape de a fi declarată ca "ipoteză eșuată". Diagnostic ulterior a arătat că relația e puternic negativă în 67% din timp și pozitivă în 13% — mediana se anulează, dar fenomenul e real.

### De ce s-a întâmplat

Când scrii un AC pentru o ipoteză pe care nu ai testat-o încă empiric, **tinzi să folosești metricile pe care le știi** (Pearson global), nu metricile potrivite pentru fenomenul real. E un default cognitiv, nu lene. Pearson e prima metrică pe care o învață oricine la statistică intro. Metricile potrivite (rolling correlation, structural break tests, regime-switching models) sunt avansate și non-default.

### Fix pentru PRD-uri viitoare

- Pentru fiecare AC care implică o metrică statistică, întreabă-te explicit: *"există în literatură consensus că această metrică e potrivită pentru această relație?"*
- Dacă nu știi sigur, scrie AC-ul ca **range plauzibil + obligația de diagnostic preliminar**, nu un prag fix.
- Exemplu pentru PRD-400 (COT positioning): nu scrie *"COT positioning extremes prezic reversal cu accuracy > 60%"*. Scrie *"COT positioning extremes corelează cu reversal subsequent în max 90 zile, cu metrică de evaluare definită după diagnostic preliminar pe date 2018-2024."*

---

## Lecția 2 — Diagnosticul empiric trebuie să fie un CC explicit, nu o reacție post-failure

### Ce s-a întâmplat

Notebook 02b (regime diagnostic) a fost creat **după** ce AC-6 a eșuat. A funcționat, dar a fost noroc. Dacă AC-6 ar fi trecut accidental — de exemplu pe o sub-perioadă calmă în date — nu am fi diagnosticat regime switching și am fi construit Stratul 3 (Divergence Signal) pe o ancoră prost înțeleasă. Asta ar fi generat bug-uri arhitecturale care s-ar fi manifestat doar 2-3 PRD-uri mai târziu.

### Fix pentru PRD-uri viitoare

Fiecare PRD care livrează un semnal sau composite trebuie să aibă un CC dedicat de diagnostic empiric, separat de validation. Pattern-ul:

1. CC-N livrează modulul (cod + teste unitare)
2. CC-N+1 livrează diagnostic notebook (rolling stats, structural breaks, regime check, distribution plots, sanity checks pe sub-perioade)
3. CC-N+2 livrează validarea AC pe baza rezultatelor diagnosticului

Pentru PRD-400, asta înseamnă concret:

- CC-X: COT structural pipeline (cod + teste)
- CC-Y: COT positioning regime diagnostic notebook (distribuție pozițiilor extreme, persistență temporală, corelație cu reversal subsequent pe ferestre multiple)
- CC-Z: COT validation against AC

---

## Lecția 3 — DEC-urile sunt mai importante decât credeam; PRD-uri fără DEC-uri sunt fragile

### Ce s-a întâmplat

DEC-005 a salvat reformularea AC-6 de la a fi p-hacking. Pragurile noi (median ≤ -0.30, ≤ 25% positive, min ≤ -0.50) au fost commited **înainte** de a fi calculate pe date reale. Audit trail-ul există în git history (commit 0d11ac7 înainte de bf6b94d). Peste 6 luni, oricine se uită la PRD-200 poate verifica că onestitatea metodologică a fost respectată — pragurile nu au fost mutate ca să "iasă" rezultatul.

Fără DEC-005, reformularea ar fi părut suspectă: *"de ce ai schimbat AC-ul exact când metrica originală pica?"* DEC-ul dă răspunsul în text și în timestamp.

### Fix

Scriem un DEC pentru fiecare decizie care:
- Schimbă sensul unei cerințe existente
- Introduce o constrângere care nu era evidentă din literatură
- Documentează un trade-off arhitectural (alegerea unei opțiuni dintre mai multe)
- Salvează un eșec aparent prin reframing metodologic
- Implică o sursă de date contraintuitivă sau prost documentată (ex: DEC-002 pe ECB SDMX)

Pentru PRD-400, anticipăm DEC-urile probabile:

- **DEC-006 (probabil):** Ce date COT folosim — TFF (Traders in Financial Futures) vs Disaggregated vs Legacy. Trei opțiuni cu trade-offs de granularitate vs lungime istorică.
- **DEC-007 (probabil):** Cum tratăm lag-ul de 3 zile al COT (publicat vinerea pentru pozițiile de marți). Pentru semnal real-time, lag-ul matters.
- **DEC-008 (probabil):** Pragurile pentru "extreme positioning" — percentile 80, 90, 95? Motivate cum? Din literatură, din historical distribution, sau alegere fixă?

Aceste DEC-uri se scriu **înainte** de a calcula nimic, nu după.

---

## Lecția 4 — Working tree necommited e datorie tehnică ascunsă

### Ce s-a întâmplat

Notebook-urile 02 și 02b au stat necommited zile întregi prin multiple modificări și sesiuni Claude Code. Au fost salvate doar la finalul PRD-200 prin `[PRD-200/FINALIZE]`. Risc real: dacă PC-ul ar fi crashat, am fi pierdut diagnosticul de regime switching și ar fi trebuit refăcut — incluzând toate verdictele numerice care au informat reformularea AC-6.

### Fix

După fiecare CC care produce **artefacte non-cod** (notebook-uri, figuri, decizii pe hârtie), commit imediat în același CC. Nu lăsăm pe "după review-ul utilizatorului". Review-ul vizual se poate face pe un commit care e ulterior amend-uit dacă apar modificări — git oferă flexibilitatea asta exact pentru cazul ăsta.

Regulă operațională: **fiecare CC se închide cu working tree clean.** Dacă nu se poate, e un sub-task lipsă în CC, nu un detaliu pe care îl rezolvăm "mai târziu".

---

## Lecția 5 — "Done" nu înseamnă "perfect", înseamnă "verificat și documentat"

### Ce s-a întâmplat

PRD-200 e Done cu **AC-9 outstanding** (regime detector). Asta nu e un eșec — e onestitate. Stratul 2 funcționează, dar are o limitare cunoscută (regime switching) care necesită un Stratul 3 sau un PRD nou pentru detector explicit. Marcarea Done parțial cu AC-9 outstanding e mai onest decât:

- Forțarea AC-9 într-un PRD care nu e responsabil pentru implementarea lui (ar fi extins scope-ul indefinit)
- Marcarea PRD-200 ca "Cancelled" sau "Blocked" (ar fi pierdut munca validată)
- Ignorarea AC-9 (ar fi pierdut tracking-ul dependenței downstream)

### Fix

PRD-urile viitoare au voie să fie marcate Done cu AC-uri outstanding **dacă** acele AC-uri sunt:

- (a) Cross-PRD dependencies clar identificate
- (b) Tracked într-un PRD viitor specific, sau în Notes ca trigger pentru un PRD nou
- (c) Documentate într-un DEC care explică de ce nu sunt implementate în PRD-ul curent

Această regulă **nu** e o portiță pentru a marca PRD-uri Done prematur. E o recunoaștere că arhitecturile reale au dependențe care traversează granițele de PRD, și că forțarea totul în interiorul unui singur PRD generează scope creep și PRD-uri care nu se mai termină.

---

## Aplicare la PRD-400 — concret

Cele 5 lecții se traduc în următoarele decizii pentru PRD-400:

1. **AC-urile vor fi range-uri sau condiționale, nu praguri fixe scrise pe baza intuiției.** Dacă un AC necesită un prag fix, pragul vine din literatură + DEC explicit, nu din presupunere.

2. **PRD-400 va avea un CC explicit "COT positioning regime diagnostic"** între CC-ul de pipeline și CC-ul de validare. Ordinea: pipeline → diagnostic → validation.

3. **PRD-400 va anticipa în Notes 2-3 DEC-uri probabile** (DEC-006, DEC-007, DEC-008) și le va numerota din start ca placeholder-uri. Dacă nu sunt necesare, se șterg. Mai bine o anticipare în plus decât una în minus.

4. **Fiecare CC al PRD-400 se închide cu working tree clean.** Notebook-urile, figurile, decisions — toate commited în CC-ul care le produce, nu batch la final.

5. **PRD-400 acceptă explicit posibilitatea de AC-uri outstanding** dacă diagnosticul descoperă fenomene care depășesc scope-ul (ex: "COT delta corelează cu semnal doar pentru sub-categoria X, dar implementarea sub-categoriilor e responsabilitatea PRD-401 Tactical Positioning").

---

## Meta-lecție

Acestea 5 lecții nu sunt despre PRD-200 specific. Sunt despre **rigoare metodologică în research empiric**. Toate apar în orice proiect quant serios la un moment dat. Faptul că le-am descoperit acum, în PRD-200, înseamnă că le aplicăm de la PRD-400 înainte. Faptul că le-am documentat în acest fișier înseamnă că nu le pierdem peste 3 luni când contextul s-a estompat.

Un proiect quant fără retrospective documentate repetă aceleași greșeli la fiecare layer. Un proiect cu retrospective acumulează rigoare exponențial.

---

**Următoarea revizie a acestui document:** după PRD-400 Done, adăugăm Lessons 6+ dacă apar.
