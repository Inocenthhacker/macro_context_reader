"""Inflation Expectations — Pluggable methods framework.

Toate metodele de inflation expectations (SPF, OATei, Bundesbank, HICP, etc.)
implementează Protocol-ul InflationExpectationsMethod definit în base.py.

Acest design permite schimbarea metodei în real_rate_diff prin dependency
injection, fără modificări în calling code.

Metode implementate:
- ecb_spf.py — ECB Survey of Professional Forecasters (PRD-200)
- oatei.py — OATei Breakeven (PRD-203, pending)
- dns_composite.py — SPF + OATei DNS combination (PRD-204, pending)
- bundesbank_ilb.py — Bundesbank inflation-linked Bunds (PRD-205, pending)
- hicp_yoy.py — HICP YoY baseline (PRD-206, pending)

Refs: PRD-200, research/INFLATION_EXPECTATIONS_METHODS.md
"""

from macro_context_reader.market_pricing.inflation_expectations.base import (
    InflationExpectationsMethod,
)

__all__ = ["InflationExpectationsMethod"]
