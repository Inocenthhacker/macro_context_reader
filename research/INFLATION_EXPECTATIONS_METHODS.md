# EUR Inflation Expectations — Methods Research Log

---

## 1. Header și Metadata

> **Generated:** 2026-04-10
> **Status:** Living document — updated as methods are implemented and validated
> **Purpose:** Reference pentru ordonarea implementării și compararea empirică
> **Consumer:** PRD-200 (Real Rate Differential) și PRD-uri viitoare pentru upgrade-uri
> **Criteriul de evaluare:** ACURATEȚE empirică validată. NU simplicitate, NU cost de implementare.

---

## 2. Context și Problema Centrală

Componenta EUR a formulei `real_rate_differential` din PRD-200 necesită o estimare a **așteptărilor de inflație forward-looking pe 2 ani** pentru zona euro. Formula completă din arhitectura proiectului este:

```
real_rate_differential = (US_2Y_yield − US_breakeven_2Y) − (EUR_2Y_rate − EUR_inflation_expectations_2Y)
```

Pe partea US, FRED oferă direct `DFII2` (2-Year Treasury Inflation-Indexed Security, Constant Maturity) — un breakeven derivat din TIPS, actualizat zilnic, forward-looking. Această simetrie metodologică este critică: dacă partea US este forward-looking iar partea EUR este backward-looking, `real_rate_differential` devine un indicador hibrid care compară mere cu pere. Divergențele artificiale vor apărea în fiecare punct de inflexiune al ciclului inflaționist — exact momentele în care semnalul contează cel mai mult.

ECB_FEASIBILITY_001.md (2026-04-10) a confirmat că **ECB Data Portal nu publică date de inflation-linked swaps** (CASE D — RED). Codurile EUSWI2, EUHCPT2Y_ICAP etc. există în schema SDMX dar au zero serii de date în dataflow-ul FM public (doar 114 serii din 103,362 coduri în codelist). Singurul proxy ECB disponibil este HICP YoY (`ICP.M.U2.N.000000.4.ANR`) — o măsură backward-looking, lunară, cu lag de ~4 luni.

Folosirea HICP YoY ca proxy direct pentru așteptări de inflație este **inadmisibilă metodologic** ca soluție permanentă. Literatura ECB documentează că inflația realizată și așteptările de inflație pot diverge semnificativ — în 2022, HICP a fost 10%+ în timp ce așteptările pe 2 ani au rămas ancorate sub 3%, deoarece piața anticipa că șocul era tranzitoriu. Un `real_rate_differential` bazat pe HICP în loc de așteptări forward ar fi generat un semnal fals masiv în acea perioadă.

Acest document cataloghează **toate metodele disponibile** pentru estimarea așteptărilor de inflație EUR, ordonate după acuratețea empirică documentată, cu scopul de a stabili ordinea de implementare în PRD-200 și PRD-urile ulterioare. Existența mai multor surse independente permite cross-validation și detectarea regimurilor unde o metodă individuală devine nesigură (e.g., primele de lichiditate se extind în criză, surveys lag-uiesc la puncte de inflexiune).

---

## 3. Tabel Comparativ de Acuratețe (Rezumat)

| # | Metoda | Acuratețe empirică | Frecvență | Forward-looking | Cost | Status implementare | Sursa primară de validare |
|---|--------|-------------------|-----------|-----------------|------|--------------------|-----------------------------|
| 1 | SPF + OATei DNS combination | Superior (Highest free) | Daily (derived) | ✅ Yes | Free | Not Started | ECB Blog March 2026 [source not yet verified] |
| 2 | OATei Breakeven (pură) | High | Daily | ✅ Yes | Free | Not Started | Fed FEDS 2025-041 [source not yet verified] |
| 3 | ILS via Bloomberg/Refinitiv | Highest (theoretical) | Daily | ✅ Yes | €6k–24k/year | Rejected (cost) | Reis 2020 [source not yet verified], ECB Economic Bulletin |
| 4 | ECB Survey of Professional Forecasters (SPF) | High (quarterly) | Quarterly | ✅ Yes | Free | Not Started | ECB Economic Bulletin 8/2025 [source not yet verified] |
| 5 | Bundesbank inflation-linked Bunds | High | Daily | ✅ Yes | Free | Not Started | Bundesbank Statistical Data Service |
| 6 | HICP YoY (baseline backward-looking) | None (backward) | Monthly | ❌ No | Free | Baseline only | ECB Working Paper 830 |
| 7 | ECB Consumer Expectations Survey (CES) | Medium | Monthly | ✅ Yes | Free | Not Started | ECB Economic Bulletin 8/2025 [source not yet verified] |
| 8 | Consensus Economics forecasts | Medium-High | Monthly | ✅ Yes | Paid (~€2k/year) | Rejected (cost) | CFM Discussion Paper 2023-01 [source not yet verified] |

**Nota pe acuratețe:** Ordinea reflectă consensul din literatura academică și rapoartele băncilor centrale. Valorile exacte de corelație și RMSE vor fi completate în Secțiunea 15 (Log de implementare) pe măsură ce fiecare metodă este implementată și backtestată pe date reale.

---

## 4. Metoda 1 — ECB SPF + OATei cu Dynamic Nelson-Siegel (combinație)

### Descriere tehnică

Modelul Dynamic Nelson-Siegel (DNS) extins combină datele din sondajul ECB SPF (trimestrial, anchored, expert-based) cu randamentele obligațiunilor inflation-linked (OATei, daily, market-based) pentru a genera o curbă zilnică a așteptărilor de inflație pe multiple orizonturi.

Modelul original Nelson-Siegel (1987) parametrizează curba de randamente cu 3 factori: nivel (β₀), pantă (β₁) și curbură (β₂), plus un parametru de decădere (λ). Extensia DNS adaugă dinamică temporală — factorii variază în timp conform unui proces VAR(1).

Combinația SPF + market data funcționează astfel:
- SPF furnizează ancorele trimestriale (1Y, 2Y, 5Y ahead) — stabile, neafectate de primele de lichiditate
- OATei breakeven furnizează variația zilnică — captează surprizele de piață între publicările SPF
- DNS interpolează între cele două surse, producând estimări zilnice care respectă ancorele SPF dar reflectă dinamica pieței

### Acuratețe empirică

- ECB Blog "From peak back to target" (March 2026) [source not yet verified]: confirmă că modelul combinat produce estimări mai robuste decât fiecare sursă individuală, în special în perioade de volatilitate ridicată (2022-2024)
- Burban & Guilloux-Nefussi (Banque de France Eco Notepad, 18 September 2025) [source not yet verified]: documentează modelul DNS extins cu SPF + market data, demonstrând superioritatea față de abordări pure market-based sau pure survey-based
- Limitare în scenarii de stres: când primele de lichiditate pe OATei se extind (criza 2008, martie 2020), componenta market-based introduce zgomot → modelul DNS atenuează parțial prin ancorele SPF, dar nu elimină complet distorsiunea
- [needs verification]: RMSE specifice relative la alte metode

### Surse de date

- **ECB SPF:** https://data.ecb.europa.eu/data/datasets/SPF — trimestrial, din 1999
  - Cod ECB: `SPF.Q.U2.ALL.HICP.POINT.2Y` [needs verification — cod exact pentru 2Y ahead]
  - Format: SDMX/CSV via ecbdata library
- **OATei randamente:** Agence France Trésor https://www.aft.gouv.fr/en/oateuroi-key-figures
  - Daily, din 2001
  - Format: CSV descărcabil manual + scraping AFT website
- **Model DNS:** implementare proprie necesară (scipy.optimize, statsmodels)

### Acces tehnic

- ECB SPF: accesibil via `ecbdata.ecbdata.get_series()` (confirmat ECB_FEASIBILITY_001.md)
- OATei: nu există API public oficial AFT — necesită scraping sau surse terțe (Bundesbank, ECB YC)
- DNS model: implementare custom — librării: `scipy.optimize.minimize` pentru calibrare Nelson-Siegel, `statsmodels` pentru VAR(1) pe factori
- Complexitate de implementare: **ridicată** — necesită Fazele A, B, C complete și validate individual

### Referințe

- ECB Blog "From peak back to target" (March 2026) [source not yet verified]
- Burban, T. & Guilloux-Nefussi, S. (2025). "The Anchoring of Inflation Expectations in the Euro Area." Banque de France Eco Notepad, 18 September 2025 [source not yet verified]
- Nelson, C. & Siegel, A. (1987). "Parsimonious Modeling of Yield Curves." *Journal of Business*, 60(4), 473-489. DOI: 10.1086/296409
- Diebold, F. & Li, C. (2006). "Forecasting the term structure of government bond yields." *Journal of Econometrics*, 130(2), 337-364. DOI: 10.1016/j.jeconom.2005.03.005

### Status implementare

**Not Started** — Faza D în ordinea de implementare. Necesită completarea Fazelor A (SPF), B (OATei), C (Bundesbank) înainte.

---

## 5. Metoda 2 — OATei Breakeven (pură)

### Descriere tehnică

OAT€i (Obligations Assimilables du Trésor indexées sur l'Inflation en zone euro) sunt obligațiuni suverane franceze indexate la HICP ex-tobacco al zonei euro. Emise de Agence France Trésor din 2001, acestea au o piață activă cu orizonturi multiple (aproximativ 2Y, 5Y, 10Y, 15Y, 30Y — maturitățile variază în funcție de emisiunile în circulație).

Calculul breakeven:
```
breakeven_inflation = yield(OAT nominal) − yield(OAT€i real)
```

Pentru a obține un breakeven la maturitate fixă (exact 2Y), este necesară interpolarea pe curba de randamente reale (OATei) și nominale (OAT), cel mai frecvent cu modelul Nelson-Siegel.

Breakeven-ul conține atât așteptarea de inflație cât și o **primă de risc de inflație** (inflation risk premium, IRP):
```
breakeven = inflation_expectation + inflation_risk_premium
```

IRP este de regulă pozitivă (investitorii cer compensație pentru incertitudinea inflației), ceea ce înseamnă că breakeven-ul tinde să supraestimeze ușor așteptarea pură de inflație.

### Acuratețe empirică

- Fed FEDS 2025-041 "How Stable are Inflation Expectations in the Euro Area?" [source not yet verified]: documentează stabilitatea breakeven-urilor din obligațiuni inflation-linked ca măsură a așteptărilor EUR
- ECB Working Paper 830 (Ejsing, García, Werner 2007): documentează construcția curbei term structure din OATei și metodologia Nelson-Siegel aplicată
- Bias de lichiditate: [needs verification] ~10-15bp vs. nominal OAT în condiții normale de piață, poate crește la 30-50bp+ în criză (martie 2020, toamna 2008)
- Performanță în criză 2022-2024: breakeven-urile pe 2Y au crescut rapid la începutul ciclului inflaționist, captând corect direcția, dar cu supraestimare temporară datorită IRP ridicat
- Avantaj vs. ILS: gratuit, transparent, bazat pe obligațiuni reale tranzacționate (nu derivate OTC)
- Dezavantaj vs. ILS: conține IRP care nu poate fi separat fără model suplimentar

### Surse de date

- **Agence France Trésor (AFT):** https://www.aft.gouv.fr/en/oateuroi-key-figures
  - Date zilnice de randament pentru fiecare OATei în circulație
  - Format: HTML/PDF — necesită scraping
  - Istoric: din 2001 (prima emisiune OATei)
- **ECB Yield Curve (proxy):** ECB publică curba de randamente NOMINALE guvernamentale (confirmat: `YC.B.U2.EUR.4F.G_N_C.SV_C_YM.SR_2Y`) dar **NU** publică curba reală/inflation-linked (confirmat ECB_FEASIBILITY_001.md — niciun YC series cu prefix G_I)
- **Bundesbank:** publică randamente individuale OATei [needs verification — cod de serie specific]
- **FRED:** `IRLTLT01EZM156N` [needs verification] — Long-term government bond yields, EUR area

### Acces tehnic

- AFT website: scraping cu `requests` + `BeautifulSoup4` — pagina OATei key figures
- Alternativ: Bundesbank SDMX API pentru randamente individuale ale obligațiunilor
- Construcția curbei Nelson-Siegel: `scipy.optimize.curve_fit` pe randamentele punctuale OATei
- Interpolarea la 2Y: evaluare curba Nelson-Siegel la τ = 2.0
- Librării: `requests`, `beautifulsoup4`, `scipy`, `pandas`

### Referințe

- Fed FEDS 2025-041. "How Stable are Inflation Expectations in the Euro Area?" [source not yet verified]
- Ejsing, J., García, J.A. & Werner, T. (2007). "The term structure of euro area break-even inflation rates: The impact of seasonality." ECB Working Paper No. 830. https://www.ecb.europa.eu/pub/pdf/scpwps/ecbwp830.pdf
- Agence France Trésor — OAT€i documentation: https://www.aft.gouv.fr/en/oateuroi-key-figures
- Hördahl, P. & Tristani, O. (2014). "Inflation risk premia in the euro area." *Journal of the European Economic Association*, 12(6), 1571-1600. [source not yet verified — DOI needs verification]

### Status implementare

**Not Started** — Faza B în ordinea de implementare.

---

## 6. Metoda 3 — ECB Survey of Professional Forecasters (SPF)

### Descriere tehnică

ECB Survey of Professional Forecasters este un sondaj trimestrial realizat de ECB din 1999, adresat unui panel de ~60 de economiști profesioniști din instituții financiare, centre de cercetare și organizații internaționale. Respondenții furnizează forecast-uri punctuale și distribuții de probabilitate pentru inflația HICP pe orizonturi de 1 an, 2 ani și 5 ani înainte, plus un orizont pe termen lung.

SPF este considerat benchmark-ul standard pentru așteptările de inflație ancorate (anchored inflation expectations) în literatura academică europeană. ECB îl folosește intern ca input principal pentru evaluarea anchoring-ului așteptărilor.

### Acuratețe empirică

- ECB Economic Bulletin Issue 8/2025 [source not yet verified]: raportează că SPF a rămas "firmly anchored around 2%" pe tot parcursul crizei inflaționiste 2022-2024, chiar la vârful HICP de 10%+. Acest comportament confirmă robustețea SPF ca indicator de așteptări ancorate.
- Burban & Guilloux-Nefussi (Banque de France 2025) [source not yet verified]: SPF folosit ca benchmark standard în literatura anchoring — modelul DNS îl folosește ca ancoră
- Limitare principală: frecvența trimestrială (4 puncte/an) — insuficientă pentru trading timing, dar excelentă pentru direcție structurală
- Limitare secundară: SPF poate lag-ui la puncte de inflexiune bruscă deoarece este un sondaj cu deadline de răspuns, nu o măsură market-based în timp real
- Performanță în 2022: SPF pe 2Y a crescut de la ~1.7% la ~2.4% [needs verification — valori exacte], semnificativ sub HICP realizat de 10% — ceea ce confirmă că profesioniștii au evaluat corect natura tranzitorie a șocului

### Surse de date

- **ECB Data Portal:** https://data.ecb.europa.eu/data/datasets/SPF
  - Cod ECB: `SPF.Q.U2.ALL.HICP.POINT.Q0204` [needs verification — structura exactă a codului pentru 2Y ahead HICP point forecast]
  - Frecvență: trimestrială (Q1=feb, Q2=mai, Q3=aug, Q4=nov — [needs verification])
  - Format: SDMX/CSV via ecbdata library
  - Istoric: din 1999 Q1
- **ECB SPF microdata:** https://www.ecb.europa.eu/stats/ecb_surveys/survey_of_professional_forecasters/html/index.en.html

### Acces tehnic

- Via `ecbdata.ecbdata.get_series('SPF.Q.U2.ALL.HICP.POINT.Q0204')` [needs verification — cod exact]
- Alternativ: REST API ECB direct cu `requests`
- Interpolare între trimestre: nearest-neighbor (constant între publicări) sau interpolare liniară
- Librării: `ecbdata>=0.1.1`, `pandas`

### Referințe

- ECB Economic Bulletin Issue 8/2025 [source not yet verified]
- Burban, T. & Guilloux-Nefussi, S. (2025). "The Anchoring of Inflation Expectations in the Euro Area." Banque de France Eco Notepad [source not yet verified]
- ECB Occasional Paper No. 59. "The ECB Survey of Professional Forecasters (SPF) — A review after eight years' experience." https://www.ecb.europa.eu/pub/pdf/scpops/ecbocp59.pdf
- Garcia, J.A. (2003). "An Introduction to the ECB's Survey of Professional Forecasters." ECB Occasional Paper No. 8 [source not yet verified]

### Status implementare

**Not Started** — Faza A (prima metodă de implementat) în ordinea recomandată.

---

## 7. Metoda 4 — Bundesbank Inflation-Linked Bunds

### Descriere tehnică

Germania emite obligațiuni federale indexate la HICP ex-tobacco al zonei euro (inflation-linked Bundesanleihen, cunoscute ca iBunds) din 2006. Tipurile includ:
- **iBund** — maturitate originală 10-30Y
- **iBOBL** — maturitate originală 5Y
- **Inflation-linked Bundesschatzanweisungen** — maturitate originală 2Y [needs verification — dacă există emisiuni cu maturitate originală 2Y]

Calculul breakeven este identic cu cel de la OATei:
```
breakeven_inflation = yield(nominal Bund) − yield(iBund)
```

### Acuratețe empirică

- Avantaj față de OATei: obligațiunile germane sunt considerate benchmark "risk-free" al zonei euro (spread de credit zero vs. OAT care are spread credit Franța)
- Dezavantaj: emisiunile de iBunds sunt mai puține decât OATei → piața este mai puțin lichidă → primă de lichiditate potențial mai mare
- Istoric mai scurt: din 2006 vs. 2001 pentru OATei
- Cross-validation OATei vs. iBund: diferența de breakeven între cele două surse reflectă diferența de primă de lichiditate + primă de credit Franța vs. Germania. Monitorizarea acestei diferențe este un semnal de stres al pieței suverane europene [needs verification — referințe specifice]
- [needs verification]: Studii comparative de acuratețe iBund vs. OATei

### Surse de date

- **Bundesbank Statistical Data Service:** https://www.bundesbank.de/en/statistics/money-and-capital-markets/securities-issues
  - Randamente zilnice pentru fiecare iBund în circulație
  - Format: CSV via Bundesbank Time Series Database
  - API: Bundesbank SDMX REST API — https://api.statistiken.bundesbank.de/
  - [needs verification — coduri de serie specifice pentru iBund yields]
- **Deutsche Finanzagentur:** https://www.deutsche-finanzagentur.de/en/ — emitentul oficial

### Acces tehnic

- Bundesbank SDMX API: `requests` direct la `https://api.statistiken.bundesbank.de/rest/data/{flow}/{key}`
- Format: SDMX JSON/CSV similar cu ECB
- Construcția curbei: identică cu OATei (Nelson-Siegel pe randamente punctuale)
- Librării: `requests`, `scipy`, `pandas`
- Complexitate: similară cu OATei (Metoda 2)

### Referințe

- Bundesbank Statistical Data Service documentation: https://www.bundesbank.de/en/statistics
- Deutsche Finanzagentur — Inflation-linked securities: https://www.deutsche-finanzagentur.de/en/federal-securities/federal-securities-in-detail/inflation-linked-securities
- [source not yet verified]: Studii Bundesbank specifice pe iBund breakeven accuracy

### Status implementare

**Not Started** — Faza C în ordinea de implementare.

---

## 8. Metoda 5 — Inflation-Linked Swaps prin Bloomberg/Refinitiv

### Descriere tehnică

EUR 2Y Inflation-Linked Swap (ILS) este un derivat OTC (over-the-counter) în care o parte plătește o rată fixă (swap rate) și primește inflația realizată HICP ex-tobacco pe durata contractului. Swap rate-ul reflectă așteptarea pieței de inflație pe orizontul respectiv, plus o primă de risc (care diferă structural de IRP din breakeven-uri).

Ticker Bloomberg: `EUSWI2 Curncy` — EUR 2Y Inflation Swap Zero Coupon

ILS este considerat teoretic cea mai curată măsură market-based a așteptărilor de inflație:
- Zero credit risk (colateralizat bilateral)
- Zero funding cost (swap, nu cash bond)
- Piață OTC lichidă cu quoting zilnic de către dealer banks

### Acuratețe empirică

- Reis, R. (2020) [source not yet verified]: CFM Discussion Paper, analiza ILS ca benchmark pentru așteptări de inflație europeană
- ECB Economic Bulletin: folosit regulat ca referință "market-based inflation expectations" în analizele ECB
- Avantaj: zero primă de lichiditate/credit (vs. breakeven din obligațiuni)
- Dezavantaj: primă de risc a inflației (IRP) rămâne inclusă — similară dar nu identică cu cea din breakeven-uri
- Performanță în criză 2008: ILS au avut volatilitate extremă datorită riscului de contrapartidă OTC necolateralizat (situație remediată post-2012 prin obligația de colateralizare)
- Performanță în 2022-2024: ILS pe 2Y a crescut la ~3-4% [needs verification] reflectând presiunile inflaționiste, apoi a scăzut rapid pe măsură ce ECB a ridicat ratele

### Surse de date

- **Bloomberg Terminal:** `EUSWI2 Curncy` — necesită abonament ($2,000-$24,000/an)
- **Refinitiv/LSEG Workspace:** cod RIC echivalent [needs verification]
- **ECB Data Portal:** INDISPONIBIL — confirmat ECB_FEASIBILITY_001.md (codurile EUSWI2, EUHCPT2Y_ICAP există în codelist dar au zero date publice)
- **FRED:** nu publică ILS EUR [needs verification]

### Acces tehnic

- Bloomberg API (BLPAPI): Python `blpapi` package — necesită Bloomberg Terminal activ
- Refinitiv: `eikon` sau `refinitiv.data` Python package — necesită abonament
- **Nu există sursă gratuită pentru ILS EUR.**

### Referințe

- Reis, R. (2020). "The People versus the Markets: A Parsimonious Model of Inflation Expectations." CFM Discussion Paper 2023-01 [source not yet verified — verificare an exact și DOI]
- ECB Economic Bulletin — multiple ediții citează ILS ca referință market-based
- Fleckenstein, M., Longstaff, F. & Lustig, H. (2014). "The TIPS-Treasury Bond Puzzle." *Journal of Finance*, 69(5), 2151-2197 [source not yet verified — relevantă pentru analogia US TIPS vs. ILS]

### Status implementare

**Rejected** — Cost incompatibil cu natura open-source a proiectului (minim €6,000/an pentru orice sursă de date ILS). Folosit ca benchmark teoretic "gold standard" pentru validarea celorlalte metode: referințele academice care citează ILS confirmă că alternativele gratuite trebuie să aproximeze comportamentul ILS.

---

## 9. Metoda 6 — HICP YoY (Baseline Backward-Looking)

### Descriere tehnică

Harmonised Index of Consumer Prices (HICP) este indicele oficial de inflație al zonei euro, calculat de Eurostat. HICP YoY (Year-over-Year) măsoară schimbarea procentuală a nivelului general al prețurilor față de aceeași lună a anului precedent.

HICP este o **măsură backward-looking**: raportează inflația **realizată**, nu inflația **așteptată**. Publicarea are un lag de ~2-4 săptămâni față de luna de referință (flash estimate ~30 zile, final ~45 zile [needs verification]).

### Acuratețe empirică

- **HICP este inadmisibil ca predictor forward-looking.** ECB Working Paper 830 (Ejsing, García, Werner 2007) explică de ce breakeven-urile din obligațiuni inflation-linked sunt superioare inflației realizate ca indicator al așteptărilor.
- Demonstrație empirică: în Q1 2022, HICP YoY era ~5%. Așteptările pe 2Y (SPF, ILS) erau ~2-2.5%. Real_rate_differential calculat cu HICP ar fi indicat rate reale mult mai negative decât cele indicate de așteptări — generând un semnal fals de EUR weakness relativă.
- **Rolul în acest proiect:** HICP YoY este inclus exclusiv ca **null hypothesis / baseline de comparație**. Dacă o metodă forward-looking implementată nu bate HICP YoY naiv în corelația cu EUR/USD, aceasta semnalează o problemă de implementare sau de model, nu superioritatea HICP.
- Utilitate secundară: HICP servește ca input pentru calculul breakeven-urilor "backward" (`real_rate_naive = nominal_rate - HICP_YoY`) care pot fi comparate cu breakeven-urile market-based.

### Surse de date

- **ECB Data Portal:** `ICP.M.U2.N.000000.4.ANR` — HICP overall index, annual rate of change
  - Confirmat ECB_FEASIBILITY_001.md: HTTP 200, 84 obs, 2019-01 → 2025-12, monthly, zero gaps
  - Acces: `ecbdata.ecbdata.get_series('ICP.M.U2.N.000000.4.ANR')`
- **FRED:** `EA19CPALTT01GYM` [needs verification] — HICP zone euro via OECD

### Acces tehnic

- Via ecbdata library (confirmat funcțional) sau requests direct la ECB REST API
- Zero complexitate — download + parse CSV
- Librării: `ecbdata>=0.1.1` sau `requests`, `pandas`

### Referințe

- Ejsing, J., García, J.A. & Werner, T. (2007). "The term structure of euro area break-even inflation rates." ECB Working Paper No. 830. https://www.ecb.europa.eu/pub/pdf/scpwps/ecbwp830.pdf
- ECB Statistical Data Warehouse — HICP documentation: https://data.ecb.europa.eu/

### Status implementare

**Baseline only** — Implementat ca prima sursă de date disponibilă (confirmat ECB_FEASIBILITY_001.md). Nu va fi folosit ca sursă de semnal — exclusiv ca null hypothesis pentru validare comparativă.

---

## 10. Metoda 7 — ECB Consumer Expectations Survey (CES)

### Descriere tehnică

ECB Consumer Expectations Survey (CES) este un sondaj lunar realizat de ECB din ianuarie 2020 (pilot din 2019), adresat unui panel de ~10,000 gospodării din cele mai mari 6 economii ale zonei euro (Germania, Franța, Italia, Spania, Țările de Jos, Belgia). Respondenții furnizează așteptările lor de inflație pe orizonturi de 1 an și 3 ani înainte.

CES diferă fundamental de SPF: măsoară percepția **consumatorilor** (gospodăriilor), nu a economiștilor profesioniști. Această diferență generează un bias sistematic documentat.

### Acuratețe empirică

- ECB Economic Bulletin Issue 8/2025 [source not yet verified]: documentează așteptările consumatorilor vs. profesioniști
- Bias cunoscut: gospodăriile supraestimează sistematic inflația față de profesioniști și față de piață. Median-ul așteptărilor consumatorilor pe 1Y este de regulă cu [needs verification] puncte procentuale peste SPF și ILS
- Utilitate: CES captează anchoring psychology — dacă așteptările consumatorilor se de-ancorează (cresc persistent peste 3-4%), aceasta e un semnal de alarmă chiar dacă SPF și piața rămân ancorate, deoarece de-anchoring-ul consumatorilor se transmite în negocierile salariale (efectul de runda a doua)
- Limitare: istoria scurtă (din 2020) — nu avem date pre-COVID sau din perioadele anterioare de inflație scăzută
- Performanță în 2022-2024: CES pe 1Y a crescut la ~5-7% [needs verification] — semnificativ peste SPF (~2.4%) și ILS (~3%), confirmând bias-ul consumer dar și captând direcția corectă

### Surse de date

- **ECB CES:** https://www.ecb.europa.eu/stats/ecb_surveys/consumer_exp_survey/html/index.en.html
  - Publicare: lunar, cu lag de ~6 săptămâni [needs verification]
  - Format: descărcabil ca Excel/CSV de pe ECB website
  - Cod ECB SDMX: [needs verification]
  - Istoric: din ianuarie 2020

### Acces tehnic

- Download manual de pe ECB website + parse
- Posibil accesibil via ECB SDMX API [needs verification]
- Librării: `requests`, `pandas`, posibil `openpyxl` pentru Excel parsing

### Referințe

- ECB Economic Bulletin Issue 8/2025 [source not yet verified]
- ECB Consumer Expectations Survey methodology: https://www.ecb.europa.eu/stats/ecb_surveys/consumer_exp_survey/html/index.en.html
- Coibion, O. & Gorodnichenko, Y. (2015). "Information Rigidity and the Expectations Formation Process." *American Economic Review*, 105(8), 2644-2678. DOI: 10.1257/aer.20110306 [source not yet verified — referință clasică pe formarea așteptărilor consumatorilor]

### Status implementare

**Not Started** — Deprioritized. Folosit eventual ca secondary signal pentru monitorizarea de-anchoring-ului așteptărilor consumatorilor, nu ca sursă principală.

---

## 11. Metoda 8 — Consensus Economics Forecasts

### Descriere tehnică

Consensus Economics este un serviciu privat de sondaje economice (fondat 1989) care colectează lunar previziunile unui panel larg de economiști (~250 participanți [needs verification]) din instituții financiare, centre de cercetare și guverne. Publică forecast-uri pentru inflație, PIB, rate de dobândă etc. pe multiple orizonturi (anul curent, anul viitor, termen lung).

Frecvența lunară (vs. trimestrială SPF) și panelul mai larg sunt avantajele principale față de ECB SPF.

### Acuratețe empirică

- CFM Discussion Paper 2023-01 (LSE, Ricardo Reis) [source not yet verified]: analizează forecast-urile Consensus Economics în contextul european
- Consensus Economics este utilizat ca input în modelele DNS ale ECB și ale altor bănci centrale, alături de SPF
- [needs verification]: Studii comparative directe Consensus vs. SPF pe acuratețe — literatura sugerează performanță similară, cu avantajul frecvenței lunare
- Limitare: datele sunt proprietare și nu pot fi redistribuite — impact pe reproducibilitatea proiectului

### Surse de date

- **Consensus Economics:** https://www.consensuseconomics.com/ — abonament necesar (~€2,000/an [needs verification])
- Format: PDF lunar + bază de date proprietară (acces via portal web sau API [needs verification])
- Nu există alternativă gratuită echivalentă

### Acces tehnic

- Portal web Consensus Economics cu login
- API proprietar [needs verification — dacă există]
- Alternativ: datele Consensus sunt uneori citate în publicațiile ECB/IMF — dar nu suficient granular pentru uz sistematic

### Referințe

- Reis, R. (2023). "The People versus the Markets: A Parsimonious Model of Inflation Expectations." CFM Discussion Paper 2023-01 [source not yet verified]
- Consensus Economics: https://www.consensuseconomics.com/

### Status implementare

**Rejected** — Cost incompatibil cu proiectul (~€2,000/an). Menționat pentru completitudine și ca referință pentru validare: dacă publicații ECB/IMF citează numere Consensus, acestea pot fi folosite punctual ca benchmark.

---

## 12. Ordinea de Implementare Recomandată

Bazat **EXCLUSIV** pe acuratețea empirică validată:

### Faza A — Metoda 3: ECB SPF (Foundation)

**Motiv:** Cel mai validat empiric în criza inflaționistă 2022-2024. Anchor stabil confirmat de ECB Economic Bulletin 8/2025. Deși trimestrial, este input-ul principal în toate modelele DNS ale ECB. Implementarea e simplă (download ECB SDMX) iar datele acoperă 1999-prezent — cel mai lung istoric disponibil gratuit.

**Livrabil:** Modul Python care descarcă SPF 2Y HICP point forecast, interpoleaza între trimestre, și expune interfața `InflationExpectationsMethod`.

### Faza B — Metoda 2: OATei Breakeven (Daily frequency)

**Motiv:** Adaugă frecvență zilnică market-based. Breakeven-urile din obligațiuni inflation-linked sunt validate independent (Fed FEDS 2025-041). Permite cross-validation cu SPF: când breakeven-ul deviază semnificativ de la SPF, aceasta semnalează fie o schimbare de regim (SPF lag-uiește), fie o distorsiune de primă de lichiditate (breakeven distorsionat).

**Livrabil:** Modul Python care scrapează randamente OATei de la AFT, construiește curba Nelson-Siegel reală, calculează breakeven 2Y, și expune interfața comună.

### Faza C — Metoda 4: Bundesbank ILB (Cross-validation)

**Motiv:** A doua sursă market-based din alt emitent suveran. Permite identificarea primei de lichiditate specifice Franței vs. Germaniei. Spread-ul OATei−iBund breakeven este un indicator de stres suveran eurozon util și pentru Stratul 3 (divergence).

**Livrabil:** Modul Python care descarcă iBund yields de la Bundesbank API, calculează breakeven 2Y german, și expune interfața comună.

### Faza D — Metoda 1 composită: SPF + OATei + Bundesbank DNS

**Motiv:** Combinația prin model Dynamic Nelson-Siegel reprezintă state-of-the-art conform ECB Blog 2026. Necesită ca Fazele A, B, C să fie complete și validate individual — fiecare componentă trebuie să funcționeze standalone înainte de a le combina.

**Livrabil:** Modul DNS care calibrează factori Nelson-Siegel pe datele combinate SPF + OATei + iBund, produce estimări zilnice interpolate, și expune interfața comună cu `accuracy_tier = "composite"`.

### Faza E — Metoda 6: HICP YoY ca baseline

**Motiv:** Implementat **ULTIMUL** ca null hypothesis pentru validare. Verifică dacă metodele forward din Fazele A-D depășesc semnificativ baseline-ul backward-looking în corelația cu EUR/USD. Dacă nu depășesc — avem o problemă de implementare.

**Livrabil:** Modul Python minimal care descarcă HICP YoY de la ECB, expune interfața comună. Comparat cu Fazele A-D pe metricile din Secțiunea 14.

### Metode rejected (cost)

- **Metoda 5: Bloomberg ILS** — cost incompatibil (~€6,000-24,000/an). Folosit doar ca referință academică.
- **Metoda 8: Consensus Economics** — cost incompatibil (~€2,000/an). Citat punctual din publicații ECB/IMF.

### Metode deprioritized

- **Metoda 7: ECB CES** — bias consumer, istoric scurt (din 2020). Implementat eventual ca secondary signal pentru monitorizarea de-anchoring-ului gospodăriilor, nu ca sursă principală de așteptări de inflație.

---

## 13. Interfața Comună (Pluggable Architecture)

Toate metodele implementate trebuie să respecte următoarea interfață Python, permițând swap-ul transparent între surse:

```python
from typing import Protocol
from datetime import datetime
import pandas as pd


class InflationExpectationsMethod(Protocol):
    name: str
    frequency: str  # "daily", "monthly", "quarterly"
    source: str     # "SPF", "OATei", "Bundesbank", "HICP", etc.

    def fetch(self, start: datetime, end: datetime) -> pd.DataFrame:
        """Returns DataFrame with columns: date, expectation_2y, metadata.

        - date: datetime — observation date
        - expectation_2y: float — expected 2Y HICP inflation, annualized %
        - metadata: dict — source-specific info (e.g., survey round, bond ISIN)
        """
        ...

    def get_at_date(self, date: datetime, horizon_years: float = 2.0) -> float:
        """Returns expected inflation at given horizon, interpolated if needed.

        For quarterly sources (SPF): returns latest available value.
        For daily sources (OATei, Bundesbank): returns value at date.
        For monthly sources (HICP, CES): returns value for the month containing date.
        """
        ...

    def get_metadata(self) -> dict:
        """Returns method metadata for output tagging.

        Keys:
        - accuracy_tier: str — "composite", "market_daily", "survey_quarterly", "backward_baseline"
        - empirical_validation_source: str — primary academic reference
        - known_biases: list[str] — e.g., ["liquidity_premium", "inflation_risk_premium"]
        - last_updated: datetime — last data point available
        - covers_from: datetime — earliest data point available
        """
        ...
```

**Utilizare în PRD-200:**

```python
# PRD-200 real_rate_differential acceptă orice InflationExpectationsMethod
def compute_real_rate_diff(
    us_2y: float,
    us_breakeven_2y: float,
    eur_2y_rate: float,
    eur_inflation_method: InflationExpectationsMethod,
    date: datetime,
) -> dict:
    eur_inflation_2y = eur_inflation_method.get_at_date(date, horizon_years=2.0)
    rrd = (us_2y - us_breakeven_2y) - (eur_2y_rate - eur_inflation_2y)
    return {
        "real_rate_differential": rrd,
        "eur_inflation_source": eur_inflation_method.name,
        "accuracy_tier": eur_inflation_method.get_metadata()["accuracy_tier"],
    }
```

---

## 14. Criterii de Comparație Empirică

Fiecare metodă implementată trebuie evaluată pe următoarele metrici, calculate în mod standardizat pe perioada 2020-01 → present:

1. **Pearson correlation cu EUR/USD** pe ferestre rolling (30d, 90d, 180d, 365d) — corelația `real_rate_differential` calculat cu metoda respectivă vs. nivel EUR/USD
2. **Lead/lag analysis** (cross-correlation function) — metoda e leading sau lagging vs. EUR/USD? Optim: leading cu 5-20 zile de business
3. **Stabilitate în timp** (variance of rolling correlation) — o metodă cu corelație instabilă e mai puțin utilă decât una cu corelație modestă dar stabilă
4. **Performance în regime shifts** — corelație calculată separat pe 4 sub-perioade:
   - 2020-01 → 2020-06 (COVID shock)
   - 2020-07 → 2021-12 (recovery + incipient inflation)
   - 2022-01 → 2023-06 (inflation crisis + ECB hiking)
   - 2023-07 → present (disinflation + cut cycle)
5. **Corelație cu metoda benchmark** — SPF ca referință inițială (Faza A), DNS composite ca referință finală (Faza D). Deviația semnificativă necesită investigare.
6. **Cost de tranziție la regim schimbat** — cât de repede detectează schimbări? Măsurat ca lag-ul (în zile) de la prima mișcare a ILS Bloomberg (benchmark teoretic, obținut din publicații ECB) la prima mișcare a metodei respective
7. **Robustețe la revizuiri de date** — relevant pentru SPF (revizuiri ale prognozelor) și HICP (flash vs. final). Diferența absolută medie între prima estimare și valoarea finală.

---

## 15. Log de Implementare

Se completează pe parcurs. Format:

### Method 3 — ECB SPF
- **Implemented:** —
- **Module:** src/macro_context_reader/market_pricing/inflation_expectations/spf.py
- **Tests:** tests/market_pricing/inflation_expectations/test_spf.py
- **Data artifact:** data/market_pricing/inflation_expectations/spf_hicp_2y.parquet
- **Pearson correlation with EUR/USD (5Y rolling):** —
- **Lead/lag vs EUR/USD:** —
- **Notes:** —

### Method 2 — OATei Breakeven
- **Implemented:** —
- **Module:** src/macro_context_reader/market_pricing/inflation_expectations/oatei.py
- **Tests:** tests/market_pricing/inflation_expectations/test_oatei.py
- **Data artifact:** data/market_pricing/inflation_expectations/oatei_breakeven_2y.parquet
- **Pearson correlation with EUR/USD (5Y rolling):** —
- **Lead/lag vs EUR/USD:** —
- **Notes:** —

### Method 4 — Bundesbank ILB
- **Implemented:** —
- **Module:** src/macro_context_reader/market_pricing/inflation_expectations/bundesbank_ilb.py
- **Tests:** tests/market_pricing/inflation_expectations/test_bundesbank_ilb.py
- **Data artifact:** data/market_pricing/inflation_expectations/bundesbank_breakeven_2y.parquet
- **Pearson correlation with EUR/USD (5Y rolling):** —
- **Lead/lag vs EUR/USD:** —
- **Notes:** —

### Method 1 — SPF + OATei + Bundesbank DNS Composite
- **Implemented:** —
- **Module:** src/macro_context_reader/market_pricing/inflation_expectations/dns_composite.py
- **Tests:** tests/market_pricing/inflation_expectations/test_dns_composite.py
- **Data artifact:** data/market_pricing/inflation_expectations/dns_composite_2y.parquet
- **Pearson correlation with EUR/USD (5Y rolling):** —
- **Lead/lag vs EUR/USD:** —
- **Notes:** —

### Method 6 — HICP YoY Baseline
- **Implemented:** —
- **Module:** src/macro_context_reader/market_pricing/inflation_expectations/hicp_baseline.py
- **Tests:** tests/market_pricing/inflation_expectations/test_hicp_baseline.py
- **Data artifact:** data/market_pricing/inflation_expectations/hicp_yoy.parquet
- **Pearson correlation with EUR/USD (5Y rolling):** —
- **Lead/lag vs EUR/USD:** —
- **Notes:** Null hypothesis. Dacă alte metode nu bat acest baseline → problemă de implementare.

---

## 16. Referințe Bibliografice

1. **Nelson, C. & Siegel, A. (1987).** "Parsimonious Modeling of Yield Curves." *Journal of Business*, 60(4), 473-489.
   DOI: 10.1086/296409
   https://www.jstor.org/stable/2352957

2. **Ejsing, J., García, J.A. & Werner, T. (2007).** "The term structure of euro area break-even inflation rates: The impact of seasonality." ECB Working Paper No. 830.
   https://www.ecb.europa.eu/pub/pdf/scpwps/ecbwp830.pdf

3. **Diebold, F. & Li, C. (2006).** "Forecasting the term structure of government bond yields." *Journal of Econometrics*, 130(2), 337-364.
   DOI: 10.1016/j.jeconom.2005.03.005

4. **ECB Occasional Paper No. 59.** "The ECB Survey of Professional Forecasters (SPF) — A review after eight years' experience."
   https://www.ecb.europa.eu/pub/pdf/scpops/ecbocp59.pdf

5. **Burban, T. & Guilloux-Nefussi, S. (2025).** "The Anchoring of Inflation Expectations in the Euro Area." Banque de France Eco Notepad, 18 September 2025. [source not yet verified — URL needs verification]

6. **ECB Blog (March 2026).** "From peak back to target." [source not yet verified — URL needs verification]

7. **ECB Economic Bulletin Issue 8/2025.** [source not yet verified — URL needs verification]
   Expected: https://www.ecb.europa.eu/pub/economic-bulletin/html/index.en.html

8. **Fed FEDS 2025-041.** "How Stable are Inflation Expectations in the Euro Area?" [source not yet verified — URL needs verification]
   Expected: https://www.federalreserve.gov/econres/feds/

9. **Reis, R. (2023).** "The People versus the Markets: A Parsimonious Model of Inflation Expectations." CFM Discussion Paper. [source not yet verified — an exact și DOI needs verification]
   Expected: https://www.lse.ac.uk/CFM/publications/discussion-papers

10. **Agence France Trésor — OAT€i Documentation.**
    https://www.aft.gouv.fr/en/oateuroi-key-figures

11. **Bundesbank Statistical Data Service.**
    https://www.bundesbank.de/en/statistics

12. **Deutsche Finanzagentur — Inflation-Linked Securities.**
    https://www.deutsche-finanzagentur.de/en/federal-securities/federal-securities-in-detail/inflation-linked-securities

13. **ECB Consumer Expectations Survey.**
    https://www.ecb.europa.eu/stats/ecb_surveys/consumer_exp_survey/html/index.en.html

14. **Consensus Economics.**
    https://www.consensuseconomics.com/

15. **Coibion, O. & Gorodnichenko, Y. (2015).** "Information Rigidity and the Expectations Formation Process." *American Economic Review*, 105(8), 2644-2678.
    DOI: 10.1257/aer.20110306

16. **Hördahl, P. & Tristani, O. (2014).** "Inflation risk premia in the euro area." *Journal of the European Economic Association*, 12(6), 1571-1600. [source not yet verified — DOI needs verification]

17. **ECB_FEASIBILITY_001.md (2026-04-10).** Internal project research — ECB Data Portal API exploration confirming CASE D (ILS unavailable).
    Path: `research/ECB_FEASIBILITY_001.md`

---

*Document generat: 2026-04-10 | Ultima actualizare: 2026-04-10 | Actualizat la fiecare implementare nouă dintr-o Fază (A→E)*
