"""Tests pentru Protocol-ul InflationExpectationsMethod și schemele asociate.

Refs: PRD-200 CC-1
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest
from pydantic import ValidationError

from macro_context_reader.market_pricing.inflation_expectations.base import (
    InflationExpectationsMethod,
)
from macro_context_reader.market_pricing.schemas import (
    MethodMetadata,
    InflationExpectationRow,
)


class _MockCompleteMethod:
    """Mock care implementează complet Protocol-ul."""

    @property
    def name(self) -> str:
        return "Mock Complete"

    @property
    def frequency(self) -> str:
        return "quarterly"

    @property
    def source(self) -> str:
        return "Mock Source"

    def fetch(self, start: datetime, end: datetime) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "date": [start, end],
                "expected_inflation": [2.0, 2.1],
                "horizon_years": [2.0, 2.0],
            }
        )

    def get_at_date(self, date: datetime, horizon_years: float = 2.0) -> float:
        return 2.0

    def get_metadata(self) -> MethodMetadata:
        return MethodMetadata(
            name="Mock Complete",
            source="Mock Source",
            frequency="quarterly",
            accuracy_tier="high",
            validation_source="test",
            known_biases=[],
            forward_looking=True,
        )


class _MockIncompleteMethod:
    """Mock care NU implementează toate metodele (lipsește get_metadata)."""

    @property
    def name(self) -> str:
        return "Mock Incomplete"

    @property
    def frequency(self) -> str:
        return "quarterly"

    @property
    def source(self) -> str:
        return "Mock"

    def fetch(self, start: datetime, end: datetime) -> pd.DataFrame:
        return pd.DataFrame()

    def get_at_date(self, date: datetime, horizon_years: float = 2.0) -> float:
        return 0.0

    # Lipsește intenționat get_metadata


def test_protocol_importable():
    """Protocol-ul trebuie să fie importabil din inflation_expectations."""
    assert InflationExpectationsMethod is not None


def test_complete_mock_satisfies_protocol():
    """O clasă completă trebuie recunoscută ca implementare a Protocol-ului."""
    mock = _MockCompleteMethod()
    assert isinstance(mock, InflationExpectationsMethod)


def test_incomplete_mock_fails_protocol():
    """O clasă incompletă NU trebuie recunoscută."""
    mock = _MockIncompleteMethod()
    assert not isinstance(mock, InflationExpectationsMethod)


def test_method_metadata_valid_tier():
    """MethodMetadata acceptă toate tier-urile valide."""
    for tier in ["highest", "high", "medium", "low", "baseline"]:
        meta = MethodMetadata(
            name="Test",
            source="Test",
            frequency="quarterly",
            accuracy_tier=tier,
            validation_source="test",
            forward_looking=True,
        )
        assert meta.accuracy_tier == tier


def test_method_metadata_invalid_tier():
    """MethodMetadata respinge tier-uri invalide."""
    with pytest.raises(ValidationError):
        MethodMetadata(
            name="Test",
            source="Test",
            frequency="quarterly",
            accuracy_tier="invalid_tier",
            validation_source="test",
            forward_looking=True,
        )


def test_method_metadata_frozen():
    """MethodMetadata e imutabil (frozen)."""
    meta = MethodMetadata(
        name="Test",
        source="Test",
        frequency="quarterly",
        accuracy_tier="high",
        validation_source="test",
        forward_looking=True,
    )
    with pytest.raises(ValidationError):
        meta.name = "Changed"


def test_inflation_expectation_row_valid():
    """InflationExpectationRow validează corect un rând valid."""
    row = InflationExpectationRow(
        date=datetime(2025, 1, 1),
        horizon_years=2.0,
        expected_inflation=2.3,
        method_name="ECB SPF",
    )
    assert row.horizon_years == 2.0
    assert row.expected_inflation == 2.3


def test_inflation_expectation_row_invalid_horizon():
    """InflationExpectationRow respinge horizon_years negativ sau 0."""
    with pytest.raises(ValidationError):
        InflationExpectationRow(
            date=datetime(2025, 1, 1),
            horizon_years=0,
            expected_inflation=2.3,
            method_name="ECB SPF",
        )

    with pytest.raises(ValidationError):
        InflationExpectationRow(
            date=datetime(2025, 1, 1),
            horizon_years=-1,
            expected_inflation=2.3,
            method_name="ECB SPF",
        )
