"""Pydantic schemas pentru Layer 2 — Market Pricing.

Acest modul definește schemele stricte de validare pentru toate datele
procesate în market_pricing: rate, FX, inflation expectations.

Regulile de design:
- Toate timestamp-urile sunt timezone-naive datetime (convenție ECB/FRED)
- Rate-urile sunt în procente (nu fracții): 2.5 = 2.5%, nu 0.025
- Valorile lipsă folosesc None, niciodată NaN în schemele Pydantic

Refs: PRD-200, research/INFLATION_EXPECTATIONS_METHODS.md
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

import math

from pydantic import BaseModel, Field, ConfigDict, model_validator


AccuracyTier = Literal["highest", "high", "medium", "low", "baseline"]
FrequencyType = Literal["daily", "weekly", "monthly", "quarterly"]


class MethodMetadata(BaseModel):
    """Metadata pentru o metodă de inflation expectations.

    Se propagă prin întregul pipeline până la output-ul final al
    real_rate_differential, permițând identificarea sursei și a
    nivelului de încredere metodologic.
    """

    model_config = ConfigDict(frozen=True)

    name: str = Field(..., description="Numele metodei, ex: 'ECB SPF 2Y'")
    source: str = Field(..., description="Sursa datelor, ex: 'ECB Data Portal'")
    frequency: FrequencyType
    accuracy_tier: AccuracyTier = Field(
        ..., description="Nivelul de acuratețe empirică validată"
    )
    validation_source: str = Field(
        ..., description="Referință academică care validează metoda"
    )
    known_biases: list[str] = Field(
        default_factory=list,
        description="Bias-uri cunoscute, ex: ['liquidity premium 15bp']",
    )
    forward_looking: bool = Field(
        ..., description="True dacă metoda e forward-looking (nu backward)"
    )


class InflationExpectationRow(BaseModel):
    """Un singur rând de inflation expectation."""

    model_config = ConfigDict(frozen=True)

    date: datetime
    horizon_years: float = Field(..., gt=0, le=10)
    expected_inflation: float = Field(
        ..., description="Inflația așteptată în procente (2.5 = 2.5%)"
    )
    method_name: str


class USRatesRow(BaseModel):
    """Un singur rând de rate US — orizont 5Y.

    Vezi decisions/DEC-001-switch-to-5y-horizon.md pentru motivul
    schimbării de la 2Y la 5Y.
    """

    model_config = ConfigDict(frozen=True)

    date: datetime
    us_5y_nominal: float
    us_5y_real: float
    us_5y_breakeven: float = Field(
        ..., description="Calculat ca us_5y_nominal - us_5y_real"
    )

    @model_validator(mode="after")
    def _reject_nan(self) -> USRatesRow:
        for name in ("us_5y_nominal", "us_5y_real", "us_5y_breakeven"):
            if math.isnan(getattr(self, name)):
                raise ValueError(f"{name} must not be NaN")
        return self


class EURRatesRow(BaseModel):
    """Un singur rând de rate EUR 5Y din ECB Yield Curve.

    Conține ambele variante AAA-only și All issuers, plus credit stress
    spread calculat. AAA-only e folosit ca input principal în real_rate_diff
    (simetrie metodologică cu US Treasury). All issuers și spread-ul sunt
    preservate ca semnale paralele independente.

    Vezi DEC-002 (decisions/DEC-002-dual-eur-yield-curves.md) pentru context.

    Source: ECB Yield Curve, Svensson model, daily TARGET business days.
    Series:
    - YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_5Y (AAA — G_N_A = triple A rated)
    - YC.B.U2.EUR.4F.G_N_C.SV_C_YM.SR_5Y (All — G_N_C = all ratings)

    Refs: PRD-200 CC-3, DEC-002
    """

    model_config = ConfigDict(frozen=True)

    date: datetime
    eu_5y_nominal_aaa: float = Field(
        ...,
        description="ECB AAA govt yield 5Y, methodological principal",
    )
    eu_5y_nominal_all: float = Field(
        ...,
        description="ECB all-issuer govt yield 5Y, parallel signal",
    )
    eu_credit_stress_5y: float = Field(
        ...,
        description="Spread = eu_5y_nominal_all - eu_5y_nominal_aaa, "
                    "indicator de stres financiar zona euro",
    )


class FXRow(BaseModel):
    """Un singur rând de FX."""

    model_config = ConfigDict(frozen=True)

    date: datetime
    eurusd: float = Field(..., gt=0, description="EUR/USD exchange rate")


class RealRateDiffRow(BaseModel):
    """Rând final agregat — real rate differential cu metadata."""

    model_config = ConfigDict(frozen=True)

    date: datetime
    us_5y_real: float
    eu_5y_real: float = Field(
        ..., description="Calculat ca eu_5y_nominal - eur_inflation_expectation"
    )
    real_rate_diff: float = Field(
        ..., description="us_5y_real - eu_5y_real, în procente"
    )
    eurusd: Optional[float] = None
    methodology_confidence: AccuracyTier
    inflation_method_name: str
