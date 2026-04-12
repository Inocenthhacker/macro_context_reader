# DEC-010: Session Workflow — Chat-First Decisions, Batch Documentation

**Status:** Adopted
**Date:** 2026-04-12
**PRD:** Cross-cutting

## Context

During session 2026-04-12, several architectural decisions were made iteratively
in chat (scaler scope, covariance type, BIC+ARI grid) and implemented immediately
in Claude Code prompts. Documentation was consolidated at session end rather than
maintained synchronously during implementation.

## Decision

1. **Technical decisions are made in chat**, not in PRD documents mid-session.
   The discussion is the decision process; the code is the implementation.

2. **Claude Code prompts generated directly** without new PRD for:
   - Mechanical renames / rebrand operations
   - Refactors that don't change architecture (e.g., scaler scope, covariance type)
   - Bug fixes
   - Test additions to existing modules

3. **Formal PRD required** only for:
   - New algorithm or methodology (e.g., HMM classifier was PRD-050)
   - New architectural layer or module
   - New external data source integration

4. **Documentation (ROADMAP, PRD updates, DEC records, registry) consolidated
   in a single batch at session checkout**, triggered explicitly by user
   ("update documentele", "checkout", "consolidează").

## Rationale

- Mid-session PRD updates create merge conflicts with implementation commits
- Chat decisions are traceable via git log commit messages referencing PRD/CC IDs
- Batch documentation ensures consistency (all docs reflect same final state)
- Reduces overhead: 1 documentation batch vs. N mid-session interruptions

## Consequences

- DEC records may reference multiple commits (not 1:1 DEC:commit)
- ROADMAP is only guaranteed accurate after a session checkout, not during
- Commit messages MUST include PRD/CC references for traceability
