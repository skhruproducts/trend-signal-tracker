"""Trend status and momentum.

Status
    Watching       1-4 unique stories
    Strengthening  5+ stories AND 4+ players AND 2+ sectors or audiences
                   AND an evidence span of 7+ days
    Confirmed / Fading are set by people and never overwritten.
    Zero stories: keep the current status and flag insufficient evidence.

Momentum
    Rising           3+ newly observed stories in the trailing 7 days
    Below threshold  otherwise
    Falling is set by people and never overwritten.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

from .config import DEFAULT_THRESHOLDS, Thresholds
from .models import Momentum, Signal, Theme, TrendStatus

LOCKED_STATUSES = frozenset({TrendStatus.CONFIRMED, TrendStatus.FADING})
LOCKED_MOMENTUM = frozenset({Momentum.FALLING})


def _key(signal: Signal) -> str:
    return signal.story_key.strip().casefold() or f"id:{signal.id}"


def unique_stories(signals: Iterable[Signal]) -> list[Signal]:
    """One entry per story, keeping the earliest-seen row for each story key."""
    stories: dict[str, Signal] = {}
    for signal in signals:
        key = _key(signal)
        if key not in stories or signal.first_seen < stories[key].first_seen:
            stories[key] = signal
    return list(stories.values())


def signals_for_trend(trend_id: str, themes: Iterable[Theme], signals: Iterable[Signal]) -> list[Signal]:
    """Signals that reach a trend through its themes (the Notion rollup)."""
    theme_ids = {t.id for t in themes if t.trend_id == trend_id}
    return [s for s in signals if s.theme_id in theme_ids]


def _distinct(values: Iterable[str]) -> int:
    return len({" ".join(v.casefold().split()) for v in values if v.strip()})


@dataclass(frozen=True)
class StatusResult:
    status: TrendStatus
    previous: TrendStatus
    computed: TrendStatus | None
    stories: int
    players: int
    sectors: int
    audiences: int
    span_days: int
    failed_tests: tuple[str, ...]
    note: str

    @property
    def changed(self) -> bool:
        return self.status is not self.previous

    def calculation(self, as_of: date) -> str:
        """One line for the trend's status-calculation field."""
        return (
            f"{as_of.isoformat()}: {self.stories} stories, {self.players} players, "
            f"{self.sectors} sectors, {self.audiences} audiences, span {self.span_days}d "
            f"-> {self.status.value}. {self.note}"
        ).strip()


def compute_status(
    current: TrendStatus,
    signals: Iterable[Signal],
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
) -> StatusResult:
    stories = unique_stories(signals)
    players = _distinct(p for s in stories for p in s.players)
    sectors = _distinct(x for s in stories for x in s.sectors)
    audiences = _distinct(x for s in stories for x in s.audiences)
    dates = [s.event_date for s in stories]
    span = (max(dates) - min(dates)).days if dates else 0

    def result(status, computed, failed, note):
        return StatusResult(status, current, computed, len(stories), players, sectors,
                            audiences, span, tuple(failed), note)

    if not stories:
        return result(current, None, ["no linked stories"],
                      "Insufficient evidence: status kept.")

    failed: list[str] = []
    if len(stories) < thresholds.strengthening_min_stories:
        failed.append(f"stories {len(stories)} < {thresholds.strengthening_min_stories}")
    else:
        if players < thresholds.strengthening_min_players:
            failed.append(f"players {players} < {thresholds.strengthening_min_players}")
        if max(sectors, audiences) < thresholds.strengthening_min_sectors_or_audiences:
            failed.append(
                f"sectors/audiences {max(sectors, audiences)} < "
                f"{thresholds.strengthening_min_sectors_or_audiences}"
            )
        if span < thresholds.strengthening_min_span_days:
            failed.append(f"span {span}d < {thresholds.strengthening_min_span_days}d")

    computed = TrendStatus.WATCHING if failed else TrendStatus.STRENGTHENING

    if current in LOCKED_STATUSES:
        note = f"Set by a person and kept; rules alone would give {computed.value}."
        return result(current, computed, failed, note)

    note = "" if not failed else "Failing: " + "; ".join(failed) + "."
    return result(computed, computed, failed, note)


@dataclass(frozen=True)
class MomentumResult:
    momentum: Momentum
    previous: Momentum
    computed: Momentum
    new_stories: int
    window_start: date
    as_of: date
    note: str

    @property
    def changed(self) -> bool:
        return self.momentum is not self.previous


def compute_momentum(
    current: Momentum,
    signals: Iterable[Signal],
    as_of: date,
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
) -> MomentumResult:
    window_start = as_of - timedelta(days=thresholds.rising_window_days)
    new = [s for s in unique_stories(signals) if window_start < s.first_seen <= as_of]
    computed = (
        Momentum.RISING if len(new) >= thresholds.rising_min_new_stories else Momentum.BELOW_THRESHOLD
    )

    if current in LOCKED_MOMENTUM:
        note = f"Set by a person and kept; rules alone would give {computed.value}."
        return MomentumResult(current, current, computed, len(new), window_start, as_of, note)

    note = f"{len(new)} new stories since {window_start.isoformat()}."
    return MomentumResult(computed, current, computed, len(new), window_start, as_of, note)
