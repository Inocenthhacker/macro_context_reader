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

from pydantic import BaseModel, Field, ConfigDict


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
    us_breakeven_implied: float = Field(
        ..., description="Calculat ca us_5y_nominal - us_5y_real"
    )


class EURRatesRow(BaseModel):
    """Un singur rând de rate EUR (guvernamentale, proxy pentru OIS)."""

    model_config = ConfigDict(frozen=True)

    date: datetime
    eu_5y_nominal: float = Field(
        ..., description="ECB govt yield 5Y, proxy pentru OIS (spread <15bp)"
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
