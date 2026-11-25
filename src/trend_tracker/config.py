"""Tunable thresholds. Defaults follow docs/METHODOLOGY.md."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Thresholds:
    # Trend status
    strengthening_min_stories: int = 5
    strengthening_min_players: int = 4
    strengthening_min_sectors_or_audiences: int = 2
    strengthening_min_span_days: int = 7

    # Trend momentum
    rising_min_new_stories: int = 3
    rising_window_days: int = 7

    # Signal strength: a quantitative source covering this many days counts as "sustained"
    sustained_period_days: int = 56

    # Theme creation
    theme_min_stories: int = 3
    theme_min_players: int = 3

    # Duplicate detection
    duplicate_max_day_gap: int = 3
    duplicate_title_similarity: float = 0.6
    duplicate_title_only_similarity: float = 0.95


DEFAULT_THRESHOLDS = Thresholds()
