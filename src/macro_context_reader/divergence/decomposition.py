"""
Deep Current vs. Surface Wave Decomposition — PRD-300 / REQ-8
Inspirat din: Broecker (1991), "The Great Ocean Conveyor", Oceanography

Principiu: EUR/USD are doua layere cu orizonturi temporale radical diferite.
  - Deep current  = real rate differential trend structural (saptamani-luni)
  - Surface waves = deviatii temporare, spike-uri, zgomot intraday

Regula operationala (Broecker 1991):
  daca deep_current_stable AND surface_wave contra deep_current
  -> ignora spike-ul, ramai in directia curentului

Trei metode implementate si comparate empiric pe USMPD backtesting:
  A) HP Filter (Hodrick-Prescott) — statsmodels, standard macroeconomic
     Pro: simplu, interpretabil, standard in macro
     Con: edge effects la capatul seriei (endpoint bias)
     lambda=1600 = prior pentru date zilnice, calibrat empiric

  B) EMD (Empirical Mode Decomposition) — PyEMD
     Pro: adaptiv, fara parametri de smoothing, robust la non-stationaritate
     Con: harder to interpret, computationally heavier
     IMF[-1] = componenta cu frecventa cea mai joasa = deep current

  C) Rolling mean multi-scale — baseline, zero librarii extra
     Pro: trivial, fara dependente, complet transparent
     Con: lag la tranzitii, window fixa
     window=63 zile (3 luni) = prior, calibrat empiric

Decizie finala: metoda cu Sharpe ratio maxim pe USMPD 30-min windows.

CALIBRARE EMPIRICĂ — rolling_window=63 zile (3 luni):

Pragul de 63 zile nu e arbitrar. E validat academic de:
Gebauer, Georgiadis, Holm-Hadulla, Kostka (2025), ECB Blog:
"What Happens When US and Euro Area Monetary Policy Decouple?"
https://www.ecb.europa.eu/press/blog/date/2025/html/ecb.blog20250205~44578cf53f.en.html

Descoperire empirică pe date 2002–2024 (local projections):

  0–3 luni  (window < 63 zile) — SURFACE WAVE:
    Fed tightening surpriză → EUR slăbește (efect FX direct)
    → euro area inflation CREȘTE (importuri mai scumpe în USD)
    → efect OPUS față de BCE tightening
    → semnalul NLP hawkish Fed = bullish USD pe termen scurt ✓

  3+ luni (window >= 63 zile) — DEEP CURRENT:
    Fed tightening → economia SUA încetinește → cerere mai mică
    pentru exporturi europene → economia europeană se răcește
    → efect IDENTIC cu BCE tightening
    → divergența Fed-BCE se comprimă singură pe termen mediu
    → semnalul NLP hawkish Fed se atenuează structural

Implicație operațională:
  Sub 63 zile: Fed hawkish = semnal valid bullish USD
  Peste 63 zile: Fed hawkish = divergență se auto-comprimă,
                 semnal trebuie discountat proporțional cu orizontul
"""

from __future__ import annotations

from typing import Literal

import pandas as pd

DecompositionMethod = Literal["hp_filter", "emd", "rolling_mean"]


def decompose_series(
    series: pd.Series,
    method: DecompositionMethod = "hp_filter",
    hp_lambda: float = 1600.0,
    rolling_window: int = 63,
) -> dict[str, pd.Series]:
    """
    Descompune o serie temporala in deep current (trend structural)
    si surface wave (deviatie temporara).

    Args:
        series: seria de descompus (real_rate_differential sau
                composite_divergence_score)
        method: "hp_filter" | "emd" | "rolling_mean"
        hp_lambda: parametrul de smoothing HP (1600 = standard zilnic)
                   calibrat empiric — valori mai mari = trend mai smooth
        rolling_window: fereastra pentru rolling mean (default 63 = 3 luni)

    Returns:
        {
          "deep_current": pd.Series,   <- componenta structurala
          "surface_wave": pd.Series,   <- deviatie temporara
          "method": str,
        }

    TODO: implementare la activare PRD-300.
          Validare pe USMPD: care metoda produce Sharpe ratio mai bun?
    """
    raise NotImplementedError("TODO: PRD-300")


def compute_deep_current_signal(
    deep_current: pd.Series,
    normalize_window: int = 252,
) -> pd.Series:
    """
    Normalizeaza deep_current pe rolling window -> semnal in [-1, +1].

    Args:
        deep_current: output din decompose_series()["deep_current"]
        normalize_window: fereastra de normalizare (default 252 = 1 an)

    Returns:
        pd.Series in [-1, +1] — pozitiv = USD bullish structural

    TODO: PRD-300
    """
    raise NotImplementedError("TODO: PRD-300")


def is_deep_current_stable(
    deep_current: pd.Series,
    stability_window: int = 5,
    stability_threshold: float = 0.05,
) -> pd.Series:
    """
    Detecteaza daca deep current e stabil sau in tranzitie.

    Stabil = pct_change pe stability_window < stability_threshold.
    Instabil = deep current se misca -> posibila tranzitie de regim.

    Returns:
        pd.Series[bool] — True = stabil, False = in schimbare

    TODO: PRD-300
    """
    raise NotImplementedError("TODO: PRD-300")


def compute_decision_signal(
    deep_current: pd.Series,
    surface_wave: pd.Series,
) -> pd.Series:
    """
    Aplica regula Broecker: deep current + surface wave -> semnal de decizie.

    Logica:
      deep_current_stable AND surface_wave contra deep_current
        -> "ignore_surface_spike"
      deep_current instabil AND surface_wave confirma directia
        -> "trend_transition_confirmed"
      deep_current instabil AND surface_wave contra
        -> "conflicting_signals"
      deep_current stabil AND surface_wave confirma
        -> "trend_confirmed"

    Returns:
        pd.Series[str] cu valorile de mai sus

    TODO: PRD-300 — calibrare threshold stabilitate empiric pe USMPD
    """
    raise NotImplementedError("TODO: PRD-300")


def compute_horizon_adjusted_signal(
    nlp_hawkish_score: float,
    trading_horizon_days: int,
    surface_threshold_days: int = 63,
) -> dict[str, float]:
    """
    Ajustează semnalul NLP hawkish în funcție de orizontul temporal
    al tranzacției, pe baza mecanismului de transmisie Fed→EUR documentat
    empiric de Gebauer et al. (2025), ECB Blog.

    Logica:
      trading_horizon_days < surface_threshold_days (63 zile):
        → ești în "surface wave" — efect FX direct domină
        → adjusted_signal = nlp_hawkish_score × 1.0  (fără discount)

      trading_horizon_days >= surface_threshold_days:
        → ești în "deep current" — efect economic indirect atenuează
        → divergența Fed-BCE se comprimă singură
        → adjusted_signal = nlp_hawkish_score × decay_factor
        → decay_factor = surface_threshold_days / trading_horizon_days
          (exemplu: 63/126 = 0.5 la 6 luni, 63/252 = 0.25 la 1 an)

    Args:
        nlp_hawkish_score: scorul FOMC-RoBERTa ∈ [0, 1]
        trading_horizon_days: orizontul tranzacției în zile de trading
        surface_threshold_days: pragul empiric ECB (default 63 = 3 luni)

    Returns:
        {
          "original_score": float,
          "adjusted_score": float,   ← semnalul corectat pentru orizont
          "decay_factor": float,     ← 1.0 dacă surface, <1.0 dacă deep
          "horizon_regime": str,     ← "surface_wave" | "deep_current"
          "rationale": str,          ← explicație human-readable
        }

    Referință: Gebauer et al. (2025), ECB Blog
    https://www.ecb.europa.eu/press/blog/date/2025/html/ecb.blog20250205~44578cf53f.en.html

    NOTE: decay_factor e un prior liniar simplu — calibrat empiric pe
          USMPD backtesting la activarea PRD-300. Poate fi non-liniar.

    TODO: PRD-300 — implementare la activare.
          Backtesting: compară Sharpe ratio cu și fără ajustare pe
          USMPD windows de diferite orizonturi (5d, 21d, 63d, 126d).
    """
    raise NotImplementedError("TODO: PRD-300")


def compare_methods_backtesting(
    series: pd.Series,
    usmpd_returns: pd.Series,
) -> pd.DataFrame:
    """
    Compara toate trei metode pe datele USMPD.

    Args:
        series: real_rate_differential sau composite_divergence_score
        usmpd_returns: EUR/USD 30-min returns din SF Fed USMPD

    Returns:
        pd.DataFrame cu Sharpe ratio per metoda:
        | method      | sharpe | max_drawdown | hit_rate |
        |-------------|--------|--------------|----------|
        | hp_filter   | ...    | ...          | ...      |
        | emd         | ...    | ...          | ...      |
        | rolling_mean| ...    | ...          | ...      |

    NOTE: metoda cu Sharpe maxim devine default in productie.
          Aceasta e singura functie care trebuie rulata o singura data
          la activarea PRD-300.

    TODO: PRD-300
    """
    raise NotImplementedError("TODO: PRD-300")
