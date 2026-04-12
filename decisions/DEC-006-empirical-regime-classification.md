# DEC-006: Empirical Regime Classification (HMM + Mahalanobis)

**Status:** Adopted
**Date:** 2026-04-12
**PRD:** PRD-050 CC-1+2+3
**Commits:** c69d73e, 1d32bb5

## Context

PRD-050 draft initial proposed a rule-based regime classifier with YAML-configured
thresholds (e.g., CPI YoY > 3.0% → INFLATION regime). The `config/regime_thresholds.yaml`
file defined fixed numeric boundaries for FINANCIAL_STABILITY, INFLATION, and GROWTH.

User directive: "Zero hardcoded thresholds. Nu reject/defer pentru complexitate;
state-of-the-art din prima."

## Options Considered

1. **Rule-based with YAML thresholds** (original PRD-050 draft)
   - Pro: Simple, interpretable, fast
   - Con: Thresholds are arbitrary; regime boundaries shift over time

2. **Percentile-based classification**
   - Pro: Data-adaptive thresholds
   - Con: Still requires manual feature→regime mapping

3. **Gaussian Mixture Models (GMM)**
   - Pro: Data-driven clustering
   - Con: No temporal structure; ignores regime persistence

4. **Hidden Markov Model (HMM) + Mahalanobis analogs** (chosen)
   - Pro: Latent state learning respects temporal dynamics; analog detection provides
     interpretability via historical matches; consensus mechanism handles disagreement
   - Con: More complex; requires stability validation (addressed by ARI threshold)

## Decision

Replace rule-based classifier with dual-method empirical approach:
- **HMM (GaussianHMM):** Discovers latent regime states from 6 FRED macro features.
  Model selection via BIC + ARI stability (see DEC-008).
- **Mahalanobis Analog Detector:** Finds historically similar periods using distance
  in feature space. Tikhonov regularization for near-singular covariance.
- **Consensus:** If HMM state matches dominant state of top-3 analogs → HIGH confidence.
  Divergence → LOW confidence with `conflicting_signals=True`.

Auto-generated labels from dominant feature z-scores (e.g., "CPI_YOY_HIGH",
"NFCI_HIGH") — no manual label assignment.

## Rationale

1. Macro regimes are latent constructs — no single threshold defines them
2. HMM captures temporal persistence (regimes last months, not days)
3. Analog detection provides economic interpretability (what happened last time?)
4. Consensus mechanism handles model disagreement explicitly
5. Academic backing: Mulliner et al. (2025) for Mahalanobis analogs

## Consequences

- `config/regime_thresholds.yaml` is now legacy (kept for reference, not used by HMM)
- `classifier.py` (rule-based) remains as skeleton for potential comparison
- PRD-300 divergence calibration will be regime-conditional (see DEC-009)
- PRD-500 DST weights sourced from HMM regime, not rule-based classification

## References

- Mulliner, Harvey, Xia & Fang (2025), "Regimes", SSRN 5164863
- Chiapparoli (2025), "Macroeconomic Factor Timing", SSRN 5287108
- Thim (2012), Acta Anaesthesiologica — ABCDE triage protocol analogy
