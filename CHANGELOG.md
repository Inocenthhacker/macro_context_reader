# Changelog

All notable changes to the Macro Context Reader project.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased] - 2026-04-15

### Added

- **PRD-202: CME FedWatch Loader & Surprise Signal** — full implementation
  - CC-1: Parser CME FedWatch CSV + pydantic schemas (commit `451b1dc`)
  - CC-2: Multi-snapshot loader with dedup + Parquet (commit `0d1f93c`)
  - CC-2-PATCH: Logging warnings on invalid files (commit `f49f91d`)
  - CC-3: Surprise signal with 3 methods — binary, expected_change (Gürkaynak-Sack-Swanson 2005), kl_divergence (commit `0cb3493`)
  - CC-4: MAP.md for fedwatch/ submodule (commit `896bb97`, batch with onboarding)
  - 56 tests passing; smoke test validated end-to-end (9220 rows, 3 methods return sensible magnitudes)

- **Onboarding scaffold for new collaborators** (commit `896bb97`)
  - README expanded from 814B to 82 lines with phase status + doc links
  - 4 docs: `docs/ONBOARDING.md`, `ARCHITECTURE.md`, `DATA_REFRESH.md`, `WORKFLOW.md`
  - 8 new `MAP.md` files (regime, rhetoric, positioning, monitoring, divergence, output, economic_sentiment, market_pricing/fedwatch) — total now 9 with pre-existing market_pricing/
  - `.gitignore` broader globs for test residue + FinFut dumps

- **8 missing PRD standalone files** (commit `dc12431`): PRD-001, 002, 051, 101, 102, 300, 401, 500 — all YAML-ish frontmatter per CLAUDE.md canonical template

- **Decisions D23-D26** added to ROADMAP §8:
  - D23: CME FedWatch CSV manual snapshots (FRED/FTP unavailable)
  - D24: 3 surprise methods simultaneous (selection deferred to PRD-300)
  - D25: Default NLP→bps calibration 25bps (OLS recal in PRD-300)
  - D26: Context awareness mandatory in Claude Code edit prompts

- **Technical Debt log** (ROADMAP §11):
  - TD-1: CME FedWatch CSV manual refresh (low priority)
  - TD-2: PRD-101 integration tests need HF_TOKEN skip guard (medium priority)
  - TD-3: CLAUDE.md line 98 references defunct CME FTP (low priority)

### Changed

- **PRD-202 slot reused** (commit `8d98b08`): old "Tactical Short-Horizon Signal Layer" (Draft, never implemented) archived to `prds/archived/PRD-202-tactical-superseded.md` with superseded banner; slot now holds "FedWatch Probabilities Loader & Surprise Signal" matching shipped reality
- **PRD-400 frontmatter** migrated from markdown-header style to YAML-ish block (commit `8d98b08`)
- **Faza 2 (NLP Layer)** marked ~85% Done after audit 2026-04-14 corrected PRD-101 status from ❌ to ~85% Done (47 unit + 4 integration tests)
- **Stray root files** removed: `FinFutYY.txt`, `integration_after_patch_v2.txt`, `unit_after_patch_v2.txt`, `setup_*_output.txt`

### Fixed

- PRD-202.md status corrected from `~95% Done` to `Done` after MAP.md verification (this commit)

## [Unreleased] - 2026-04-12

### Added

- **PRD-050 CC-1+2+3:** Macro Regime Classifier — HMM + Mahalanobis analog detector + consensus (c69d73e, 1d32bb5)
  - `regime/schemas.py`: Pydantic models (StateProfile, AnalogMatch, RegimeClassification, HMMFitDiagnostics)
  - `regime/indicators.py`: 6-feature FRED matrix (CPI, PCE, GDP, UNRATE, NFCI, T10Y2Y)
  - `regime/hmm_classifier.py`: GaussianHMM with BIC model selection, auto-generated labels
  - `regime/analog_detector.py`: Mahalanobis distance with Tikhonov regularization, anti-leakage
  - `regime/consensus.py`: HMM+Analog aggregation with confidence scoring
  - `tests/regime/`: 19 initial tests (hmm: 6, analog: 7, consensus: 6)
  - `notebooks/01_regime_classifier_validation.ipynb`: empirical validation notebook
  - Dependencies: hmmlearn>=0.3, scikit-learn>=1.4, scipy>=1.12

- **DEC-006 through DEC-011:** 6 new architectural decision records
  - DEC-006: Empirical regime classification (no hardcoded thresholds)
  - DEC-007: Full-history scaler scope
  - DEC-008: HMM diag covariance + BIC+ARI grid selection
  - DEC-009: Regime-switching correlation for PRD-300
  - DEC-010: Session workflow (chat-first decisions, batch docs)
  - DEC-011: API change protocol (notebooks sync)

- **PRD-050.md:** Full PRD document (was missing, only placeholder code existed)
- **CHANGELOG.md:** This file

### Changed

- **PRD-050 CC-1b:** HMM fit strategy refactor (c778a5e, ca1651f)
  - Scaler: fit on full history instead of pre-COVID window (DEC-007)
  - Covariance: "diag" default instead of "full" (DEC-008)
  - Grid: extended to [2,3,4,5,6,7,8] with 10-seed evaluation
  - Selection: dual criterion BIC + ARI stability (threshold 0.70)
  - Labels: duplicate prevention with secondary feature discriminator
  - Tests: expanded to 12 (was 6), including ARI fallback and unique labels
  - Notebook: added BIC/AIC/ARI triple plot (cell 3)

- **PRD-400-RESTRUCTURE CC-4:** Mechanical rebrand cot_structural → cot_leveraged_funds (846ae6d, 5d5629d)
  - 3 files renamed via git mv
  - 4 import/patch paths updated in test file
  - 18 references updated across 5 .md files
  - Zero logic changes

- **ROADMAP.md:** Updated PRD registry, Faza 1 status, architectural decisions D15-D19
- **PRD-200.md:** Minor status clarification
- **decisions/README.md:** Index updated with DEC-006 through DEC-011

### Fixed

- `analog_detector.py`: exclude_window_days=0 no longer excludes the query point itself
- `test_consensus.py`: updated `candidate_states` → `n_states` after CC-1b API change (DEC-011)
