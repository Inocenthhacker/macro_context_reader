# Changelog

All notable changes to the Macro Context Reader project.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
