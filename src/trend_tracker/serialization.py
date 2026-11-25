"""Load a dataset of trends, themes and signals from JSON."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from .models import Momentum, Signal, Source, SourceKind, Theme, Trend, TrendStatus


@dataclass
class Dataset:
    trends: list[Trend] = field(default_factory=list)
    themes: list[Theme] = field(default_factory=list)
    signals: list[Signal] = field(default_factory=list)
    incoming: list[Signal] = field(default_factory=list)


def source_from_dict(d: dict[str, Any]) -> Source:
    return Source(
        name=d["name"],
        url=d.get("url", ""),
        origin=d["origin"],
        kind=SourceKind(d.get("kind", "secondary")),
        quantitative=bool(d.get("quantitative", False)),
        markets=tuple(d.get("markets", ())),
        period_days=d.get("period_days"),
    )


def signal_from_dict(d: dict[str, Any]) -> Signal:
    return Signal(
        id=d["id"],
        title=d["title"],
        url=d.get("url", ""),
        event_date=date.fromisoformat(d["event_date"]),
        first_seen=date.fromisoformat(d["first_seen"]),
        story_key=d.get("story_key", ""),
        players=tuple(d.get("players", ())),
        sectors=tuple(d.get("sectors", ())),
        audiences=tuple(d.get("audiences", ())),
        markets=tuple(d.get("markets", ())),
        sources=tuple(source_from_dict(s) for s in d.get("sources", ())),
        theme_id=d.get("theme_id"),
    )


def load_dataset(path: str | Path) -> Dataset:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return Dataset(
        trends=[
            Trend(t["id"], t["name"], TrendStatus(t.get("status", "watching")),
                  Momentum(t.get("momentum", "below_threshold")))
            for t in raw.get("trends", ())
        ],
        themes=[Theme(t["id"], t["name"], t.get("trend_id")) for t in raw.get("themes", ())],
        signals=[signal_from_dict(s) for s in raw.get("signals", ())],
        incoming=[signal_from_dict(s) for s in raw.get("incoming", ())],
    )
