"""CME FedWatch probabilities module — PRD-202."""
from .loader import (
    build_master_dataset,
    list_available_snapshots,
    load_all_snapshots,
    load_fedwatch_history,
)
from .parser import get_snapshot_metadata, parse_fedwatch_csv
from .schemas import FedWatchRow, FedWatchSnapshot
from .surprise import (
    DEFAULT_NLP_CALIBRATION_BPS,
    SurpriseMethod,
    compute_surprise_signal,
    compute_surprise_timeseries,
)
from .synthetic import build_mpt_dataset, load_mpt_history

__all__ = [
    "parse_fedwatch_csv",
    "get_snapshot_metadata",
    "list_available_snapshots",
    "load_all_snapshots",
    "build_master_dataset",
    "load_fedwatch_history",
    "compute_surprise_signal",
    "compute_surprise_timeseries",
    "SurpriseMethod",
    "DEFAULT_NLP_CALIBRATION_BPS",
    "FedWatchRow",
    "FedWatchSnapshot",
    "build_mpt_dataset",
    "load_mpt_history",
]
