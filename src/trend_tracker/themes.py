"""When a group of signals may become a new theme."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .config import DEFAULT_THRESHOLDS, Thresholds
from .models import Signal
from .status import unique_stories


@dataclass(frozen=True)
class ThemeCheck:
    ok: bool
    stories: int
    players: int
    reason: str


def check_new_theme(signals: Iterable[Signal], thresholds: Thresholds = DEFAULT_THRESHOLDS) -> ThemeCheck:
    """A theme needs 3+ separate stories from 3+ different brands, people or institutions.

    This only checks the evidence count. Whether an existing theme (or a synonym)
    already covers the pattern is a judgement call made before calling this.
    """
    stories = unique_stories(signals)
    players = {" ".join(p.casefold().split()) for s in stories for p in s.players if p.strip()}
    problems = []
    if len(stories) < thresholds.theme_min_stories:
        problems.append(f"{len(stories)} stories (need {thresholds.theme_min_stories})")
    if len(players) < thresholds.theme_min_players:
        problems.append(f"{len(players)} players (need {thresholds.theme_min_players})")
    if problems:
        return ThemeCheck(False, len(stories), len(players), "Not enough evidence: " + ", ".join(problems) + ".")
    return ThemeCheck(True, len(stories), len(players), "Enough separate stories and players.")
