# Archived PRDs

This folder contains PRDs that were drafted but **never implemented** and have been **superseded** by other PRDs occupying the same ID slot.

## Why archive instead of delete?

- Historical record of design thinking
- Disambiguation when git log references old PRD IDs
- Audit trail for PRD ID reuse decisions

## Files

| File | Original ID | Superseded by | Reason |
|---|---|---|---|
| PRD-202-tactical-superseded.md | PRD-202 | PRD-202 (FedWatch Loader) | Old tactical short-horizon signal draft never implemented; slot reused for FedWatch after audit 2026-04-15 found FRED/CME FTP unavailable |

## Rules

- Files here are **read-only reference** — do NOT modify
- Do NOT reference archived PRDs from active code or active PRDs
- If archiving a new PRD: add a row to the table above with reason
