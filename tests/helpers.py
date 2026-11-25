from __future__ import annotations

from datetime import date, timedelta
from itertools import count

from trend_tracker import Signal, Source, SourceKind

_ids = count(1)
BASE = date(2026, 11, 1)


def src(origin: str, *, primary: bool = False, quant: bool = False, markets=(), period_days=None) -> Source:
    return Source(
        name=f"{origin} page",
        url=f"https://{origin.lower().replace(' ', '')}.example.com",
        origin=origin,
        kind=SourceKind.PRIMARY if primary else SourceKind.SECONDARY,
        quantitative=quant,
        markets=tuple(markets),
        period_days=period_days,
    )


def sig(
    *,
    day: int = 0,
    seen: int | None = None,
    key: str | None = None,
    players=("Brand A",),
    sectors=("fashion",),
    audiences=(),
    title: str | None = None,
    url: str | None = None,
    sources=None,
    theme_id: str | None = "TH1",
) -> Signal:
    n = next(_ids)
    return Signal(
        id=f"S{n}",
        title=title or f"Story number {n} about something specific",
        url=url if url is not None else f"https://news.example.org/story-{n}",
        event_date=BASE + timedelta(days=day),
        first_seen=BASE + timedelta(days=seen if seen is not None else day),
        story_key=key if key is not None else f"story-{n}",
        players=tuple(players),
        sectors=tuple(sectors),
        audiences=tuple(audiences),
        sources=tuple(sources) if sources is not None else (src("Outlet"),),
        theme_id=theme_id,
    )
