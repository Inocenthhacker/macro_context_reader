"""
Aggregator — PRD-102 (Status: Draft)

Responsabilitate: indicator_matrix → model de agregare → predicție stance Fed

TREI OPȚIUNI DE AGREGARE — decizie empirică pe backtesting, niciuna exclusă a priori:

A) Ridge Regression — BASELINE (Faza 1)
   Partial pooling implicit prin regularizare. Simplu, interpretabil, zero overhead.
   Consistent cu principiul proiectului: modele simple pe date puține.
   Referință: Aruoba & Drechsel (2024) folosesc ridge pe indicatorii lor.

B) Bayesian Hierarchical Model — REZERVAT (Faza 2, activat după validare Faza 1)
   Structura ierarhică naturală a datelor Beige Book:
     Nivel 3: stance Fed național (parametru global)
         ↑ partial pooling
     Nivel 2: stance per district (parametru de grup)
         ↑ partial pooling
     Nivel 1: observație — frecvența entităților în text district × ediție

   Avantaje față de ridge:
     - Shrinkage automat proporțional cu volumul textului per district
       (Kansas City publică mai puțin → mai mult shrinkage spre media națională)
     - Propagare incertitudine end-to-end: intervalul de credibilitate al
       composite_divergence_score din PRD-300 reflectă incertitudinea cumulată
       district → național → divergență
     - Prior informativ pe district weights din Boston Fed (2025):
       NY și SF mai predictive = prior explicit pe varianța parametrilor,
       nu weight arbitrar hardcodat în YAML

   Output: national_hawkish_score = 0.65 [0.58, 0.71] 90% credible interval
           Confidență scăzută → nu intri în poziție sau reduci size-ul

   Librării candidate (toate open source, Colab T4 compatible):
     - numpyro (Apache 2.0) — MCMC pe JAX, GPU-accelerated, OPTIM pentru T4
     - pymc v5 (Apache 2.0) — MCMC + ADVI, Python nativ
     - stan/CmdStanPy (BSD) — MCMC, backend C++

   Referință: Gelman & Hill (2007), Data Analysis Using Regression and
   Multilevel/Hierarchical Models, Cambridge University Press, Cap. 11-13

   CONDIȚIE DE ACTIVARE: Faza 1 (ridge) completă + backtesting pe USMPD arată
   că incertitudinea e critică pentru sizing pozițiilor.

   DATE NECESARE: minim 5-10 ani Beige Book (480-960 observații) pentru MCMC
   fiabil. Arhiva Minneapolis Fed 1990-2025 este suficientă.

C) Variational Inference (ADVI) — compromis viteză/acuratețe față de MCMC full
   Mai rapid decât B dar produce aproximații ale posteriorului.
   Util dacă MCMC e prea lent pe hardware disponibil.
"""

from __future__ import annotations

from typing import Any, Literal

import pandas as pd

AggregationMethod = Literal["ridge", "bayesian_hierarchical", "advi"]


def fit(
    indicator_matrix: pd.DataFrame,
    target: pd.Series,
    method: AggregationMethod = "ridge",
) -> Any:
    """
    Antrenează modelul de agregare pe date istorice.

    Args:
        indicator_matrix: shape (n_editions, n_indicators)
                          MultiIndex coloane: (district, concept, subtype)
        target: shape (n_editions,)
                TODO: target variable TBD empiric — opțiuni:
                  - USMPD 30-min EUR/USD return post-FOMC
                  - FedWatch surprise score
                  - Realized vs. forecasted CPI delta
        method: "ridge" (default, Faza 1) |
                "bayesian_hierarchical" (Faza 2, rezervat) |
                "advi" (alternativă rapidă la MCMC)

    Returns:
        model fitted — sklearn-compatible pentru ridge,
                       numpyro/pymc model object pentru bayesian

    TODO: implementare în ordinea fazelor. Nu sări la Faza 2 fără
          validarea empirică a Fazei 1 pe USMPD.
    """
    raise NotImplementedError("TODO: PRD-102")


def predict(
    indicator_vector: pd.Series,
    model: Any,
    return_interval: bool = False,
) -> dict[str, float]:
    """
    Produce predicția stance Fed pentru un document nou.

    Args:
        indicator_vector: vectorul de indicatori pentru o ediție nouă
        model: modelul fitted din fit()
        return_interval: dacă True, returnează și intervalul de credibilitate
                         (disponibil doar pentru method="bayesian_hierarchical"
                          sau "advi" — pentru ridge returnează None)

    Returns:
        {
          "national_hawkish_score": 0.65,
          "credible_interval_90": [0.58, 0.71],  # None dacă method="ridge"
          "district_scores": {                    # None dacă method="ridge"
              "new_york": 0.71,
              "san_francisco": 0.68,
              ...
          }
        }
    """
    raise NotImplementedError("TODO: PRD-102")
