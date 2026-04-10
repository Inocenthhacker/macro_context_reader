# Decisions Log

This directory contains Architecture Decision Records (ADRs) for the
Macro Context Reader project. Each significant methodological or
architectural decision gets a dedicated file: DEC-XXX-short-title.md

## Format

Each DEC follows the structure:
- Context: what problem are we solving
- Options considered: what alternatives existed
- Decision: what we chose
- Rationale: why we chose it (with empirical evidence)
- Consequences: what changes in the project
- References: academic sources, official documentation

## Index

| ID | Title | Status | Date |
|---|---|---|---|
| DEC-001 | Switch from 2Y to 5Y horizon for real rate differential | Adopted | 2026-04-10 |

## Rules

1. Never delete a DEC file. Mark as "Superseded by DEC-XXX" if replaced.
2. New decisions go in new files, never edit old ones.
3. Each DEC corresponds to a git commit for traceability.
