# Macro Context Reader — EUR/USD Regime Detector

> Sistem de detecție a regimului macro pentru perechea EUR/USD. **Nu prezice preț — detectează regim.**

## Ce face

Răspunde la întrebarea: *"Fed-ul e hawkish sau dovish față de ce prețuiește piața? Care e direcția structurală a USD?"*

Output: scor de regim cu interval de confidență (ex: `USD bearish (67% confidence)`), nu predicție punctuală.

## Arhitectura — 4 straturi

| Layer | Description |
|-------|-------------|
| **Rhetoric** | NLP scoring of Fed/ECB communications (hawkish/dovish/neutral) |
| **Market Pricing** | Implied rate expectations from CME FedWatch and eurozone OIS forwards |
| **Divergence** | Surprise scores and real rate differentials — the actionable signal |
| **Positioning** | CFTC COT institutional positioning on EUR futures |

Vezi [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) pentru detalii.

## Quick start

### Cerințe
- Python 3.11+
- API keys: `FRED_API_KEY` (gratuit), opțional `HF_TOKEN`, `DEEPINFRA_API_KEY`

### Instalare

```bash
git clone <repo-url>
cd macro_context_reader
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env
# Editează .env și adaugă FRED_API_KEY
```

### Verificare instalare

```bash
pytest -m "not integration" --tb=no -q
# Expected: ~150+ tests pass
```

## Documentație

Pentru un developer nou:
1. **[docs/ONBOARDING.md](docs/ONBOARDING.md)** — start aici, ghid pas-cu-pas
2. **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — cum funcționează cele 4 straturi
3. **[docs/WORKFLOW.md](docs/WORKFLOW.md)** — workflow-ul PRD → Claude Code → commit
4. **[docs/DATA_REFRESH.md](docs/DATA_REFRESH.md)** — refresh manual al dataset-urilor

Pentru orientare în cod:
- **[ROADMAP.md](ROADMAP.md)** — starea canonică a proiectului, statusuri PRD
- **[CLAUDE.md](CLAUDE.md)** — system prompt pentru Chat A architect role
- **[fomc_macro_research.md](fomc_macro_research.md)** — research consolidat (papers, datasets, surse)
- **[prds/](prds/)** — Product Requirements Documents per feature
- **`MAP.md`** în fiecare modul — descriere componente în metafora "piese de mașină"

## Status proiect

În dezvoltare activă. Status detaliat în [ROADMAP.md](ROADMAP.md).

**Faze:**
- ✅ Faza 0 — Infrastructure
- ✅ Faza 1 — Ancora Fundamentală (real_rate_differential + COT + regime)
- 🟢 Faza 2 — NLP Layer (~85%)
- ✅ Faza 3 — Positioning Layer
- 🔵 Faza 4 — Divergence Signal Integration (curentă)
- ✅ Faza 5 — Economic Sentiment (Cleveland Fed loader)
- 🔵 Faza 6 — Output Aggregation (DST)
- 🔵 Faza 7 — Live Pipeline

## Licență

Personal use only. Modelele NLP folosite (FOMC-RoBERTa, Cleveland Fed indices) sunt CC BY-NC 4.0.

## Contact

Owner: Hrimiuc
