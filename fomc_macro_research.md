# Research: Algoritm NLP pe FOMC + Beige Book pentru Trading Forex & Futures
## Macro Context Reader pentru EUR/USD, CFD-uri și Futures pe Rate

> **Generat:** Aprilie 2026  
> **Scope:** Două rapoarte de research consolidate — (1) NLP pe comunicare Fed, (2) Macro Regime Detection pentru EUR/USD  
> **Surse:** Papers peer-reviewed, documentație oficială Fed/ECB/CFTC, GitHub repos verificate

---

## CUPRINS

1. [Contextul și Problema Centrală](#1-contextul-și-problema-centrală)
2. [Arhitectura Sistemului — Cele 4 Straturi](#2-arhitectura-sistemului--cele-4-straturi)
3. [Tools și Platforme Existente](#3-tools-și-platforme-existente)
4. [Research Papers Relevante](#4-research-papers-relevante)
5. [Implementări și Tentative Anterioare](#5-implementări-și-tentative-anterioare)
6. [Cross-Pollination Findings](#6-cross-pollination-findings)
7. [Zone Nevăzute și Riscuri](#7-zone-nevăzute-și-riscuri)
8. [Glosar Tehnic](#8-glosar-tehnic)
9. [Pasul Următor Recomandat](#9-pasul-următor-recomandat)

---

## 1. Contextul și Problema Centrală

### Ce vrei să construiești — și ce NU

Nu vrei un predictor de preț care să îți spună că EUR/USD va fi la 1.0950 mâine. Vrei un **Macro Context Reader** — un sistem care îți spune în orice moment:

> *"Fed-ul e hawkish sau dovish față de ce prețuiește piața? BCE în ce direcție merge? Divergența e mare sau mică? Direcția probabilă a USD e care?"*

**Exemplul concret:** La final de 2024, EUR/USD a crescut masiv. Nu trebuia să prezici nivelul exact. Trebuia să știi că:
- Fed era în ciclu de tăiere de dobânzi (dovish)
- Piața prețuia agresiv mai multe cuts viitoare
- Dolarul era structural slab față de echilibrul fundamental
- → Long EUR/USD, aștepți

Asta e un **macro regime detector**, nu un price predictor. E mai simplu de construit și mult mai robust.

### Cele 4 Sub-Probleme

| # | Sub-problemă | Ce măsoară |
|---|---|---|
| **Stratul 1** | Rhetoric central bank | Ce spune Fed/BCE prin comunicare oficială? (hawkish / dovish / neutral — NLP) |
| **Stratul 2** | Market pricing | Ce prețuiesc piețele că vor face Fed și BCE în 3–12 luni? (OIS forwards, FedWatch) |
| **Stratul 3** | Divergența | Diferența Stratul 1 − Stratul 2 = informația acționabilă |
| **Stratul 4** | Poziționare | Unde sunt deja poziționate instituțiile? (COT report) |

**Output final:**  
`USD_bias = f(Fed_stance, ECB_stance, rate_differential, surprise, positioning)`  
→ Scor de regim actualizat la fiecare eveniment relevant

### De ce diferențialul de rate reale contează mai mult decât cel nominal

Mulți traderi urmăresc rata nominală Fed vs. BCE. Edgeul real vine din **rata reală** (nominală minus inflație așteptată):

```
real_rate_differential = (US_2Y_yield − US_breakeven_2Y) − (EUR_2Y_OIS − EUR_inflation_expectations_2Y)
```

Când inflația din SUA scade dar Fed menține dobânda, rata reală crește → USD se întărește chiar fără acțiuni ale Fed. Dacă nu ajustezi cu inflația, citești greșit semnalul.

---

## 2. Arhitectura Sistemului — Cele 4 Straturi

### Stratul 1: NLP pe Comunicare Fed (și BCE)

**Ce documente procesezi:**

| Document | Frecvență | Horizon temporal al semnalului | Disponibil |
|---|---|---|---|
| FOMC Statement | 8x/an, imediat post-meeting | Ore–zile | federalreserve.gov |
| FOMC Press Conference transcript | 8x/an, imediat | Ore–zile | federalreserve.gov |
| FOMC Minutes | 8x/an, cu 3 săptămâni lag | Zile–săptămâni | federalreserve.gov |
| Fed Governor Speeches | Continuu, ~2–4/săptămână | Zile | federalreserve.gov/speeches |
| Beige Book | 8x/an, 2 săptămâni înainte de meeting | Săptămâni–luni | federalreserve.gov/publications/beige-book |

**Cum funcționează clasificarea NLP:**

Fiecare propoziție din document e clasificată ca:
- **Hawkish** (0): semnalizează tightening, îngrijorare inflație, intenție hike
- **Dovish** (1): semnalizează easing, îngrijorare creștere/ocupare, intenție cut
- **Neutral** (2): fără semnal de politică

Scorul document-level = `(Hawkish_sentences − Dovish_sentences) / Total_sentences`

**Problema specifică a textului Fed:**

Textul Fed NU e text financiar standard. O propoziție ca *"Unemployment declined"* ar fi clasificată negativ de un model generic (cuvântul "declined" = negativ), deși înseamnă că economia merge bine (bullish for rates). Acesta e motivul pentru care modelele antrenate specific pe FOMC (FOMC-RoBERTa, FinBERT-FOMC) sunt superioare modelelor generice.

**Performanța comparată a modelelor (Kim et al., ICAIF 2024):**

| Model | Acuratețe pe text FOMC |
|---|---|
| VADER (rule-based, baseline) | 44.3% |
| FinBERT (pre-antrenat pe text financiar general) | 59.7% |
| FinBERT-FOMC (fine-tunat pe minute FOMC) | 63.8% |
| GPT-4 | 68.2% |
| Llama 3-70B | 79.34% |
| **Performanță umană** | **Semnificativ peste toate modelele** |

**Concluzie practică:** Llama 3 e cel mai precis dar și cel mai scump computațional. FinBERT-FOMC e optim cost/performanță pentru un sistem individual. GPT-4 via API e o opțiune rezonabilă cu prompt engineering bun.

### Stratul 2: Market Pricing — Ce Prețuiesc Piețele

Principalele instrumente care îți spun ce anticipează piața:

- **CME Fed Funds Futures** → probabilitățile implicite de schimbare a ratei la fiecare meeting (CME FedWatch Tool)
- **SOFR Futures** → așteptările de dobândă pe orizont de 1–4 trimestre
- **OIS (Overnight Index Swaps)** → rate forward curate, fără risc de credit
- **EUR/USD 2Y swap spread** → diferențialul de rate anticipat Fed vs. BCE pe 2 ani (cel mai corelat cu EUR/USD pe termen mediu)

### Stratul 3: Surpriza = Semnalul Acționabil

```
surprise_score = NLP_hawkish_score − FedWatch_hawkish_probability
```

Dacă Fed vorbește mai hawkish decât prețuiește piața → USD mai puternic decât anticipat → potențial long USD.

Dacă Fed vorbește mai dovish decât prețuiește piața → oportunitate long EUR/USD.

**Principiul din neuroștiință (Predictive Coding, Friston 2005):**  
Creierul nu procesează stimuli brut — procesează *eroarea de predicție*. Confirmare așteptărilor = zgomot. Surpriza = semnal. Același principiu aplicat trading-ului: nu scorul absolut contează, ci deviația față de așteptări.

### Stratul 4: Poziționarea COT — "Piața Aglomerată"

Un semnal dovish Fed e **puternic** dacă piața nu era deja poziționată long EUR.  
Un semnal dovish Fed e **slab** dacă hedge funds-urile sunt deja la extrem long EUR (nu mai sunt cumpărători de margine).

COT Leveraged Funds la >80th percentile long EUR = piață "aglomerată" = risc de reversal chiar cu semnal macro corect.

### Ierarhia Surselor de Semnal (după frecvență și orizont)

| Stratul tău | Frecvență | Orizont semnalului | Rol în sistem |
|---|---|---|---|
| NLP speech Fed | Per eveniment | Ore–zile | Timing |
| CME FedWatch | Zilnic | Zile | Calibrare surpriză |
| FRED rate differential real | Săptămânal | Săptămâni | Direcție structurală |
| COT positioning | Săptămânal | Săptămâni–luni | Filtru risc |
| Beige Book district sentiment | 8x/an | Luni | Confirmare macro |

**Regula de ierarhie:** Semnalele cu frecvență joasă dau direcția. Cele cu frecvență înaltă dau timing-ul. Nu intra contra-trend față de semnalele structurale bazat pe un singur speech.

---

## 3. Tools și Platforme Existente

### 3.1 NLP — Modele Pre-Antrenate

#### FOMC-RoBERTa (gtfintechlab / Georgia Tech FinTech Lab)
**Cel mai direct aplicabil model NLP pentru sistemul tău.**

- **Ce face:** Clasifică fiecare propoziție din documente FOMC în hawkish / dovish / neutral, folosind RoBERTa-large fine-tunat pe cel mai mare dataset adnotat manual de text FOMC (minute + speeches + press conferences)
- **Performanță:** State-of-the-art pe task-ul hawkish-dovish la momentul publicării (ACL 2023)
- **Licență:** Open Source — CC BY-NC 4.0 (gratis pentru uz personal/cercetare)
- **Cod de pornire:**

```python
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification, AutoConfig

tokenizer = AutoTokenizer.from_pretrained("gtfintechlab/FOMC-RoBERTa", do_lower_case=True)
model = AutoModelForSequenceClassification.from_pretrained("gtfintechlab/FOMC-RoBERTa", num_labels=3)
config = AutoConfig.from_pretrained("gtfintechlab/FOMC-RoBERTa")

classifier = pipeline('text-classification', model=model, tokenizer=tokenizer, config=config, framework="pt")

results = classifier([
    "Such a directive would imply that any tightening should be implemented promptly.",
    "The labor market has softened and inflation has eased considerably."
], batch_size=32, truncation="only_first")

print(results)
# [{'label': 'HAWKISH', 'score': 0.92}, {'label': 'DOVISH', 'score': 0.88}]
```

- **GitHub:** https://github.com/gtfintechlab/fomc-hawkish-dovish
- **HuggingFace Model:** https://huggingface.co/gtfintechlab/FOMC-RoBERTa
- **Dataset:** https://huggingface.co/datasets/gtfintechlab/fomc_communication
- **Paper ACL 2023:** https://aclanthology.org/2023.acl-long.368

---

#### FinBERT-FOMC (ZiweiChen / Incredible88)
**Alternativă optimizată pentru propoziții complexe cu disjunctori** (*although, while, but*).

- **Ce face:** FinBERT (BERT pre-antrenat pe text financiar) fine-tunat pe minutele FOMC 2006–2023, cu metodă "Sentiment Focus" (SF) care re-labelează propozițiile complexe cu disjunctori
- **Problema rezolvată:** FinBERT standard confundă propoziții ca *"However, the apparent pickup in inflation, while worrisome, was relatively small"* → SF detectează că sentiment-ul net e ambiguu/ușor negativ, nu pozitiv simplu
- **Acuratețe:** 88.3% pe propoziții complexe (vs. 74% FinBERT standard)
- **Licență:** Open Source
- **Cod de pornire:**

```python
from transformers import BertTokenizer, BertForSequenceClassification, pipeline

finbert = BertForSequenceClassification.from_pretrained('ZiweiChen/FinBERT-FOMC', num_labels=3)
tokenizer = BertTokenizer.from_pretrained('ZiweiChen/FinBERT-FOMC')
finbert_fomc = pipeline("text-classification", model=finbert, tokenizer=tokenizer)

sentences = ["Spending on cars increased somewhat but apparently weakened in August"]
results = finbert_fomc(sentences)
print(results)  # [{'label': 'Negative', 'score': 0.994}]
```

- **GitHub:** https://github.com/Incredible88/FinBERT-FOMC
- **HuggingFace:** https://huggingface.co/ZiweiChen/FinBERT-FOMC
- **Paper:** https://doi.org/10.1145/3604237.3626843

---

#### FinBERT (ProsusAI) — Modelul de bază
**Punctul de pornire, nu soluția finală.**

- **Ce face:** BERT pre-antrenat pe corpus financiar mare (Reuters TRC2), fine-tunat pentru sentiment financiar (positive/negative/neutral)
- **Limitare pe text FOMC:** Nu înțelege contextul economic — "unemployment declined" = negativ în financePhrase Bank, dar pozitiv pentru Fed (piața muncii se îmbunătățește)
- **Utilitate:** Poți folosi ca baseline rapid sau layer suplimentar, nu ca model principal
- **GitHub:** https://github.com/ProsusAI/finBERT
- **HuggingFace:** https://huggingface.co/ProsusAI/finbert

---

#### Loughran-McDonald Financial Sentiment Dictionary
**Lexicon specializat pentru text financiar — util pentru validare și baseline.**

- **Ce face:** Mapează cuvinte la categorii de sentiment în contextul financiar, diferit de sentiment-ul din limbajul comun (ex: "liability" e negativ în finanțe, neutru în limbaj comun)
- **Acuratețe pe FOMC:** ~44% — utilizabil ca baseline sau validare, nu ca model principal
- **Utilizare în Python:** Disponibil ca CSV; parsezi manual sau folosești librăria `pyfinviz`
- **Sursă:** University of Notre Dame, Prof. Tim Loughran
- **Link:** https://sraf.nd.edu/textual-analysis/resources/

---

### 3.2 Date de Piață — Market Pricing

#### FRED API (Federal Reserve Economic Data)
**Baza de date macro publică cea mai completă, gratuită.**

- **Ce conține relevant:**
  - `DGS2` — US Treasury 2-Year Yield
  - `DGS10` — US Treasury 10-Year Yield
  - `T5YIE` — 5-Year Breakeven Inflation Rate
  - `T10YIE` — 10-Year Breakeven Inflation Rate
  - `FEDFUNDS` — Effective Federal Funds Rate
  - `CPIAUCSL` — CPI Urban Consumers
  - `CPILFESL` — Core CPI (ex food & energy)
  - `DPCERD3Q086SBEA` — PCE Price Index (target preferabil al Fed)
  - `UNRATE` — Unemployment Rate
  - `DTWEXBGS` — US Dollar Index (broad)
  - `DEXUSEU` — EUR/USD Exchange Rate (zilnic)

- **Instalare și utilizare Python:**

```python
pip install fredapi

from fredapi import Fred
fred = Fred(api_key='YOUR_API_KEY')  # gratis la https://fred.stlouisfed.org/docs/api/api_key.html

us_2y = fred.get_series('DGS2')
breakeven_5y = fred.get_series('T5YIE')
eurusd = fred.get_series('DEXUSEU')

# Calculul diferențialului de rate reale (US side)
us_real_rate = us_2y - breakeven_5y
```

- **API docs:** https://fred.stlouisfed.org/docs/api/fred/
- **Website:** https://fred.stlouisfed.org/
- **Tip:** Gratuit / Federal Reserve Bank of St. Louis

---

#### ECB Data Portal API
**Echivalentul FRED pentru zona euro — obligatoriu pentru EUR/USD.**

- **Ce conține relevant:**
  - Rata de referință BCE (Main Refinancing Operations Rate)
  - EURIBOR (3M, 6M, 12M)
  - Inflație HICP (Harmonised Index of Consumer Prices)
  - OIS rates europene
  - Date de credit zona euro

- **Utilizare (REST API fără autentificare):**

```python
import requests

# Exemplu: EURIBOR 3M
url = "https://data.ecb.europa.eu/api/data/FM/B.U2.EUR.RT0.BB.B23.3M.EURIBOR?format=csvdata"
response = requests.get(url)

# Sau prin librăria ecbdata (PyPI)
pip install ecbdata
from ecbdata import ecbdata
df = ecbdata.get_series('FM/B.U2.EUR.RT0.BB.B23.3M.EURIBOR')
```

- **API docs:** https://data.ecb.europa.eu/help/api/data
- **Portal:** https://data.ecb.europa.eu/
- **Tip:** Gratuit / Banca Centrală Europeană

---

#### CME FedWatch Tool
**Cel mai important instrument pentru Stratul 2 — market pricing al Fed.**

- **Ce face:** Calculează probabilitățile implicite de schimbare a Fed Funds Rate la fiecare meeting FOMC viitor, derivate din prețurile futures pe 30-Day Fed Funds
- **De ce e esențial:** Compari scorul tău NLP (ce spune Fed) cu FedWatch (ce anticipează piața) → obții surpriza → semnalul tău acționabil
- **Exemplu de utilizare:** Dacă FedWatch prețuiește 30% șanse hike și FOMC-RoBERTa dă scor hawkish de 0.75 → divergență mare → piața va fi surprinsă → USD upside
- **Link:** https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html
- **Tip:** Gratuit / CME Group

---

#### U.S. Monetary Policy Event-Study Database (USMPD) — San Francisco Fed
**Critică pentru backtesting — date intraday în jurul evenimentelor FOMC.**

- **Ce conține:**
  - Schimbări de prețuri pe ferestre de 30 minute în jurul fiecărui eveniment FOMC
  - Instrumente: futures SOFR, randamente Treasury 2Y/10Y, EUR/USD, JPY/USD, S&P500
  - Tipuri de evenimente: Statements (30min window), Press conferences (70min), Minutes (30min)
  - Actualizat 2025, acoperă din 2008

- **De ce e esențial pentru backtesting:** Îți permite să corelezi scorul tău NLP cu mișcările de piață măsurate precis în primele 30 minute post-publicare, nu pe date zilnice noisy
- **Link:** https://www.frbsf.org/research-and-insights/data-and-indicators/us-monetary-policy-event-study-database/
- **Tip:** Gratuit / Federal Reserve Bank of San Francisco

---

### 3.3 Date de Poziționare Instituțională

#### CFTC Commitment of Traders (COT) — Traders in Financial Futures
**Stratul 4 al sistemului — unde sunt poziționate instituțiile.**

- **Ce e:** Raport săptămânal al pozițiilor futures mari. Publicat vinerea pentru pozițiile din marțea precedentă (lag de 3 zile).
- **Categorii relevante pentru EUR/USD:**
  - **Leveraged Funds** (hedge funds, speculatori) — indicatorul principal de sentiment speculativ
  - **Asset Managers** (pensii, fonduri mutuale) — poziționare structurală, mai lentă
- **Cum interpretezi:**
  - Leveraged Funds > 80th percentile net long EUR → piață "aglomerată" → risc reversal
  - Leveraged Funds la extreme net short EUR → contrarianș: oportunitate long dacă fundamentale se îmbunătățesc
  - Schimbarea săptămânală a pozițiilor (nu nivelul absolut) e cel mai predictiv indicator

- **Surse de date:**
  - Sursa oficială: https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm
  - Vizualizare grafică: https://www.barchart.com/forex/commitment-of-traders
  - EUR-specific cu chart vs. EUR/USD: https://en.macromicro.me/charts/1206/eur-cot-eur
  - Myfxbook COT: https://www.myfxbook.com/commitments-of-traders/EUR
  - CME Group tool: https://www.cmegroup.com/tools-information/quikstrike/commitment-of-traders.html

- **Tip:** Gratuit / CFTC (Commodity Futures Trading Commission)
- **Limitare importantă:** Data vine cu 3 zile lag și e publicată săptămânal. Nu e un instrument de timing — e un instrument de confirmare structurală.

---

### 3.4 Surse de Date Complementare

#### MacroMicro
- **Ce e:** Platformă de vizualizare macro cu 10.000+ serii de date globale
- **Util pentru:** Dashboard vizual rapid — EUR COT Index vs EUR/USD, OIS rates, Fed pricing, comparații politici centrale
- **Link:** https://en.macromicro.me/
- **Tip:** Freemium (funcționalități de bază gratuite)

#### JP Morgan Macrosynergy Quantamental System (JPMaQS)
- **Ce e:** Date macro historice "point-in-time" pentru 40 de țări, fără look-ahead bias. Include: rate diferentiale reale, inflație relativă, creștere credit, sold extern
- **Util pentru:** Backtesting pe date istorice curate, fără biaș de revizuire a datelor
- **Acces research (gratuit cu lag):** https://macrosynergy.com/research/global-fx-management-a-systematic-macro-view/
- **Tip:** Freemium (gratuit pentru research, plătit pentru date live)

#### Sursa Date Beige Book
- **Toate edițiile Beige Book:** https://www.federalreserve.gov/monetarypolicy/publications/beige-book-default.htm
- **Arhivă Minneapolis Fed:** https://www.minneapolisfed.org/region-and-community/regional-economic-indicators/beige-book-archive
- **Publicat:** 8 ediții/an, miercurea, cu 2 săptămâni înainte de fiecare meeting FOMC
- **Important:** Procesează pe districte separat (New York, San Francisco sunt mai predictive pentru piețe financiare decât Kansas City sau Minneapolis) — confirmat de Boston Fed Research (2025)

---

## 4. Research Papers Relevante

### 4.1 NLP pe Comunicare FOMC

#### Shah, Paturi & Chava (2023) — "Trillion Dollar Words"
- **Publicat în:** Proceedings of ACL 2023 (Annual Meeting of the Association for Computational Linguistics) — peer-reviewed, Toronto, Canada
- **Ce aduce:**
  - Construiesc cel mai mare dataset adnotat manual de text FOMC: minute + speeches + press conferences
  - Definesc formal task-ul hawkish/dovish/neutral — distinct de sentiment financiar standard
  - RoBERTa-large ca model câștigător; scorul corelează cu CPI, PPI și randamente Treasury
  - Propun o strategie de tranzacționare pe QQQ care bate buy-and-hold pe ultimul deceniu
  - **Insight critic:** Cuvântul "increase" cu "employment" = dovish (bine pentru economie); "increase" cu "inflation" = hawkish (problemă). Un model generic de sentiment le tratează identic.
- **Limitări:** Dataset eșantionat (nu toate propozițiile); strategie testată pe QQQ (acțiuni), nu forex direct
- **DOI:** https://doi.org/10.18653/v1/2023.acl-long.368
- **ArXiv:** https://arxiv.org/abs/2305.07972

---

#### Kim, Spörer, Lee & Handschuh (2024) — "Is Small Really Beautiful for Central Bank Communication?"
- **Publicat în:** ACM ICAIF 2024 (5th ACM International Conference on AI in Finance) — peer-reviewed, Brooklyn, NY
- **Ce aduce:**
  - Benchmark direct: VADER 44.3% < FinBERT 59.7% < FinBERT-FOMC 63.8% < GPT-4 68.2% < Llama 3-70B 79.34%
  - Concluzie: Llama 3 e cel mai precis dar computațional cel mai scump. FinBERT-FOMC e optim cost/performanță.
  - **Performanța umană rămâne superioară tuturor modelelor** — important pentru calibrarea așteptărilor
  - AUC GPT-4 nu e superior FinBERT-FOMC, deși acuratețea brută e mai mare → modelele mici fine-tunate pot fi competitive cu LLM-urile mari
- **Limitări:** Testează acuratețea clasificării, nu impactul de piață
- **Link:** https://dl.acm.org/doi/fullHtml/10.1145/3677052.3698675

---

#### Aruoba & Drechsel (2024) — "Identifying Monetary Policy Shocks: A Natural Language Approach"
- **Publicat în:** UMD Working Paper + publicare academică (2024)
- **Ce aduce:**
  - Construiesc 296 indicatori de sentiment pe concepte economice specifice din documentele FOMC (inflație, creștere, ocupare — separate)
  - Demonstrează că **textul conține informație esențială dincolo de prognozele numerice** ale staff-ului Fed
  - Utilizează Beige Book explicit în analiză ca proxy pentru datele recente
  - Metoda: Loughran-McDonald augmentat cu dicționar custom Fed; ridge regression pentru agregare
- **Limitări:** Analiza e retrospectivă pe date cu lag de 5 ani (documentele interne Fed cu 5 ani întârziere); analiza directă a datelor live nu e posibilă cu această metodă
- **Link:** https://econweb.umd.edu/~drechsel/papers/Aruoba_Drechsel.pdf

---

#### Djourelova et al. (2025) — "Communicating Monetary Policy by Committee: Echoes That Move Markets"
- **Publicat în:** Chicago Fed Insights / Federal Reserve Working Paper (2025)
- **Ce aduce:**
  - Analizează 481 speeches FOMC timestampate cu mișcări intraday pe futures
  - **Descoperire cheie pentru trading:** Speeches **similare textual** cu press conference-ul precedent Powell **amplifică semnalul de piață**; speeches dissonante (Fed members care deviază de la mesajul Chair-ului) = **zgomot**, nu semnal
  - Implicație: Nu toate speeches Fed au aceeași greutate. Trebuie să calculezi similaritatea cosinus a speech-ului nou față de ultimul press conference Powell
  - Similaritate înaltă + semnal hawkish → efect puternic pe yield curve
  - Similaritate scăzută → ignoră semnalul
- **Limitări:** Efectul pe forex e mai mic decât pe yield curve; necesită calibrare separată pentru EUR/USD
- **Link:** https://www.chicagofed.org/publications/chicago-fed-insights/2025/communicating-monetary-policy-by-committee

---

#### Rosa (2013) — "The Financial Market Effect of FOMC Minutes"
- **Publicat în:** Federal Reserve Bank of New York Economic Policy Review (2013)
- **Ce aduce:**
  - Demonstrează că publicarea minutelor FOMC **triplează volatilitatea randamentelor Treasury pe 2Y** față de zilele control
  - Influențează semnificativ cursul EUR/USD, CHF/USD, JPY/USD în ferestre de **5 minute**
  - Confirmat statistic că există semnal acționabil în primele minute post-publicare
  - Analiza pe date intraday 2005–2011: înainte de era press conferences regulate
- **Limitări:** Perioada 2005–2011; dinamica s-a schimbat după introducerea press conferences regulate Powell
- **Link:** https://www.newyorkfed.org/research/epr/2013/0913rosa.pdf

---

#### CFA Institute (2023) — "Machine Learning and FOMC Statements: What's the Sentiment?"
- **Publicat în:** CFA Institute Enterprising Investor Blog (January 2023) — review, nu peer-reviewed
- **Ce aduce:**
  - Aplică Loughran-McDonald + BERT + XLNet pe statements FOMC
  - Scorurile detectează schimbările de regim hawkish/dovish cu o decalaj față de piață
  - **Concluzie practică:** Manual labeling > automatic labeling. Dacă adnotezi manual chiar 200–300 propoziții recente, obții un model superior
  - NASDAQ mai responsiv la scorul de sentiment FOMC decât S&P500
- **Limitări:** Loughran-McDonald evaluat doar la nivel de cuvânt (nu propoziție) → subevaluare sistematică a negațiilor
- **Link:** https://blogs.cfainstitute.org/investor/2023/01/18/machine-learning-and-fomc-statements-whats-the-sentiment/

---

#### Handlan (2022) — "Text Shocks and Monetary Surprises: Text Analysis of FOMC Statements"
- **Publicat în:** Working Paper, Amy Handlan (Brown University)
- **Ce aduce:**
  - Construiește "text shocks" ca componenta randamentelor bond intraday în jurul statements FOMC care e predictibilă din limbajul statement-ului
  - Metoda de izolare: separă efectul textului de efectul deciziei de rată în sine
  - Include liste complete ale tuturor celor 165 statements cu date și ore — util ca dataset de antrenament
- **Link:** https://handlanamy.github.io/MyFiles/Handlan_TextShocks_sub.pdf

---

### 4.2 Beige Book și Forecasting Economic

#### Boston Fed Research (2025) — "The Beige Book's Value for Forecasting Recessions"
- **Publicat în:** Federal Reserve Bank of Boston Current Policy Perspectives (November 2025)
- **Ce aduce:**
  - Demonstrează că **sentimentul la nivel de district** (nu cel național agregat) corelează semnificativ cu riscul de recesiune pe orizont de **3 luni**
  - Sentimentul district-level e mai predictiv decât cel national summary — confirmă că trebuie să procesezi Beige Book pe districte separate
  - Regresia de district sentiment rămâne semnificativă chiar după controlul pentru term spread și S&P 500
  - Acoperire: April 1970 – November 2024
- **Limitări:** Orizont de 3 luni → prea lent pentru tranzacționare tactică imediată; mai util pentru poziționare strategică swing trading
- **Link:** https://www.bostonfed.org/publications/current-policy-perspectives/2025/beige-book-for-forecasting-recessions.aspx

---

### 4.3 Mecanisme Macro EUR/USD și Divergență Fed-BCE

#### ECB Blog Staff (2025) — "What Happens When US and Euro Area Monetary Policy Decouple?"
- **Publicat în:** ECB Blog / ECB Research (February 2025)
- **Ce aduce:**
  - Documentează mecanismul exact de transmisie Fed → EUR/USD cu date istorice
  - **Efect imediat (zile–săptămâni):** Tightening surpriză Fed → EUR se slăbește → inflație europeană crește (importuri mai scumpe în USD)
  - **Efect mediu termen (luni):** Tightening Fed → încetinire economie SUA → cerere mai mică pentru exporturi europene → efect similar cu ECB tightening
  - **Implicație pentru trading:** Același eveniment Fed poate fi bullish USD pe 3 zile și irelevant pe 3 săptămâni. Orizontul temporal al tranzacției dictează cum interpretezi semnalul.
- **Link:** https://www.ecb.europa.eu/press/blog/date/2025/html/ecb.blog20250205~44578cf53f.en.html

---

#### BBVA Research (2025) — "Equilibrium of the EUR/USD Exchange Rate: A Long-Term Perspective"
- **Publicat în:** BBVA Research Working Paper (March 2025)
- **Ce aduce:**
  - Descompune forța USD în componente: Global Financial Conditions Index (GFCI) + politica monetară Fed
  - La final de 2024, politica monetară restrictivă a Fed explica **până la 13 puncte procentuale** din supraevaluarea dolarului față de echilibrul fundamental
  - Când Fed a semnalizat cuts, acești 13pp s-au comprimat → EUR/USD a crescut masiv — *exact* scenariul tău de la final de 2024
  - Rată de echilibru EUR/USD: ~1.20 pe baza diferențialelor de productivitate, dar piața a fost mult sub din cauza divergenței politicii monetare
- **Link:** https://www.bbvaresearch.com/wp-content/uploads/2025/03/Equilibrium-of-the-EUR-USD-exchange-rate-A-long-term-perspective.pdf

---

#### Djourelova et al. (2025) — CEPR Summary
- **Publicat în:** CEPR VoxEU Column (October 2025)
- **Link:** https://cepr.org/voxeu/columns/communicating-monetary-policy-committee-echoes-move-markets

---

#### Ismayilli (2025) — "Implications of Diverging Monetary Policies on Exchange Rates and Capital Flows"
- **Publicat în:** SSRN Working Paper (April 2025) — preprint, ne-peer-reviewed
- **Ce aduce:**
  - Confirmă că diferențialul de rate de dobândă e factorul dominant în alocarea capitalului
  - Riscul geopolitic și sentimentul investitorilor complică efectele divergenței Fed-BCE
  - **Implicație:** În perioade de stres geopolitic ridicat (escaladare militară, tarifare comerciale, crize bancare), semnalul tău macro pur bazat pe rate poate fi suprimat de risk-off generalizat care suprascrie fundamentalele
- **Link:** https://papers.ssrn.com/sol3/Delivery.cfm/5141086.pdf?abstractid=5141086&mirid=1

---

#### Mulliner, Harvey, Xia & Fang (2025) — "Regimes"
- **Publicat în:** Journal of Financial Economics (citat în Alpha Architect, March 2025) — peer-reviewed
- **Ce aduce:**
  - Metodă sistematică de identificare a regimului economic curent prin comparare cu *momente analogice din istorie*
  - Vector de indicatori macro (yield curve, inflație, spread credit, stock-bond correlation) → distanță Euclidiană față de perioade istorice
  - "Anti-regimuri" (perioade cele mai diferite de prezent) au și ele putere predictivă
  - Baza teoretică: dacă regimul de azi seamănă cu regimul X din 2008 sau 2015, dinamica activelor ar putea urma un pattern similar
- **Link:** https://alphaarchitect.com/regime-detection/

---

#### Macrosynergy Research (2024) — "Macro Information Changes as Systematic Fixed Income Signals"
- **Publicat în:** Macrosynergy Research (September 2024) — proprietar, nu peer-reviewed
- **Ce aduce:**
  - Demonstrează că *schimbările în starea informațională macro* (nu nivelurile absolute) sunt predictori mai puternici
  - Conceptul cheie: nu contează că inflația e 3% — contează că **a trecut de la "în scădere" la "în creștere"**
  - Principiu aplicabil direct: urmărești schimbările de direcție ale narativi ului din comunicare FOMC, nu nivelul absolut al scorului hawkish
- **Link:** https://macrosynergy.com/research/macro-information-changes/

---

## 5. Implementări și Tentative Anterioare

### Morgan Stanley — MNLPFEDS Sentiment Index (patentat 2022)

- **Ce au făcut:** Deep learning pe statements FOMC pentru un index de sentiment hawkish/dovish/neutral, patentat în 2022. Ken Zhang + Qingyi Huang (AlphaWise Quant Research).
- **Rezultate:** Model cu lead de ~1 an față de acțiunile de politică monetară; corelație cu forma curbei de randamente și direcția USD; folosit intern de Morgan Stanley
- **Ce nu au reușit:** Transformarea directă a semnalului într-o strategie de tranzacționare standalone — admis explicit că frecvența redusă a documentelor FOMC (8x/an) e o limitare pentru modelele data-hungry
- **Lecție:** Chiar cu resursele Morgan Stanley, edge-ul NLP pe FOMC nu e suficient singur. Se combină cu alte semnale.
- **Link:** https://www.morganstanley.com/articles/mnlpfeds-sentiment-index-federal-reserve

---

### Georgia Tech FinTech Lab — Trading Strategy pe QQQ (2023)

- **Ce au făcut:** Au construit scorul hawkish/dovish din FOMC-RoBERTa și au aplicat o strategie simplă: long QQQ când scorul e dovish, short când hawkish, la ziua publicării
- **Rezultate:** Strategie care bate buy-and-hold pe QQQ pe ultimul deceniu
- **Limitare critică:** Testată pe acțiuni (QQQ), nu forex. Impactul FOMC pe equity vs. forex are timing și magnitudine diferite.
- **Lecție:** Semnalul funcționează directional pe termen de zile–săptămâni. Pe forex trebuie combinat cu analiza poziționării pre-event.
- **GitHub:** https://github.com/gtfintechlab/fomc-hawkish-dovish
- **Paper:** https://aclanthology.org/2023.acl-long.368

---

### Capital Flows Research — Macro Regime Tracker (Substack, 2024–2025, activ)

- **Ce fac:** Dashboard narativ + sistematic care clasifică regimul macro curent (Goldilocks / Boom / Stagflation / Easing) pe baza creștere, inflație, lichiditate, positioning. Monitorizează Fed în timp real și generează bias de direcție pentru USD.
- **Structură:** Yield curve + credit spreads + positioning COT + narative Fed = scor de regim robust
- **Lecție importantă:** Un sistem funcțional NU are nevoie de NLP sofisticat ca fundament. Diferențialele de rate + COT + yield curve dau regimul. NLP e un layer adăugat, nu fundația.
- **Link:** https://www.capitalflowsresearch.com/p/macro-regime-tracker-market-cycles

---

### Macrosynergy / JPMaQS — FX Systematic Macro Scores (2023–2025)

- **Ce fac:** Sistem fully quantitative care construiește scoruri macro pentru 40 perechi valutare pe factori: inflație relativă, diferențial de rate reale, creștere credit, balanță externă
- **Rezultate:** Scorurile compozite au edge demonstrat pe FX pe orizonturi săptămânale-lunare
- **Lecție critică:** Diferențialul de rate **reale** (ajustat cu inflația) e mai predictiv decât diferențialul nominal. Mulți traderi urmăresc ratele nominale Fed vs. BCE — edgeul vine din rata reală.
- **Link:** https://macrosynergy.com/research/global-fx-management-a-systematic-macro-view/

---

### GitHub — FOMC NLP Sentiment Analysis (Greg Jason Roberts, open source)

- **Ce face:** Scraping a 200+ PDF-uri de minute FOMC (1980–2010), tokenizare cu spaCy/NLTK, sentiment mapping pe Loughran-McDonald. Pipeline funcțional demonstrat.
- **Utilitate:** Arhitectura de scraping PDF → tokenizare → sentiment e replicabilă ca punct de pornire
- **Limitare:** Model basic (bag of words), fără backtesting pe date de piață
- **GitHub:** https://github.com/gregjasonroberts/FOMC_NLP_Sentiment_Analysis

---

## 6. Cross-Pollination Findings

### 🔬 Meteorologie — Ensemble Forecasting: Probabilitate, Nu Predicție Punctuală

**Ce există:** Forecasting-ul meteorologic modern (ECMWF, NOAA) nu produce o singură prognoză — produce un *ansamblu* de 50–100 simulări paralele, fiecare cu mici variații ale condițiilor inițiale. Output-ul nu e "mâine va ploua" ci "probabilitate 73% de precipitații". Incertitudinea e cuantificată, nu ascunsă.

**De ce e relevant:** Sistemul tău de macro context ar trebui să funcționeze identic. Nu "USD bullish" ca output binar, ci "probabilitate 68% de regim USD bullish, bazată pe: Fed hawkish (+2), piața prețuiește dovish (-1), COT neutru (0), diferențial real rate pozitiv (+1)". Un scor cu incertitudine mare înseamnă nu intri în poziție sau reduci size-ul.

**Cum implementezi:** Calculezi scorul composite și deviația standard a scorurilor individuale ca măsură de incertitudine. Intri în poziție doar când incertitudinea (std) e scăzută relativ la scor (high signal-to-noise).

**Dificultate adaptare:** 🟢 Scăzută — nu necesită matematică specială

**Sursă:** Gneiting & Raftery (2005), "Weather Forecasting with Ensemble Methods", *Science* — https://doi.org/10.1126/science.1115255

---

### 🔬 Oceanografie — Curenți Termohalini: Trend de Adâncime vs. Valuri de Suprafață

**Ce există:** Oceanografia distinge explicit între *valurile de suprafață* (haotice, vizibile, termen scurt) și *circulația termohalină* (curenți de adâncime conduși de diferențele de temperatură și salinitate, care se mișcă lent dar determină clima pe decenii). Instrumentele de măsurare sunt diferite pentru fiecare layer.

**De ce e relevant:** EUR/USD are exact doi layere:
- **Suprafața** = volatilitate zilnică (știri, technicals, sentiment intraday)
- **Curentul de adâncime** = diferențialul de rate reale Fed-BCE + fluxuri de capital pe termen lung

Sistemul tău vizează curentul de adâncime. Dacă diferențialul real de rate Fed-BCE e consistent negativ (USD slab structural), trebuie să ignori spike-urile intraday de USD și să rămâi long EUR/USD. Curentul de adâncime te ține în trade.

**Implementare concretă:** Construiești un indicator "curent de adâncime" (diferențial real rate + trend COT pe 3 luni) separat de indicatorii "suprafață" (price action, VIX, technicals) și le folosești pe orizonturi temporale diferite.

**Dificultate adaptare:** 🟢 Scăzută

**Sursă:** Broecker (1991), "The Great Ocean Conveyor", *Oceanography* — https://doi.org/10.5670/oceanog.1991.07

---

### 🔬 Neuroștiință — Predictive Coding: Surpriza Ca Semnal

**Ce există:** Predictive Coding (Karl Friston, 2005) — framework neurologic care susține că creierul nu procesează stimuli brut, ci *eroarea de predicție* (diferența dintre ce aștepta și ce a primit). Neuronii transmit în sus ierarhia erorile de predicție, nu inputul brut. Confirmare = zgomot suprimat. Surpriză = semnal.

**De ce e relevant:** Nu scorul absolut hawkish/dovish contează, ci deviația față de ce preda piața. Dacă FedWatch prețuia 70% probabilitate no change și documentul NLP dă scor puternic hawkish → surpriza e mare → semnal puternic. Dacă FedWatch prețuia deja hawkish și NLP confirmă → surpriză zero → semnal slab, chiar dacă scorul absolut e mare.

**Formula:**
```
signal = NLP_hawkish_score − FedWatch_hawkish_probability
```

**Dificultate adaptare:** 🟢 Scăzută — CME FedWatch oferă probabilitățile în timp real; scorul de surpriză se calculează trivial

**Sursă:** Friston (2005), "A Theory of Cortical Responses", *Philosophical Transactions of the Royal Society B* — https://doi.org/10.1098/rstb.2005.1622

---

### 🔬 Fizică — Tranziții de Fază: Sisteme Stabile cu Rupturi Bruște

**Ce există:** Fizica materialelor studiază *tranzițiile de fază* — schimbări de stare (solid→lichid→gaz) care nu se petrec liniar, ci printr-o acumulare de tensiune sub pragul critic, urmată de schimbare bruscă. Aproape de punctul de tranziție, există semnale precursoare măsurabile: **creșterea varianței** și a **autocorrelației** seriei temporale.

**De ce e relevant:** EUR/USD și macro regimes au exact această dinamică — perioade lungi de consolidare urmate de mișcări bruște de 300–500+ pips. Exemplul tău de la final de 2024 *e* o tranziție de fază.

**Aplicație practică:** Înainte de o tranziție de regim macro, varianța și autocorrelația indicatorilor tăi cresc. Monitorizezi varianța rolling a scorului tău composite, nu doar direcția lui. **Varianță în creștere + scor stabil = acumulare de presiune → tranziție iminentă → reduci size-ul sau intri în opțiuni pe volatilitate.**

**Dificultate adaptare:** 🟡 Medie — calculul varianței rolling e trivial; calibrarea pragului necesită backtesting

**Sursă:** Scheffer et al. (2009), "Early-Warning Signals for Critical Transitions", *Nature* — https://doi.org/10.1038/nature08227

---

### 🔬 Epidemiologie — Sisteme de Early Warning din Text Calitativ

**Ce există:** Sisteme de biosurveillance (HealthMap Harvard, ProMED, GPHIN) scanează în timp real rapoarte calitative pentru a detecta *semnale slabe* ale izbucnirii bolilor cu săptămâni înainte ca datele formale să confirme. Tehnica centrală: **Named Entity Recognition (NER)** — extrage entități specifice (locații, simptome, agenți patogeni) și le urmărește ca serii temporale.

**De ce e relevant:** Beige Book e structural analog cu rapoartele de biosurveillance — document de teren, calitativ, anecdotic, cu surse distribuite geografic (12 districte = 12 senzori). NER aplicat la Beige Book ar permite extragerea de entități economice specifice (*"tariffs", "hiring freeze", "supply constraints", "wage pressures"*) și urmărirea lor ca serii temporale separate pe districte.

**Implementare:** spaCy are NER out-of-the-box. Definești o listă de entități economice relevante (termen economic + context) și construiești serii temporale ale frecvenței lor pe districte Beige Book.

**Dificultate adaptare:** 🟢 Scăzută

**Sursă:** Brownstein et al. (2008), *PLOS Medicine* — https://doi.org/10.1371/journal.pmed.0050151

---

### 🔬 Sonar / Procesare Semnal — Matched Filter: Amplificarea Semnalului Cunoscut

**Ce există:** În sonar pasiv și activ, tehnica *matched filter* (filtru adaptat) maximizează detectarea unui semnal cunoscut în prezența zgomotului, prin corelarea semnalului primit cu un *template* al semnalului așteptat.

**De ce e relevant:** Djourelova et al. (2025) descoperă empiric un principiu structural identic: speeches Fed care sunt **textual similare** cu precedentul press conference Powell **amplifică semnalul**; cele dissonante = zgomot.

**Implementare concretă:**
1. Extragi embedding-ul press conference-ului precedent Powell (Sentence-BERT / text-embedding-3-small)
2. Calculezi similaritatea cosinus a fiecărui speech nou față de el
3. Ponderebi scorul NLP al speech-ului cu similaritatea: `weighted_signal = NLP_score × cosine_similarity`

**Dificultate adaptare:** 🟢 Scăzută — Sentence Transformers disponibil pe HuggingFace

**Sursă:** Turin (1960), "An Introduction to Matched Filters", *IRE Transactions on Information Theory* — https://doi.org/10.1109/TIT.1960.1057571

---

### 🔬 Intelligence Militar — Doctrine de Fuziune Multi-Sursă

**Ce există:** Doctrina NATO de intelligence multi-sursă (MULTI-INT) clasifică sursele de informații pe o ierarhie de credibilitate și relevanță temporală. Fiecare categorie are orizont temporal și acuratețe diferite. Decizia finală combină toate straturile ierarhizat.

**De ce e relevant:** Sistemul tău are exact această structură multi-sursă. Ierarhia explicită:

| Stratul tău | Echivalent intel | Frecvență | Orizont |
|---|---|---|---|
| NLP speech Fed | SIGINT real-time | Per eveniment | Ore–zile |
| CME FedWatch | SIGINT market | Zilnic | Zile |
| FRED rate differential | HUMINT fundamentals | Săptămânal | Săptămâni |
| COT positioning | IMINT structural | Săptămânal | Săptămâni–luni |
| Beige Book district | HUMINT teren | 8x/an | Luni |

**Regula:** Semnalele cu frecvență înaltă dau timing-ul; cele cu frecvență joasă dau direcția. Nu intra în contra-trend față de semnalele structurale bazat pe un singur speech de frecvență înaltă.

**Dificultate adaptare:** 🟢 Scăzută — e o regulă de decizie conceptuală, nu tehnică

**Sursă:** Clark (2013), *Intelligence Analysis: A Target-Centric Approach*, CQ Press — metodologie documentată

---

### 🔔 Convergență Identificată

Trei domenii diferite (**meteorologie ensemble**, **fizică tranziții de fază**, **neuroștiință predictive coding**) converg spre aceeași concluzie pentru arhitectura sistemului tău:

> **Output-ul sistemului nu ar trebui să fie un label binar ("USD bullish"), ci un scor cu interval de confidență. Varianța semnalului e la fel de importantă ca direcția lui. Surpriza relativă față de așteptări e mai informativă decât scorul absolut.**

---

## 7. Zone Nevăzute și Riscuri

### Riscul Geopolitic Suprascrie Fundamentalele

În episoade de stres geopolitic ridicat (tarifare comerciale, conflicte, crize bancare), corelațiile tradiționale USD-rate se rup temporar. Sistemul va genera semnale false în aceste perioade. Necesari un filtru explicit:

```python
if VIX > 30 or HY_credit_spread > threshold:
    signal_output = "QUIET MODE — no signal"
```

Referință: Ismayilli (2025) — https://papers.ssrn.com/sol3/Delivery.cfm/5141086.pdf?abstractid=5141086&mirid=1

---

### ECB-Side E Mai Greu de Automatizat

Există mult mai puțin research NLP pe comunicarea BCE față de Fed. FOMC-RoBERTa e antrenat exclusiv pe text Fed. Opțiuni pentru stratul BCE:
- **Proxy cantitativ:** OIS forward eurozone (extrase din ECB Data Portal) — un proxy bun al așteptărilor de politică BCE
- **Construiești manual:** Fine-tunezi FOMC-RoBERTa pe speeches Lagarde (mai puțin text, mai puțin stabil)
- **LLM cu prompt:** GPT-4 sau Claude cu prompt specific pe speeches ECB

---

### COT Data Vine cu 3 Zile Lag

Pozițiile reflectă marțea, sunt publicate vinerea. Dacă o mișcare mare s-a produs joi-vineri, ești deja târziu. Folosește COT **pentru confirmare structurală**, nu pentru timing de intrare.

---

### "Priced In" E Un Concept Fluid

Nu există o măsurătoare perfectă a ce e deja prețuit de piață. CME FedWatch e cel mai bun proxy disponibil, dar prețuiește cu precizie doar meeting-ul următor — anticiparea pe 12 luni e mult mai noisy. Nu trata FedWatch ca pe o certitudine.

---

### Modele Antrenate în Regim de Hiking — Overfitting

Marea majoritate a paperelor (2021–2023) sunt antrenate/testate în cicluri de tightening excepționale. Performanța modelelor în regimuri de rate stabile sau cutting poate fi semnificativ mai slabă. Validează pe date din 2015–2019 (perioadă relativ neutră).

---

### Limbajul Fed Se Schimbă Cu Chair-ul

Modele antrenate pe documente din era Yellen sau Bernanke pot fi descalibrate pe limbajul Powell sau al succesorilor. Necesită reantrenare/fine-tuning periodic.

---

### Domeniu în Mișcare Rapidă

LLM-urile și modelele NLP evoluează rapid. Llama 3-70B (79.34% acuratețe în 2024) va fi depășit de modele mai noi în 12–18 luni. Verifică benchmarks-urile periodic.

---

## 8. Glosar Tehnic

| Termen | Definiție |
|---|---|
| **Hawkish** | Stance de politică monetară care favorizează dobânzi mai mari pentru a controla inflația. Termen din engleză (șoim = agresiv față de inflație). |
| **Dovish** | Stance de politică monetară care favorizează dobânzi mai mici pentru a stimula creșterea/ocuparea. (porumbel = blând față de inflație). |
| **Fed Funds Rate** | Rata de dobândă overnight la care băncile se împrumută reciproc la Fed. Instrument principal de politică monetară al Fed. |
| **OIS (Overnight Index Swap)** | Swap de dobândă bazat pe rata overnight. OIS rates reflectă așteptările de politică monetară fără premium de credit — cel mai curat indicator al așteptărilor de rată. |
| **SOFR (Secured Overnight Financing Rate)** | Rata overnight bazată pe tranzacțiile repo colateralizate cu trezorerie US. Înlocuiește LIBOR în SUA din 2023. |
| **Peer-review** | Procesul prin care un articol științific e evaluat critic de alți experți din domeniu înainte de publicare. Garanția minimă de calitate academică. |
| **BERT / RoBERTa** | Modele de limbaj (neural networks) pre-antrenate pe cantități masive de text. BERT (Google, 2018), RoBERTa (Meta, 2019). Stau la baza majorității modelelor NLP moderne. |
| **Fine-tuning** | Procesul de continuare a antrenării unui model pre-antrenat pe un dataset specific (ex: text FOMC), pentru a-l specializa pe task-ul dorit. |
| **Embedding / Vector** | Reprezentarea matematică a unui text ca un vector numeric de dimensiune înaltă (ex: 768 dimensiuni). Texte similare semantic au vectori apropiați în spațiu. |
| **Cosine Similarity** | Măsura de similaritate între doi vectori, calculată ca cosinusul unghiului dintre ei. 1 = identici; 0 = fără legătură; -1 = opuși. |
| **COT (Commitment of Traders)** | Raport săptămânal CFTC cu pozițiile futures ale participanților mari de piață. |
| **Leveraged Funds** | Categoria din raportul COT care include hedge funds și traderi speculativi. Cel mai relevant indicator de sentiment speculativ. |
| **Rate Diferențial Real** | Diferența dintre ratele de dobândă reale (ajustate cu inflația așteptată) ale două economii. Cel mai puternic driver documentat al cursurilor valutare pe termen mediu. |
| **Term Premium** | Componenta randamentului unei obligațiuni pe termen lung care depășește așteptările de rate scurte — compensație pentru risc de durată. |
| **Breakeven Inflation** | Diferența dintre randamentul unui bond nominal și al unui bond indexat la inflație (TIPS) de același maturitate. Reprezintă inflația anticipată de piață. |
| **HMM (Hidden Markov Model)** | Model probabilistic care presupune că piața se află într-unul din mai multe "state" latente (regimuri), fiecare cu distribuție proprie de randamente. |
| **Look-ahead Bias** | Eroarea de a folosi în backtesting date care nu erau disponibile la momentul deciziei simulate. Produce rezultate artificail de bune. |
| **Named Entity Recognition (NER)** | Subdomeniu NLP care identifică și clasifică entități din text: persoane, organizații, locații, concepte economice. |
| **Predictive Coding** | Framework neuroștiințific care susține că creierul procesează erori de predicție, nu inputul senzorial brut. |
| **Matched Filter** | Tehnică de procesare de semnal care maximizează detectarea unui semnal cunoscut în zgomot, prin corelare cu un template al semnalului așteptat. |
| **Ensemble Forecast** | Prognoză bazată pe multiple simulări paralele cu variații mici ale condițiilor inițiale, care produce o distribuție de probabilitate, nu o valoare punctuală. |

---

## 9. Pasul Următor Recomandat

### Ordinea Corectă de Construcție

**Nu** începi cu NLP. Începi cu diferențialul de rate reale — cel mai documentat driver al EUR/USD.

#### Faza 1: Ancora Fundamentală (Ziua 1–3)

Deschide FRED și ECB Data Portal și construiește această serie temporală:

```python
from fredapi import Fred

fred = Fred(api_key='YOUR_KEY')

us_2y = fred.get_series('DGS2')          # US Treasury 2Y nominal
us_breakeven = fred.get_series('T5YIE')  # 5Y breakeven inflation (proxy)
eurusd = fred.get_series('DEXUSEU')      # EUR/USD daily

# Rata reală US
us_real_rate = us_2y - us_breakeven

# Pentru EUR: extrage 2Y OIS din ECB Data Portal
# și inflația așteptată europeană
# Diferențialul: us_real_rate - eur_real_rate
```

Plotează `real_rate_differential` împreună cu `EUR/USD` pe ultimii 5 ani. Vei vedea corelația structurală cu ochii liberi. Acesta e "curentul de adâncime" — ancora fundamentală.

#### Faza 2: Layer-ul de Surpriză (Săptămâna 1–2)

Descarcă dataset-ul `gtfintechlab/fomc_communication` de pe HuggingFace. Rulează FOMC-RoBERTa pe toate documentele → generezi scorul hawkish/dovish per eveniment. Compară cu FedWatch la momentul T-1h față de publicare. Calculează surpriza.

#### Faza 3: Backtesting Integrat (Săptămâna 2–4)

Descarcă USMPD de la San Francisco Fed (mișcări EUR/USD intraday pe ferestre 30-min în jurul fiecărui eveniment FOMC). Calculează:
```
signal = surprise_score × cosine_similarity_with_chair_press_conference
```
Verifică: semnalul predict mișcarea EUR/USD în primele 30-minute? Calculează Sharpe ratio pe această strategie simplă.

**Motivul acestei ordini:** Dacă backtestul pe date istorice nu arată edge după costuri, nu ai motiv să construiești sistemul live. Dacă arată edge, știi exact ce model și ce fereastră temporală să optimizezi.

---

## Surse Oficiale Principale (Quick Reference)

| Sursă | URL | Ce oferă |
|---|---|---|
| Fed — Beige Book | https://www.federalreserve.gov/monetarypolicy/publications/beige-book-default.htm | Toate edițiile Beige Book |
| Fed — Speeches | https://www.federalreserve.gov/newsevents/speeches.htm | Toate speeches Fed Governors |
| Fed — FOMC Minutes | https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm | Calendar FOMC + toate documentele |
| FRED API | https://fred.stlouisfed.org/docs/api/fred/ | Date macro SUA |
| ECB Data Portal API | https://data.ecb.europa.eu/help/api/data | Date macro Eurozone |
| CME FedWatch | https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html | Prețuri implicite Fed |
| SF Fed USMPD | https://www.frbsf.org/research-and-insights/data-and-indicators/us-monetary-policy-event-study-database/ | Date intraday FOMC events |
| CFTC COT | https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm | Positioning futures |
| FOMC-RoBERTa | https://github.com/gtfintechlab/fomc-hawkish-dovish | Modelul NLP principal |
| FinBERT-FOMC | https://huggingface.co/ZiweiChen/FinBERT-FOMC | Model alternativ NLP |
| Loughran-McDonald | https://sraf.nd.edu/textual-analysis/resources/ | Dicționar financiar |
| MacroMicro | https://en.macromicro.me/ | Dashboard vizual macro |

---

*Document generat în Aprilie 2026 pe baza research-ului din sesiunea de chat. Verificați linkurile periodic — paperele și tool-urile evoluează rapid în acest domeniu.*
