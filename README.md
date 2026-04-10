# Macro Context Reader — EUR/USD Regime Detector

Macro regime detection system for EUR/USD based on Fed/ECB rhetoric, market pricing, rate differentials, and institutional positioning.

## Architecture

| Layer | Description |
|-------|-------------|
| **Rhetoric** | NLP scoring of Fed/ECB communications (hawkish/dovish/neutral) |
| **Market Pricing** | Implied rate expectations from CME FedWatch and eurozone OIS forwards |
| **Divergence** | Surprise scores and real rate differentials — the actionable signal |
| **Positioning** | CFTC COT institutional positioning on EUR futures |

## Setup

```bash
git clone <repo-url> && cd Trading_copilot
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

## Project Status

In development.
