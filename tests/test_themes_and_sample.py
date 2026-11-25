from datetime import date
from pathlib import Path

from trend_tracker import (
    Action,
    Momentum,
    TrendStatus,
    check_new_theme,
    compute_momentum,
    compute_status,
    load_dataset,
    score_strength,
    signals_for_trend,
    triage,
)
from helpers import sig

SAMPLE = Path(__file__).parent.parent / "examples" / "sample_dataset.json"


def test_theme_needs_three_stories_from_three_players():
    assert check_new_theme([sig(players=["A"]), sig(players=["B"]), sig(players=["C"])]).ok


def test_theme_rejected_when_one_player_drives_it():
    check = check_new_theme([sig(players=["A"]), sig(players=["A"]), sig(players=["A"])])
    assert not check.ok
    assert "1 players" in check.reason


def test_theme_rejected_with_two_stories():
    assert not check_new_theme([sig(players=["A"]), sig(players=["B", "C"])]).ok


# --- the sample dataset behaves as documented in the README ---------------

def test_sample_dataset():
    data = load_dataset(SAMPLE)
    stars = {s.id: score_strength(s).stars for s in data.signals}
    assert [stars[i] for i in ("S1", "S2", "S3", "S4", "S5", "S6")] == [1, 2, 2, 3, 4, 5]

    actions = {s.id: triage(s, data.signals).action for s in data.incoming}
    assert actions == {"N1": Action.UPDATE, "N2": Action.FLAG, "N3": Action.CREATE}

    as_of = date(2026, 11, 25)
    by_id = {t.id: t for t in data.trends}
    t1 = signals_for_trend("T1", data.themes, data.signals)
    assert compute_status(by_id["T1"].status, t1).status is TrendStatus.STRENGTHENING
    assert compute_momentum(by_id["T1"].momentum, t1, as_of).momentum is Momentum.RISING

    t2 = signals_for_trend("T2", data.themes, data.signals)
    assert compute_status(by_id["T2"].status, t2).status is TrendStatus.WATCHING

    t3 = signals_for_trend("T3", data.themes, data.signals)
    assert compute_status(by_id["T3"].status, t3).status is TrendStatus.CONFIRMED
