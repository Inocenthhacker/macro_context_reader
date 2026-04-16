# Divergence Module — Legacy Files Audit

Generated: 2026-04-15

## Summary

| File | Lines | Stubs | References (code) | In PRD-300 v2? | Last touched | Recommendation |
|------|-------|-------|-------------------|----------------|--------------|----------------|
| `equilibrium.py` | 246 | 6 / 6 functions | 0 imports (orphan) | Not in architecture tree; only cited as methodology source; consumer exists in PRD-500 | `1397e3f` 2026-04-10 (5d ago, never modified since initial snapshot) | **KEEP (deferred rewrite)** |
| `regime_conditional.py` | 315 | 0 (fully IMPLEMENTED) | 12 tests + 1 notebook + `__init__.py` re-export | YES — PRD-300 line 94 shows `regime_conditional/` as directory (not single file) | `c3fb8da` 2026-04-12 (3d ago, actively maintained) | **REWRITE → move into subdirectory** |

---

## File 1: `equilibrium.py`

### Purpose
Module docstring declares: *"EUR/USD Equilibrium & Misalignment Layer — PRD-300 / REQ-9, REQ-10, REQ-11"*. Based on BBVA Research (Martínez, Neut, Ramírez 2025). Four conceptual deliverables:
1. **Descompunere EUR/USD** — separate `usd_strength_component` from `eur_weakness_component` via DXY + EUR basket series
2. **Three equilibrium scenarios** — central (1.20), subdued_gfci (1.10), trade_tensions (1.05)
3. **Misalignment indicator** — `(eurusd_current − eurusd_equilibrium) / eurusd_equilibrium` with ±0.08 / ±0.05 trading thresholds
4. **GFCI proxy** — FRED NFCI (Chicago Fed) as free substitute for Goldman Sachs GFCI

Last line of module docstring: *"DO NOT implement until PRD-300 is Approved."* (PRD-300 was approved 2026-04-15 per commit `5bffd8b`, but file has not been updated since.)

### Public API
- `get_current_equilibrium(scenario) -> float` — **PLACEHOLDER** (NotImplementedError)
- `compute_misalignment(eurusd_current, scenario) -> dict` — **PLACEHOLDER**
- `decompose_eurusd_movement(eurusd, dxy, eur_basket) -> pd.DataFrame` — **PLACEHOLDER**
- `fetch_gfci_proxy(fred_api_key, start_date) -> pd.Series` — **PLACEHOLDER**
- `compute_equilibrium_scenario_from_regime(macro_regime, nfci) -> EquilibriumScenario` — **PLACEHOLDER**
- `get_equilibrium_signal(fred_api_key, macro_regime) -> dict` — **PLACEHOLDER** (main entry point)

Constants:
- `EquilibriumScenario = Literal["central", "subdued_gfci", "trade_tensions"]`
- `EQUILIBRIUM_RATES = {"central": 1.20, "subdued_gfci": 1.10, "trade_tensions": 1.05}`
- `GFCI_PROXY_FRED_TICKER = "NFCI"`

### References found (code imports / uses)
**Source files importing `equilibrium` or its symbols: NONE found.** The `divergence/__init__.py` file mentions equilibrium only in a docstring comment (*"Future (placeholders): equilibrium: BBVA misalignment + GFCI proxy (CC-4/CC-5)"*) — not an import statement.

Grep for symbols (`compute_misalignment`, `fetch_gfci_proxy`, `get_equilibrium_signal`, `decompose_eurusd_movement`, `EQUILIBRIUM_RATES`, `GFCI_PROXY_FRED_TICKER`) across `src/` + `tests/` + `notebooks/` returned 0 import hits outside the file itself.

### PRD alignment
- **PRD-300.md:** `line 114` — BBVA Research is cited as methodology source (*"BBVA Research / Martínez et al. (2025) — equilibrium EUR/USD model, decomposition în structural vs cyclical"*). However, the planned architecture tree (lines 80-110) of PRD-300 v2 lists: `decomposition/`, `calibration/`, `composite/`, `regime_conditional/`, `notifications/`, `pipeline.py` — **no `equilibrium/` or `equilibrium.py`**. PRD-300 v2 CC list (CC-1..CC-7) does not mention equilibrium as a deliverable.
- **ROADMAP.md:**
  - `line 138-145` — "EUR/USD Misalignment (BBVA Research 2025)" section enumerates the three scenarios + GFCI proxy
  - `line 262` — architecture tree shows `equilibrium.py ← BBVA misalignment + GFCI + USD/EUR decomp`
  - `line 510` — data source table: "BBVA Research (Martínez et al. 2025) → PRD-300 equilibrium"
  - `line 545` — "D12 | GFCI proxy = Chicago Fed NFCI (FRED)"
- **PRD-500.md:** `line 20` — `REQ-3: bba_mappers/layer3_divergence.py — map_divergence_to_bba(surprise, misalignment) → BBA (consumes PRD-300)`. Declared consumer of misalignment signal.
- **decisions/lessons:** no hits for `equilibrium|BBVA|GFCI|NFCI|misalignment`.

### Git history
- Total commits touching the file: **1**
- Last touched: `1397e3f` on `2026-04-10` — *"chore: initial project snapshot"*
- Active in last 14d: **no** (unchanged since initial import)

### Recommendation: **KEEP (deferred rewrite)**

**Justification:** Zero consumers today, but (a) PRD-500 explicitly depends on `misalignment` output, (b) ROADMAP treats it as a planned deliverable, and (c) the `divergence/__init__.py` docstring already flags it as a CC-4/CC-5 target. Deleting now would require re-creating similar stubs later; equilibrium scenarios + GFCI proxy are well-scoped BBVA methodology. The module is dormant but not dead.

**Mismatch with PRD-300 v2:** PRD-300 v2 architecture tree does **not** include an `equilibrium/` subdirectory. There is an unresolved inconsistency between ROADMAP (keeps equilibrium as Stratul 3 component) and PRD-300 v2 (omits it). Architect must reconcile: either (a) add `equilibrium/` to PRD-300 v2 scope, (b) spin off as PRD-301, or (c) accept it under PRD-500 bba_mappers.

**If eventually DELETE:** file to remove = `src/macro_context_reader/divergence/equilibrium.py`. No `__init__.py` re-export exists (already absent from `__all__`). ROADMAP.md + PRD-500.md would need consumer references retired.

**If eventually MOVE:** suggested new PRD = **PRD-301: EUR/USD Equilibrium & Misalignment (BBVA)** — Stratul 3 sibling, consumes FRED NFCI + DXY + ECB EUR basket, produces misalignment signal feeding PRD-500 bba_mappers.

---

## File 2: `regime_conditional.py`

### Purpose
Module docstring: *"Regime-conditional correlation analysis — PRD-300 CC-0d. Computes real_rate_differential ↔ EUR/USD correlations stratified by HMM-detected macro regime. Validates the regime-switching hypothesis (DEC-009)."* Diagnostic/validation tooling — confirms that global Pearson r = −0.045 masks regime-specific correlations that are individually strong.

### Public API
- `load_aligned_data(start="2003-01-01") -> pd.DataFrame` — **IMPLEMENTED**
- `compute_conditional_correlations(df, n_bootstrap, n_perm, max_lag_months, random_state) -> RegimeConditionalResults` — **IMPLEMENTED** (main entry point)
- `compute_lead_lag(x, y, max_lag=6) -> dict[int, float]` — **IMPLEMENTED**
- `_bootstrap_pearson_ci(x, y, ...)` — **IMPLEMENTED** (private)
- `_permutation_pvalue(x, y, ...)` — **IMPLEMENTED** (private)
- Pydantic schemas `RegimeCorrelation`, `RegimeConditionalResults` — **IMPLEMENTED**

Constants: `MIN_OBS_PER_REGIME = 30`.

### References found
- `tests/divergence/test_regime_conditional.py` — 12 tests importing `RegimeConditionalResults`, `compute_conditional_correlations`, `load_aligned_data` (all passing per audit snapshot)
- `notebooks/03_regime_conditional_diagnostic.ipynb` — companion diagnostic notebook
- `src/macro_context_reader/divergence/__init__.py` — re-exports as module attribute (`from . import decomposition, regime_conditional`; `__all__` includes it)
- `src/macro_context_reader/divergence/MAP.md` — documented
- `src/macro_context_reader/regime/MAP.md` — cross-reference
- `src/macro_context_reader/economic_sentiment/MAP.md` — mentioned
- `docs/ARCHITECTURE.md` — mentioned

### PRD alignment
- **PRD-300.md:** `line 94` — architecture tree lists `regime_conditional/` as a **subdirectory** containing `fitter.py` (weights per regime) + `router.py` (select weights based on current regime). Current single-file `regime_conditional.py` is a **diagnostic**, not the fitter/router. `line 154` — *"De ce regime-conditional (Q7 → B)"* discussion of the calibration strategy. `line 23` — *"regime-conditional weights — standard în macro research"*.
- **PRD-200.md:** `line 142` — AC-6 was reformulated as regime-conditional (*"reformulat ca regime-conditional a relației real_rate_differential ↔ EUR/USD"*). `line 193` — *"Diagnosticul empiric (notebook 02b_layer2_regime_diagnostic.ipynb) a confirmat regime switching"*.
- **ROADMAP.md:**
  - `line 175` — PRD-300 description: *"regime-conditional (Q7)"*
  - `line 232` — *"router.py ← get_regime_weights() + DEFAULT_REGIME_WEIGHTS"*
  - `line 551` — *"D18 | Corelații regime-conditional la PRD-300 (global r=−0.045 = regime-switching) | DEC-009"*
- **decisions/DEC-009-regime-switching-correlation.md** — dedicated decision memo.
- **decisions/DEC-005-ac6-reformulation-regime-conditional.md** — dedicated decision memo.

### Git history
- Total commits touching the file: **2**
- Last touched: `c3fb8da` on `2026-04-12` — *"fix(prd-300): align start date with T5YIE availability (2003-01-01) [PRD-300/CC-0d-FIX1]"*
- Prior: `daf75af` — *"feat(prd-300): regime-conditional correlation diagnostic [PRD-300/CC-0d]"*
- Active in last 14d: **yes** (actively maintained)

### Recommendation: **REWRITE (restructure into subdirectory)**

**Justification:** Fully implemented and tested (12 tests passing, diagnostic notebook) — the code itself is valuable and must NOT be deleted. However, PRD-300 v2 reserves the name `regime_conditional/` for a **subdirectory** holding `fitter.py` + `router.py` (CC-3 calibration weights per regime). The current single file occupies that namespace with diagnostic tooling that is semantically different from the planned fitter/router. When CC-3 arrives, the collision must be resolved.

**Proposed restructure (no code deletion):**
```
divergence/
├── regime_conditional/
│   ├── __init__.py
│   ├── diagnostic.py    ← move current regime_conditional.py here (rename internally)
│   ├── fitter.py        ← NEW in CC-3 (weights per regime)
│   └── router.py        ← NEW in CC-3 (select weights)
```
Preserves 12 passing tests (update import paths only) and keeps DEC-009 validation artifact alongside the production fitter/router when CC-3 implements them.

**Alternative (simpler):** rename file to `regime_conditional_diagnostic.py` at flat level, then create `regime_conditional/` subdirectory for CC-3 fitter/router. Avoids packaging reshuffle but fragments the semantic grouping.

**If DELETE (not recommended):** files to remove = `src/macro_context_reader/divergence/regime_conditional.py`, `tests/divergence/test_regime_conditional.py`, `notebooks/03_regime_conditional_diagnostic.ipynb`, plus `__init__.py` re-export. This would lose the DEC-009 empirical validation and PRD-200 AC-6 evidence — strongly discouraged.

---

## Cross-cutting findings

1. **Both files date-tag themselves to PRD-300 but represent different maturity:** `equilibrium.py` is day-0 stub that never progressed; `regime_conditional.py` is completed diagnostic work (CC-0d) that predates PRD-300 formal approval.

2. **PRD-300 v2 architecture does NOT match ROADMAP for equilibrium:** PRD-300 v2's module tree (`prds/PRD-300.md` lines 80-110) omits `equilibrium/` entirely, while `ROADMAP.md` line 262 lists it as a planned component, and `PRD-500.md` line 20 consumes a `misalignment` output. Document drift — one of the three must be updated.

3. **PRD-300 v2 namespace collision for `regime_conditional`:** current file occupies the name PRD-300 v2 reserves for a subdirectory (`fitter.py` + `router.py`). CC-3 implementation work will force this issue; preemptive restructure avoids a later breaking change.

4. **No orphan imports:** `divergence/__init__.py` only imports `decomposition` + `regime_conditional` (intentional). `equilibrium` is not re-exported, consistent with its placeholder status.

5. **Tests passing:** the current divergence test suite (35 passed per AUDIT_SNAPSHOT §4) includes 12 `regime_conditional` tests. Any restructure must preserve them by updating import paths only.

---

## Architect decision needed

| File | Decision required | Blocks |
|---|---|---|
| `equilibrium.py` | KEEP (as placeholder) vs MOVE-TO-NEW-PRD-301 vs accept under PRD-500 | Nothing immediately — but PRD-500 cannot finish `map_divergence_to_bba` until some module provides `misalignment`. Also requires reconciliation of PRD-300 v2 ↔ ROADMAP drift. |
| `regime_conditional.py` | REWRITE (subdirectory restructure) vs RENAME (flat keep) | **PRD-300/CC-3** (calibration with regime-conditional weights) — cannot start until namespace collision resolved |

Pending decisions block CC-3 work. CC-2 (Calibration layer without regime split) can proceed independently of either decision.

---

Audit complete. equilibrium.py → KEEP (deferred rewrite), regime_conditional.py → REWRITE (restructure into subdirectory). See AUDIT_DIVERGENCE.md.
