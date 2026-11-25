"""Core records: sources, signals, themes and trends."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum


class SourceKind(str, Enum):
    PRIMARY = "primary"  # the brand, platform, dataset or retailer itself
    SECONDARY = "secondary"  # reporting or commentary about it


class TrendStatus(str, Enum):
    WATCHING = "watching"
    STRENGTHENING = "strengthening"
    CONFIRMED = "confirmed"  # set by a person only
    FADING = "fading"  # set by a person only


class Momentum(str, Enum):
    RISING = "rising"
    BELOW_THRESHOLD = "below_threshold"
    FALLING = "falling"  # set by a person only


@dataclass(frozen=True)
class Source:
    """One piece of evidence for a signal.

    ``origin`` identifies who produced the information. Two articles that
    repeat the same press release share an origin, so they count as one
    independent source.
    """

    name: str
    url: str
    origin: str
    kind: SourceKind = SourceKind.SECONDARY
    quantitative: bool = False  # e.g. Pinterest Trends, Google Trends, first-party data
    markets: tuple[str, ...] = ()
    period_days: int | None = None  # length of the period a quantitative source covers

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Source.name is required")
        if not self.origin.strip():
            raise ValueError(f"Source {self.name!r} needs an origin to judge independence")


@dataclass(frozen=True)
class Signal:
    """One specific, observable change. One story = one signal."""

    id: str
    title: str
    url: str
    event_date: date
    first_seen: date
    story_key: str = ""
    players: tuple[str, ...] = ()
    sectors: tuple[str, ...] = ()
    audiences: tuple[str, ...] = ()
    markets: tuple[str, ...] = ()
    sources: tuple[Source, ...] = ()
    theme_id: str | None = None


@dataclass(frozen=True)
class Theme:
    """A pattern shared by several signals from several players."""

    id: str
    name: str
    trend_id: str | None = None


@dataclass(frozen=True)
class Trend:
    """A cross-sector shift in what people want or do. Created by people, not the agent."""

    id: str
    name: str
    status: TrendStatus = TrendStatus.WATCHING
    momentum: Momentum = Momentum.BELOW_THRESHOLD
