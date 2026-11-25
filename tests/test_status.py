from datetime import date

from trend_tracker import (
    Momentum,
    Theme,
    Thresholds,
    TrendStatus,
    compute_momentum,
    compute_status,
    signals_for_trend,
    unique_stories,
)
from helpers import BASE, sig


def strong_set():
    """5 stories, 4 players, 2 sectors, 10-day span: passes every Strengthening test."""
    return [
        sig(day=0, players=["A"], sectors=["fashion"]),
        sig(day=2, players=["B"], sectors=["fashion"]),
        sig(day=4, players=["C"], sectors=["styling"]),
        sig(day=7, players=["D"], sectors=["fashion"]),
        sig(day=10, players=["A"], sectors=["styling"]),
    ]


# --- status ---------------------------------------------------------------

def test_one_to_four_stories_is_watching():
    result = compute_status(TrendStatus.WATCHING, strong_set()[:4])
    assert result.status is TrendStatus.WATCHING
    assert result.failed_tests == ("stories 4 < 5",)


def test_all_tests_pass_is_strengthening():
    result = compute_status(TrendStatus.WATCHING, strong_set())
    assert result.status is TrendStatus.STRENGTHENING
    assert result.changed
    assert result.failed_tests == ()


def test_five_stories_but_too_few_players_stays_watching_and_says_why():
    signals = [sig(day=d, players=["A"], sectors=["fashion", "styling"]) for d in (0, 3, 6, 9, 12)]
    result = compute_status(TrendStatus.WATCHING, signals)
    assert result.status is TrendStatus.WATCHING
    assert result.failed_tests == ("players 1 < 4",)


def test_audiences_can_replace_sectors_for_breadth():
    signals = [
        sig(day=0, players=["A"], audiences=["premium 25+"]),
        sig(day=2, players=["B"], audiences=["young high spenders"]),
        sig(day=4, players=["C"]),
        sig(day=6, players=["D"]),
        sig(day=8, players=["E"]),
    ]
    assert compute_status(TrendStatus.WATCHING, signals).status is TrendStatus.STRENGTHENING


def test_short_evidence_span_stays_watching():
    signals = [sig(day=d, players=[p], sectors=[s]) for d, p, s in
               [(0, "A", "fashion"), (1, "B", "styling"), (2, "C", "fashion"), (3, "D", "fashion"), (4, "E", "fashion")]]
    result = compute_status(TrendStatus.WATCHING, signals)
    assert result.status is TrendStatus.WATCHING
    assert result.failed_tests == ("span 4d < 7d",)


def test_rows_with_the_same_story_key_count_once():
    base = strong_set()
    dup = sig(day=12, key=base[0].story_key, players=["Z"])
    result = compute_status(TrendStatus.WATCHING, base[:4] + [dup])
    assert result.stories == 4


def test_zero_stories_keeps_status_and_flags():
    result = compute_status(TrendStatus.STRENGTHENING, [])
    assert result.status is TrendStatus.STRENGTHENING
    assert "Insufficient evidence" in result.note


def test_human_set_confirmed_is_never_overwritten():
    result = compute_status(TrendStatus.CONFIRMED, strong_set()[:2])
    assert result.status is TrendStatus.CONFIRMED
    assert result.computed is TrendStatus.WATCHING
    assert "Set by a person" in result.note


def test_human_set_fading_is_never_overwritten():
    result = compute_status(TrendStatus.FADING, strong_set())
    assert result.status is TrendStatus.FADING
    assert result.computed is TrendStatus.STRENGTHENING


def test_thresholds_are_tunable():
    loose = Thresholds(strengthening_min_stories=2, strengthening_min_players=2,
                       strengthening_min_sectors_or_audiences=1, strengthening_min_span_days=1)
    assert compute_status(TrendStatus.WATCHING, strong_set()[:2], loose).status is TrendStatus.STRENGTHENING


def test_calculation_line():
    line = compute_status(TrendStatus.WATCHING, strong_set()).calculation(date(2026, 11, 25))
    assert line.startswith("2026-11-25: 5 stories, 4 players, 2 sectors")
    assert "-> strengthening" in line


# --- momentum -------------------------------------------------------------

AS_OF = date(2026, 11, 15)  # BASE + 14 days; window is Nov 8 (exclusive) to Nov 15


def test_three_new_stories_in_window_is_rising():
    signals = [sig(seen=d) for d in (8, 10, 12, 14)]  # day 8 = Nov 9, inside the window
    result = compute_momentum(Momentum.BELOW_THRESHOLD, signals, AS_OF)
    assert result.momentum is Momentum.RISING
    assert result.new_stories == 4


def test_window_start_is_exclusive_and_end_inclusive():
    signals = [sig(seen=7), sig(seen=10), sig(seen=14)]  # Nov 8 is outside, Nov 15 inside
    result = compute_momentum(Momentum.BELOW_THRESHOLD, signals, AS_OF)
    assert result.new_stories == 2
    assert result.momentum is Momentum.BELOW_THRESHOLD


def test_future_first_seen_is_ignored():
    signals = [sig(seen=10), sig(seen=12), sig(seen=20)]
    assert compute_momentum(Momentum.RISING, signals, AS_OF).momentum is Momentum.BELOW_THRESHOLD


def test_falling_is_human_only_and_kept():
    signals = [sig(seen=d) for d in (9, 10, 11)]
    result = compute_momentum(Momentum.FALLING, signals, AS_OF)
    assert result.momentum is Momentum.FALLING
    assert result.computed is Momentum.RISING


def test_story_counted_by_earliest_first_seen():
    old = sig(seen=1, key="same")
    follow_up = sig(seen=12, key="same")
    assert unique_stories([follow_up, old])[0].first_seen == BASE.replace(day=2)
    assert compute_momentum(Momentum.BELOW_THRESHOLD, [old, follow_up], AS_OF).new_stories == 0


# --- rollup ---------------------------------------------------------------

def test_signals_reach_a_trend_through_its_themes():
    themes = [Theme("TH1", "a", "T1"), Theme("TH2", "b", "T1"), Theme("TH3", "c", "T2")]
    s1, s2, s3, s4 = sig(theme_id="TH1"), sig(theme_id="TH2"), sig(theme_id="TH3"), sig(theme_id=None)
    assert signals_for_trend("T1", themes, [s1, s2, s3, s4]) == [s1, s2]
