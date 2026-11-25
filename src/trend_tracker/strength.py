"""Signal strength (1-5 stars).

Strength measures how well *one story* is corroborated. It does not measure
how widespread a trend is.

    1  one traceable source
    2  two independent sources
    3  three or more independent sources, including primary evidence
    4  3 stars plus quantitative primary data
    5  4 stars where that data spans 2+ markets or a sustained period
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .config import DEFAULT_THRESHOLDS, Thresholds
from .models import Signal, Source, SourceKind


@dataclass(frozen=True)
class StrengthResult:
    stars: int
    independent_sources: int
    reason: str

    def __str__(self) -> str:
        return "★" * self.stars + "☆" * (5 - self.stars)


def _origin_key(source: Source) -> str:
    return " ".join(source.origin.casefold().split())


def group_by_origin(sources: Iterable[Source]) -> dict[str, list[Source]]:
    """Group sources that share an origin (syndication, one press release)."""
    groups: dict[str, list[Source]] = {}
    for source in sources:
        groups.setdefault(_origin_key(source), []).append(source)
    return groups


def is_primary(source: Source) -> bool:
    return source.kind is SourceKind.PRIMARY or source.quantitative


def score_strength(
    signal_or_sources: Signal | Iterable[Source],
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
) -> StrengthResult:
    if isinstance(signal_or_sources, Signal):
        sources = tuple(signal_or_sources.sources)
    else:
        sources = tuple(signal_or_sources)
    if not sources:
        raise ValueError("A signal needs at least one traceable source")

    n = len(group_by_origin(sources))

    if n == 1:
        return StrengthResult(1, n, "One traceable source.")

    if n == 2:
        return StrengthResult(2, n, "Two independent sources.")

    if not any(is_primary(s) for s in sources):
        return StrengthResult(
            2, n, f"{n} independent sources but no primary evidence, so capped at 2 stars."
        )

    quantitative = [s for s in sources if s.quantitative]
    if not quantitative:
        return StrengthResult(3, n, f"{n} independent sources including primary evidence.")

    markets = {m.casefold() for s in quantitative for m in s.markets}
    sustained = any((s.period_days or 0) >= thresholds.sustained_period_days for s in quantitative)

    if len(markets) >= 2 or sustained:
        detail = []
        if len(markets) >= 2:
            detail.append(f"{len(markets)} markets")
        if sustained:
            detail.append(f"a period of {thresholds.sustained_period_days}+ days")
        return StrengthResult(5, n, "Quantitative primary data covering " + " and ".join(detail) + ".")

    return StrengthResult(4, n, "Quantitative primary data in one market over a short period.")
