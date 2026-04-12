# DEC-011: API Change Protocol — Notebooks Sync Obligatoriu

**Status:** Adopted
**Date:** 2026-04-12
**PRD:** Cross-cutting

## Context

During PRD-050 CC-1b, `hmm_classifier.fit()` signature changed from
`candidate_states=(3,)` to `n_states_grid=[3]`. The test file `test_consensus.py`
was not updated synchronously, causing `TypeError` at test runtime.

While caught quickly (in the same session), this illustrates the risk of API
changes that silently break downstream consumers — especially notebooks which
are not covered by pytest and may fail silently when run days later.

## Decision

Any change to a function/method signature in `src/` modules must include
synchronous updates to ALL references in:
- `tests/` — caught by pytest, but must be updated in same commit
- `notebooks/` — NOT caught by pytest; must be grep-verified
- `docs/` — code examples in .md files

**Verification step before commit:**
```bash
grep -rn "{old_parameter_name}" notebooks/ tests/ docs/ --include="*.py" --include="*.ipynb" --include="*.md"
```
All hits must be updated. Zero tolerance for stale API references.

## Rationale

- Notebooks run in Jupyter, not pytest — broken imports surface only when
  a user manually runs them (potentially days later)
- `test_consensus.py` failure in this session was caught because we run
  `pytest tests/regime/ -v` as part of the DONE WHEN criteria
- Preventive grep is cheaper than debugging a TypeError in a notebook

## Consequences

- Claude Code prompts that change function signatures include a grep verification step
- Notebook cells with import statements are treated as integration surface
- DONE WHEN criteria for refactor prompts include: "zero stale references in
  notebooks/ tests/ docs/ via grep"
