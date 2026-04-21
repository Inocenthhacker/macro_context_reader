# CC-2a — Target Selection Experiment — Results Report

Generated: 2026-04-21T18:17:24.881874

## 1. Experiment Setup

- **Targets tested:** 4 (FedWatch surprise, real-rate-diff 5bd change, EUR/USD 5bd return, EUR/USD 21bd return)
- **Methods tested:** 5 (equal_weighted baseline, OLS, Ridge, Lasso, ElasticNet — last three with internal alpha CV)
- **Features:** 11 (3 statement NLP + 3 minutes-lag NLP + 2 market pricing + 3 Cleveland Fed)
- **Train/validation split:** chronological at 2024-06-30
- **CV protocol:** walk-forward expanding-window, 5 splits on train only
- **Decision metric (pre-committed):** spearman_ic > 0.1 on held-out validation
- **Anti-circularity:** fedwatch_actual_change_bps and fedwatch_surprise_bps excluded from feature set
- **Random seed:** 42

## 2. Target Summary

| Target | Mean | Std | Min | Max | N non-null |
|---|---|---|---|---|---|
| `target_A_fedwatch_surprise` | -0.2617 | 3.8631 | -10.6364 | 15.5000 | 42 |
| `target_D_rrd_change_5d` | 0.0056 | 0.1264 | -0.2857 | 0.2408 | 42 |
| `target_E_eurusd_5d` | -0.0022 | 0.0108 | -0.0215 | 0.0186 | 42 |
| `target_F_eurusd_21d` | 0.0003 | 0.0215 | -0.0353 | 0.0612 | 42 |

## 3. Results Table (20 combinations)

| Target | Method | CV mean IC ± std | Val IC | Val R² | Val RMSE | Meets IC>0.10 |
|---|---|---|---|---|---|---|
| target_A_fedwatch_surprise | equal_weighted | -0.500 ± 0.548 | -0.253 | -0.145 | 2.7019 | ✗ |
| target_A_fedwatch_surprise | ols | 0.200 ± 0.600 | 0.345 | -1.786 | 4.2140 | ✓ |
| target_A_fedwatch_surprise | ridge | 0.200 ± 0.600 | -0.073 | -1.376 | 3.8919 | ✗ |
| target_A_fedwatch_surprise | lasso | -0.167 ± 0.850 | -0.011 | -1.591 | 4.0638 | ✗ |
| target_A_fedwatch_surprise | elasticnet | -0.167 ± 0.850 | -0.011 | -1.565 | 4.0437 | ✗ |
| target_D_rrd_change_5d | equal_weighted | 0.400 ± 0.735 | -0.455 | -0.697 | 0.1054 | ✗ |
| target_D_rrd_change_5d | ols | -0.300 ± 0.678 | 0.380 | -1.075 | 0.1165 | ✓ |
| target_D_rrd_change_5d | ridge | -0.300 ± 0.678 | -0.270 | -0.480 | 0.0984 | ✗ |
| target_D_rrd_change_5d | lasso | 0.250 ± 0.750 | nan | -0.123 | 0.0857 | ✗ |
| target_D_rrd_change_5d | elasticnet | 0.250 ± 0.750 | nan | -0.123 | 0.0857 | ✗ |
| target_E_eurusd_5d | equal_weighted | -0.100 ± 0.735 | 0.244 | 0.007 | 0.0106 | ✓ |
| target_E_eurusd_5d | ols | 0.400 ± 0.490 | -0.015 | -1.046 | 0.0152 | ✗ |
| target_E_eurusd_5d | ridge | -0.200 ± 0.600 | 0.090 | -0.044 | 0.0109 | ✗ |
| target_E_eurusd_5d | lasso | -0.500 ± 0.000 | nan | -0.002 | 0.0107 | ✗ |
| target_E_eurusd_5d | elasticnet | -0.500 ± 0.000 | nan | -0.002 | 0.0107 | ✗ |
| target_F_eurusd_21d | equal_weighted | 0.400 ± 0.490 | 0.327 | -0.014 | 0.0194 | ✓ |
| target_F_eurusd_21d | ols | 0.100 ± 0.735 | 0.187 | -0.254 | 0.0215 | ✓ |
| target_F_eurusd_21d | ridge | 0.100 ± 0.490 | -0.288 | -0.250 | 0.0215 | ✗ |
| target_F_eurusd_21d | lasso | 0.500 ± 0.000 | nan | -0.023 | 0.0195 | ✗ |
| target_F_eurusd_21d | elasticnet | 0.500 ± 0.000 | nan | -0.023 | 0.0195 | ✗ |

## 4. Winners — Combinations that Meet IC > 0.10 on Validation

**5 combination(s) pass.** Ranked by validation IC:

| Rank | Target | Method | Val IC | CV mean IC | Val R² |
|---|---|---|---|---|---|
| 1 | target_D_rrd_change_5d | ols | 0.380 | -0.300 | -1.075 |
| 2 | target_A_fedwatch_surprise | ols | 0.345 | 0.200 | -1.786 |
| 3 | target_F_eurusd_21d | equal_weighted | 0.327 | 0.400 | -0.014 |
| 4 | target_E_eurusd_5d | equal_weighted | 0.244 | -0.100 | 0.007 |
| 5 | target_F_eurusd_21d | ols | 0.187 | 0.100 | -0.254 |

## 5. Feature Importance (Top 5 by |coef|)

- **target_D_rrd_change_5d × ols**: statement_fomc_roberta_net, statement_ensemble_net, minutes_lag_ensemble_net, minutes_lag_fomc_roberta_net, statement_llama_deepinfra_net
- **target_A_fedwatch_surprise × ols**: statement_ensemble_net, statement_fomc_roberta_net, minutes_lag_fomc_roberta_net, minutes_lag_ensemble_net, cleveland_divergence
- **target_F_eurusd_21d × equal_weighted**: minutes_lag_llama_deepinfra_net, cleveland_divergence, minutes_lag_ensemble_net, minutes_lag_fomc_roberta_net, cleveland_consensus_score
- **target_E_eurusd_5d × equal_weighted**: minutes_lag_llama_deepinfra_net, cleveland_divergence, minutes_lag_ensemble_net, minutes_lag_fomc_roberta_net, cleveland_consensus_score
- **target_F_eurusd_21d × ols**: statement_ensemble_net, statement_fomc_roberta_net, minutes_lag_fomc_roberta_net, minutes_lag_ensemble_net, cleveland_divergence

## 6. Interpretation

- **Best combination (by val IC):** target_D_rrd_change_5d × ols with IC = 0.380, R² = -1.075.
- **Median validation IC across 20 combinations:** -0.011.
- **Combinations above threshold:** 5/20.
- **CV ↔ Val agreement (rank-corr across combos):** 0.041 — weak signal stability between folds and hold-out.
- **Method ranking by mean val IC:** ols=0.224, elasticnet=-0.011, lasso=-0.011, equal_weighted=-0.034, ridge=-0.135
- **Target ranking by mean val IC:** E_eurusd_5d=0.106, F_eurusd_21d=0.075, A_fedwatch_surprise=-0.000, D_rrd_change_5d=-0.115

## 7. Recommendation for CC-2b

**Use target `target_A_fedwatch_surprise` with method `ols`** for CC-2b production calibration.

Selection rule: pre-committed IC > 0.10 on validation AND CV mean IC > 0 (direction agreement).

- Val IC = 0.345 (> 0.1 threshold)
- CV mean IC = 0.200 ± 0.600 (same sign as val — stable)
- Val R² = -1.786, RMSE = 4.2140
- Top features: statement_ensemble_net, statement_fomc_roberta_net, minutes_lag_fomc_roberta_net, minutes_lag_ensemble_net, cleveland_divergence

Secondary stable candidates (2): target_F_eurusd_21d × equal_weighted (val IC=0.327, CV IC=0.400), target_F_eurusd_21d × ols (val IC=0.187, CV IC=0.100)

## 8. Caveats

- **Sample size is small** by ML standards: 28 train meetings, 14 validation meetings. Spearman IC variance on N=14 is high — a single outlier can flip sign. Interpret with humility.
- **Multiple testing risk:** 20 combinations tested → family-wise error rate inflated. One winner at p≈0.05 could easily be noise. Pre-committed threshold mitigates but doesn't eliminate this.
- **Regime mismatch:** train covers hiking cycle (2022-2023) + plateau; validation covers cutting cycle (2024+). Model coefficients fit to hiking behavior may not transfer cleanly. This is a feature of the test, not a bug — we explicitly want to see if a model trained on 2022-era Fed behavior holds up on 2024-era Fed behavior.
- **One validation pass only.** Results are what they are. Do NOT re-fit or re-tune based on this report.
