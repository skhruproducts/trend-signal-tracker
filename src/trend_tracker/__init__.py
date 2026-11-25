"""Deterministic rules for a trend-signal tracker: strength, status, momentum, themes, duplicates."""

from .config import DEFAULT_THRESHOLDS, Thresholds
from .dedupe import Action, MatchKind, compare, normalize_url, triage
from .models import Momentum, Signal, Source, SourceKind, Theme, Trend, TrendStatus
from .serialization import Dataset, load_dataset
from .status import compute_momentum, compute_status, signals_for_trend, unique_stories
from .strength import score_strength
from .themes import check_new_theme

__version__ = "0.1.0"

__all__ = [
    "Action", "DEFAULT_THRESHOLDS", "Dataset", "MatchKind", "Momentum", "Signal", "Source",
    "SourceKind", "Theme", "Thresholds", "Trend", "TrendStatus", "check_new_theme", "compare",
    "compute_momentum", "compute_status", "load_dataset", "normalize_url", "score_strength",
    "signals_for_trend", "triage", "unique_stories",
]
