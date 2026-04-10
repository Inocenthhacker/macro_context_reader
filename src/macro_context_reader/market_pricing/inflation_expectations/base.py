"""Protocol comun pentru toate metodele de inflation expectations.

Orice metodă nouă (PRD-203 OATei, PRD-204 DNS, etc.) trebuie să implementeze
acest Protocol fără excepție. Asta garantează pluggability în real_rate_diff.py.

Refs: PRD-200 CC-1, research/INFLATION_EXPECTATIONS_METHODS.md Secțiunea 13
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

import pandas as pd

from macro_context_reader.market_pricing.schemas import MethodMetadata


@runtime_checkable
class InflationExpectationsMethod(Protocol):
    """Protocol pentru orice sursă de EUR inflation expectations.

    Implementări trebuie să fie stateless sau să gestioneze propriul state
    intern fără side-effects globale.

    Output-ul fetch() trebuie să fie un DataFrame cu coloanele:
    - date (datetime64[ns])
    - expected_inflation (float, în procente)
    - horizon_years (float)
    Coloane suplimentare permise dar nu obligatorii.
    """

    @property
    def name(self) -> str:
        """Numele unic al metodei, ex: 'ECB SPF 2Y'."""
        ...

    @property
    def frequency(self) -> str:
        """Frecvența publicării: 'daily', 'weekly', 'monthly', 'quarterly'."""
        ...

    @property
    def source(self) -> str:
        """Sursa datelor, ex: 'ECB Data Portal'."""
        ...

    def fetch(self, start: datetime, end: datetime) -> pd.DataFrame:
        """Descarcă observațiile între start și end (inclusiv).

        Returns:
            DataFrame cu coloane: date, expected_inflation, horizon_years
            (plus alte coloane opționale specifice metodei)
        """
        ...

    def get_at_date(self, date: datetime, horizon_years: float = 2.0) -> float:
        """Returnează expected inflation la data și orizontul dat.

        Dacă data exactă nu există în dataset, interpolează cu forward-fill
        de la cea mai apropiată observație anterioară.

        Args:
            date: Data pentru care vrem expected inflation
            horizon_years: Orizontul în ani (default 2.0)

        Returns:
            Inflația așteptată în procente (2.5 = 2.5%)

        Raises:
            ValueError: dacă nicio observație nu există înaintea datei
        """
        ...

    def get_metadata(self) -> MethodMetadata:
        """Returnează metadata metodei pentru propagare în real_rate_diff."""
        ...
