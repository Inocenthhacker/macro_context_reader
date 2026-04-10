"""
Regime Monitor — PRD-051 (Status: Draft)
Modul standalone de vizualizare a regimului macro curent.

Pornire: streamlit run src/macro_context_reader/monitoring/regime_monitor.py

COUPLING:
  Mod COUPLED:    consumă get_current_regime() din PRD-050 dacă e disponibil
  Mod STANDALONE: calculează direct din FRED via _standalone_calc.py

Auto-detectează modul la pornire — zero configurare manuală necesară.

DO NOT implement until PRD-051 is Approved.
"""
