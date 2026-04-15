# Onboarding pentru noi colaboratori

> Scopul: în 30 de minute să poți rula testele și să înțelegi unde să cauți când vrei să adaugi cod.

## 1. Setup mediu (5 min)

```bash
git clone <repo-url>
cd macro_context_reader
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env
# Editează .env: adaugă FRED_API_KEY (gratuit de la https://fred.stlouisfed.org/docs/api/api_key.html)
```

Verifică:
```bash
pytest -m "not integration" --tb=no -q
# Expected: ~150+ tests pass
```

Dacă eșuează: vezi [ARCHITECTURE.md#troubleshooting](ARCHITECTURE.md#troubleshooting).

## 2. Citire obligatorie înainte de prima linie de cod (10 min)

În ordinea asta:
1. **README.md** — ai citit deja
2. **docs/ARCHITECTURE.md** — cele 4 straturi
3. **ROADMAP.md** secțiunea 3 (PRD Registry) — ce e Done vs În progres
4. **docs/WORKFLOW.md** — cum se contribuie

## 3. Tour ghidat al codului (10 min)

Structura `src/macro_context_reader/`:

| Folder | Ce face | MAP.md |
|---|---|---|
| `market_pricing/` | Stratul 2 — rate, FedWatch, real_rate_diff | [MAP](../src/macro_context_reader/market_pricing/MAP.md) |
| `market_pricing/fedwatch/` | Sub-modul FedWatch CSV + surprise | [MAP](../src/macro_context_reader/market_pricing/fedwatch/MAP.md) |
| `rhetoric/` | Stratul 1 — NLP Fed | [MAP](../src/macro_context_reader/rhetoric/MAP.md) |
| `positioning/` | Stratul 4 — COT, OI, options | [MAP](../src/macro_context_reader/positioning/MAP.md) |
| `divergence/` | Stratul 3 — surprise signal, decomposition | [MAP](../src/macro_context_reader/divergence/MAP.md) |
| `regime/` | Macro regime classifier (HMM + analog) | [MAP](../src/macro_context_reader/regime/MAP.md) |
| `monitoring/` | Streamlit dashboard | [MAP](../src/macro_context_reader/monitoring/MAP.md) |
| `output/` | DST evidence fusion | [MAP](../src/macro_context_reader/output/MAP.md) |
| `economic_sentiment/` | Cleveland Fed Beige Book loader | [MAP](../src/macro_context_reader/economic_sentiment/MAP.md) |

Pentru orice modul: deschide **MAP.md primul**, codul după.

## 4. Primul task (5 min)

Sugestie: rulează notebook-ul `notebooks/02_layer2_market_pricing.ipynb` end-to-end. Verifică că plotează `real_rate_differential` vs EUR/USD pe ultimii 5 ani.

Dacă merge → setup-ul tău e OK. Dacă nu → vezi [ARCHITECTURE.md](ARCHITECTURE.md) secțiunea troubleshooting.

## 5. Înainte de primul commit

- Citește [WORKFLOW.md](WORKFLOW.md) — workflow PRD → prompt → commit
- Verifică în [ROADMAP.md](../ROADMAP.md) că nu lucrezi în paralel cu altcineva pe același PRD
- Toate prompturile pentru Claude Code trec prin Chat A (vezi [CLAUDE.md](../CLAUDE.md))

## Întrebări frecvente

**Q: De ce 4 straturi separate, nu un model end-to-end?**
A: Decoupling. Fiecare strat poate fi recalibrat independent. Vezi [ARCHITECTURE.md](ARCHITECTURE.md) secțiunea "Design rationale".

**Q: De ce manual download pentru CME FedWatch / Cleveland Fed?**
A: API-uri publice nu există sau sunt fragile. Vezi [DATA_REFRESH.md](DATA_REFRESH.md).

**Q: Ce fac când Claude Code raportează BLOCKER?**
A: Stop. Verifică starea repo-ului manual. Workflow-ul presupune precondiții — dacă starea diferă, fix-ul nu se aplică safe.

**Q: Pot folosi alt LLM în loc de FOMC-RoBERTa?**
A: Da, dar la backtesting trebuie să compari empiric. Vezi DEC entries în ROADMAP secțiunea 8.
