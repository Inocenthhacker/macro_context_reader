"""
Concept Extractor — PRD-102 (Status: Draft)

Responsabilitate: text + concept_dictionary → vector de indicatori

DECIZII ARHITECTURALE DESCHISE (nu presupune niciuna până la validare empirică):

D1 — METODĂ DE EXTRACȚIE: două abordări rămân deschise, validate empiric pe corpus:
  A) Dictionary matching — caută cuvinte/fraze din concept bucket în text
     Pro: simplu, transparent, zero dependențe ML
     Con: ratează variații lingvistice, fraze complexe
  B) NER cu spaCy EntityRuler — identifică entități multi-cuvânt în context
     Pro: captează "wage pressures", "supply chain constraints" ca unități
     Con: necesită definirea pattern-urilor, overhead spaCy
  C) Hybrid A+B — dictionary pentru frecvență brută, NER pentru entități compuse
  Decizie: TBD empiric pe backtesting vs. USMPD

D2 — DISTRICT WEIGHTS: districte nu sunt egale ca putere predictivă
  Boston Fed (2025): NY și SF mai predictive pentru piețe financiare
  Weights sunt parametri configurabili din YAML, nu hardcodate în cod
  Format: {"new_york": 1.5, "san_francisco": 1.3, "boston": 1.1, ..., "kansas_city": 0.8}
  Decizie: valori concrete calibrate empiric pe corpus

D3 — SUB-TAXONOMIE PER CONCEPT (critic pentru utilitate):
  Nu doar "inflație menționată în N districte" ci NATURA inflației:
  concept INFLATION are sub-tipuri:
    - inflation.wage_driven     ("wage pressures", "labor costs rising")
    - inflation.supply_driven   ("supply chain constraints", "input costs")
    - inflation.energy_driven   ("energy prices", "fuel costs", "utilities")
    - inflation.housing_driven  ("rent increases", "housing costs")
    - inflation.demand_driven   ("strong demand", "consumer spending")
  Același pattern pentru orice concept major (employment, credit, consumer etc.)
  Implicație: output e matrice district × concept × sub_tip, nu district × concept
  Decizie: sub-taxonomia definită în YAML, nu în cod
"""

from __future__ import annotations

from typing import Literal

import pandas as pd

# Tip pentru metodele de extracție — decizie empirică
ExtractionMethod = Literal["dictionary", "ner", "hybrid"]


def compute_concept_frequency(
    text: str,
    concepts: dict[str, list[str]],
    method: ExtractionMethod = "dictionary",
) -> dict[str, float]:
    """
    Calculează frecvența per concept în text.

    Args:
        text: textul brut al unui district dintr-o ediție Beige Book
        concepts: dicționar {concept_name: [keywords/phrases]}
        method: "dictionary" | "ner" | "hybrid" — ales empiric

    Returns:
        {concept_name: frequency_per_1000_words}

    TODO: implementează toate cele 3 metode și compară pe corpus real.
          Nu elimina nicio variantă înainte de validare empirică.
    """
    raise NotImplementedError("TODO: PRD-102")


def compute_concept_subtypes(
    text: str,
    concept: str,
    subtypes: dict[str, list[str]],
    method: ExtractionMethod = "dictionary",
) -> dict[str, float]:
    """
    Pentru un concept dat, identifică natura/sursa lui în text.

    Exemplu pentru concept="inflation":
      subtypes = {
        "wage_driven":    ["wage pressures", "labor costs", "compensation rising"],
        "supply_driven":  ["supply chain", "input costs", "bottleneck"],
        "energy_driven":  ["energy prices", "fuel costs", "utilities"],
        "housing_driven": ["rent increases", "housing costs", "residential"],
        "demand_driven":  ["strong demand", "consumer spending", "robust sales"],
      }

    Returns:
        {"wage_driven": 0.3, "supply_driven": 0.5, "energy_driven": 0.1, ...}
        Valorile reprezintă frecvența relativă a fiecărui sub-tip în text.

    NOTE: acesta e output-ul care face sistemul util — nu "inflație = 0.65" ci
          "inflație: 60% supply-driven, 30% wage-driven, 10% energy-driven"
    TODO: sub-taxonomia completă definită în YAML, nu hardcodată aici.
    """
    raise NotImplementedError("TODO: PRD-102")


def build_indicator_vector(
    texts_by_district: dict[str, str],
    concepts: dict[str, any],
    district_weights: dict[str, float] | None = None,
    method: ExtractionMethod = "dictionary",
) -> pd.DataFrame:
    """
    Construiește vectorul complet de indicatori pentru o ediție Beige Book.

    Args:
        texts_by_district: {district_name: raw_text} pentru o ediție
        concepts: dicționar cu concepte + sub-tipuri (din YAML)
        district_weights: {district_name: weight} — None = pondere egală
                          Default weights din Boston Fed (2025):
                          NY=1.5, SF=1.3, Boston=1.1, ..., Kansas City=0.8
                          TODO: calibrate empiric
        method: metoda de extracție — validată empiric

    Returns:
        pd.DataFrame cu MultiIndex (district, concept, subtype)
        Shape: (n_districts × n_concepts × n_subtypes, 1)

        Exemplu output pentru o ediție:
        district      concept     subtype
        new_york      inflation   wage_driven      0.42  ← ponderat cu 1.5
        new_york      inflation   supply_driven    0.31
        san_francisco inflation   wage_driven      0.18  ← ponderat cu 1.3
        ...

    NOTE: weighted output = frequency × district_weight
          aggregarea națională = suma ponderată, nu medie simplă
    """
    raise NotImplementedError("TODO: PRD-102")


def aggregate_national(
    district_df: pd.DataFrame,
    district_weights: dict[str, float],
) -> pd.DataFrame:
    """
    Agregă vectorul district-level la nivel național PONDERAT.

    IMPORTANT: nu calculezi media simplă — aplici district_weights.
    Output național = suma(frequency_district × weight_district) / suma(weights)

    Returns:
        pd.DataFrame cu Index (concept, subtype) — nivel național agregat ponderat
    """
    raise NotImplementedError("TODO: PRD-102")
