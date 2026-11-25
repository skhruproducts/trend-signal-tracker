"""Duplicate detection: one story = one row.

    same story  -> update the existing row (add a dated evidence note)
    possible    -> flag for a person; do not create a new row
    different   -> create a new row
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import Enum
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .config import DEFAULT_THRESHOLDS, Thresholds
from .models import Signal

TRACKING_PARAMS = {"fbclid", "gclid", "igshid", "mc_cid", "mc_eid", "ref", "ref_src", "si"}


def normalize_url(url: str) -> str:
    """Lowercase the host, drop www, tracking parameters, fragments and trailing slashes."""
    parts = urlsplit(url.strip())
    host = parts.netloc.casefold().removeprefix("www.")
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.casefold().startswith("utm_") and k.casefold() not in TRACKING_PARAMS
    ]
    path = parts.path.rstrip("/") or ""
    return urlunsplit(("https", host, path, urlencode(sorted(query)), ""))


def normalize_title(title: str) -> str:
    """Casefold, strip accents and punctuation. Works for Latin and Cyrillic scripts."""
    text = unicodedata.normalize("NFKD", title.casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_title(a), normalize_title(b)).ratio()


class MatchKind(str, Enum):
    SAME_STORY = "same_story"
    POSSIBLE = "possible"
    DIFFERENT = "different"


@dataclass(frozen=True)
class Match:
    kind: MatchKind
    existing_id: str
    reasons: tuple[str, ...]


def compare(candidate: Signal, existing: Signal, thresholds: Thresholds = DEFAULT_THRESHOLDS) -> Match:
    reasons: list[str] = []

    if candidate.url and existing.url and normalize_url(candidate.url) == normalize_url(existing.url):
        reasons.append("same URL")
    ck, ek = candidate.story_key.strip().casefold(), existing.story_key.strip().casefold()
    if ck and ck == ek:
        reasons.append("same story key")
    if reasons:
        return Match(MatchKind.SAME_STORY, existing.id, tuple(reasons))

    similarity = title_similarity(candidate.title, existing.title)
    shared = {p.casefold() for p in candidate.players} & {p.casefold() for p in existing.players}
    close_dates = abs((candidate.event_date - existing.event_date).days) <= thresholds.duplicate_max_day_gap

    if shared and close_dates and similarity >= thresholds.duplicate_title_similarity:
        reasons.append(f"shared players {sorted(shared)}, dates within "
                       f"{thresholds.duplicate_max_day_gap}d, title similarity {similarity:.2f}")
    elif similarity >= thresholds.duplicate_title_only_similarity:
        reasons.append(f"near-identical title ({similarity:.2f})")

    if reasons:
        return Match(MatchKind.POSSIBLE, existing.id, tuple(reasons))
    return Match(MatchKind.DIFFERENT, existing.id, ())


class Action(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    FLAG = "flag"


@dataclass(frozen=True)
class Triage:
    action: Action
    matches: tuple[Match, ...]

    @property
    def target_id(self) -> str | None:
        return self.matches[0].existing_id if self.action is Action.UPDATE else None


def triage(candidate: Signal, existing: Iterable[Signal], thresholds: Thresholds = DEFAULT_THRESHOLDS) -> Triage:
    matches = [m for e in existing if (m := compare(candidate, e, thresholds)).kind is not MatchKind.DIFFERENT]
    same = [m for m in matches if m.kind is MatchKind.SAME_STORY]
    if len({m.existing_id for m in same}) == 1:
        return Triage(Action.UPDATE, tuple(same))
    if matches:  # possible matches, or several rows claim to be the same story
        return Triage(Action.FLAG, tuple(matches))
    return Triage(Action.CREATE, ())
