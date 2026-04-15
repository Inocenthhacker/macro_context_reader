# rhetoric / MAP.md

## La ce folosește (în 1 propoziție)
Stratul 1 — extrage și scorează propozițiile din comunicatele Fed (statements, minutes, press conferences, speeches) ca hawkish/dovish/neutral prin ensemble FOMC-RoBERTa + Llama DeepInfra, ponderat prin matched-filter cu ultimul Powell presser.

## Decizii critice documentate
- **D2** — FOMC-RoBERTa ca model principal NLP (state-of-art pe text FOMC, open source).
- **Djourelova et al. 2025 (Chicago Fed)** — matched-filter: speeches similare cu Powell presser amplifică semnalul.
- FinBERT-FOMC deprecated 2026-04-12 (20% accuracy); păstrat ca backup.

## Componente

### scraper.py — "Culegătorul de texte Fed"
Funcții publice: `fetch_fomc_statements(start_year)`, `fetch_fomc_minutes(start_year)`, `fetch_press_conferences(start_year)`, `fetch_speeches(...)`. Scraping federalreserve.gov cu retry + exponential backoff, cache local în `data/rhetoric/raw/`, extragere text din HTML prin BeautifulSoup. Returnează `list[FOMCDocument]`.
**SE STRICĂ DACĂ:** federalreserve.gov schimbă structura paginii; rate-limited (429); cache corupt pe disc; `FOMCDocument` schema change.

### preprocessor.py — "Tăietorul de propoziții"
`preprocess_document(raw_text, min_words=5) -> list[str]` — normalize whitespace, dehyphenate, spaCy sentence segmentation, filtrare propoziții < `min_words`. `_get_nlp()` lazy-loads `en_core_web_sm`.
**SE STRICĂ DACĂ:** `en_core_web_sm` lipsește (`python -m spacy download en_core_web_sm`); text cu encoding aberant (non-UTF8); propoziții foarte lungi cu punctuație greșită.

### scorers/ — "Cei 3 scorere interschimbabili"
- `base.py` — `Protocol SentenceScorer` (interfață)
- `fomc_roberta.py` — `FOMCRobertaScorer` (gtfintechlab/FOMC-RoBERTa)
- `llama_deepinfra.py` — `LlamaDeepInfraScorer` + `BudgetTracker` + `BudgetExceededError` (API DeepInfra, cost-capped)
- `finbert_fomc.py` — `FinBERTFOMCScorer` (deprecated, backup)

**SE STRICĂ DACĂ:** `HF_TOKEN` lipsește pentru modele gated (RoBERTa); `DEEPINFRA_API_KEY` lipsește sau budget epuizat; VRAM insuficient pentru RoBERTa (~1.4GB); protocol schimbat fără update la scorere.

### ensemble.py — "Arbitrul NLP"
`compute_ensemble_score(sentences, scorers)` → agregare scoruri multi-model cu `_compute_agreement_rate` + `_agreement_confidence_2model`. Returnează `EnsembleScore` cu `document_score` + `confidence` based on agreement.
**SE STRICĂ DACĂ:** scorerele returnează format inconsistent; doar un scorer e disponibil (confidence = agreement nu are sens).

### matched_filter.py — "Amplificatorul cosine"
`compute_embedding(text)` (all-MiniLM-L6-v2), `compute_similarity(a, b)`, `get_last_powell_presser(before_date)`, `compute_matched_filter_weight(text, ...)`. Cosine similarity speech ↔ ultimul Powell presser → weight în [0, 1].
**SE STRICĂ DACĂ:** `sentence-transformers` nu poate descărca modelul (no internet on Colab free); nu există Powell presser înainte de data target.

### pipeline.py — "Orchestratorul end-to-end"
`run_full_pipeline(doc_type, start_year, scorer_names=None)` — scraper → preprocessor → ensemble → matched_filter → scor final per document. `_load_scorers(...)` încarcă lazy.
**SE STRICĂ DACĂ:** orice component upstream eșuează; scorer name invalid.

### schemas.py — "Dicționarul"
Pydantic: `FOMCDocument`, `SentenceScore`, `DocumentScore`, `EnsembleScore`.

### concept_framework/ — "Submodul experimental (PRD-102 pivot)"
Originally Aruoba-Drechsel concept indicator framework. După DEC-D20 pivot la Cleveland Fed ICPSR — majoritatea codului e placeholder/skeleton. Conține: `aggregator.py`, `decomposer.py`, `extractor.py`, `dictionary/{registry,validator}.py`, `discovery/{corpus,lda,expansion}.py`, `sources/{beige_book,fomc_docs}.py`. Folosit minimal.
**SE STRICĂ DACĂ:** ignorat — nu e în producție (folosește `economic_sentiment/` pentru Beige Book).

### `__init__.py` — Surface API
`clear_cache(doc_type=None)` pentru invalidare cache scraping.

## Lanțul de dependențe

```
federalreserve.gov
        │
        ▼
   scraper.py ──→ data/rhetoric/raw/ (cache)
        │
        ▼ list[FOMCDocument]
  preprocessor.py (spaCy)
        │
        ▼ list[str] sentences
  ┌─────┴──────────┐
  ▼                ▼
scorers/*    matched_filter.py
(RoBERTa,     (sentence-transformers
Llama,         vs last Powell presser)
FinBERT)
  │                │
  ▼                │
ensemble.py ←──────┘
        │
        ▼
  pipeline.py (orchestrator)
        │
        ▼
   EnsembleScore ──→ Stratul 3 (divergence)
```

## Când ceva nu merge — întrebări de diagnostic

1. **401 Unauthorized pe HuggingFace** → `HF_TOKEN` lipsește/expirat; RoBERTa e gated. Vezi TD-2 (skip-guard pe integration tests).
2. **Empty sentence list după preprocessor** → `min_words` prea mare sau text corupt.
3. **Ensemble confidence permanent LOW** → scorerele disagree sistematic; verifică că toți scorere folosesc aceeași schema de labeluri (hawkish/dovish/neutral).
4. **DeepInfra BudgetExceededError** → budget cap atins; ajustează `BudgetTracker` sau folosește doar RoBERTa.
5. **Scraper returnează lista goală** → federalreserve.gov a schimbat URL/HTML; testează manual URL-ul.

## Legătura cu restul proiectului
- **Consumer:** `divergence/` (surprise signal), `output/bba_mappers/layer1_rhetoric.py` (DST mapping).
- **Depends on:** `transformers`, `torch`, `sentence-transformers`, `spacy`, `openai` (DeepInfra client), `requests`, `beautifulsoup4`.
- **PRD:** PRD-101 (~85% Done, 47 unit + 4 integration tests).

## Limitări cunoscute
- Modele NLP antrenate 2021-2023 → over-fit pe ciclu de hiking (risc menționat în CLAUDE.md).
- Limbajul Fed se schimbă cu Chair-ul → fine-tuning periodic necesar.
- FinBERT-FOMC deprecated (20% accuracy).
- 4 integration tests din `tests/rhetoric/test_scorers.py` necesită skip-guard pe missing `HF_TOKEN` (TD-2).
- `concept_framework/` e ~80% skeleton după pivot PRD-102.
