"""Run every rule over the sample dataset and print what a daily run would report.

    python examples/run_demo.py [--as-of 2026-11-25]
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from trend_tracker import (
    check_new_theme,
    compute_momentum,
    compute_status,
    load_dataset,
    score_strength,
    signals_for_trend,
    triage,
)

HERE = Path(__file__).parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=HERE / "sample_dataset.json")
    parser.add_argument("--as-of", default="2026-11-25", type=date.fromisoformat)
    args = parser.parse_args()

    data = load_dataset(args.data)

    print("SIGNAL STRENGTH")
    for s in data.signals:
        r = score_strength(s)
        print(f"  {s.id:<4} {r}  {r.independent_sources} indep.  {r.reason}")

    print("\nINCOMING: DUPLICATE TRIAGE")
    for s in data.incoming:
        t = triage(s, data.signals)
        detail = "; ".join(f"{m.existing_id}: {', '.join(m.reasons)}" for m in t.matches) or "no match"
        print(f"  {s.id:<4} {t.action.value:<7} {detail}")

    print(f"\nTRENDS (as of {args.as_of})")
    for trend in data.trends:
        linked = signals_for_trend(trend.id, data.themes, data.signals)
        st = compute_status(trend.status, linked)
        mo = compute_momentum(trend.momentum, linked, args.as_of)
        arrow = lambda old, new: f"{old.value} -> {new.value}" if old is not new else f"{new.value} (no change)"
        print(f"  {trend.name}")
        print(f"    status:   {arrow(st.previous, st.status)}")
        print(f"    momentum: {arrow(mo.previous, mo.momentum)}  {mo.note}")
        print(f"    calc:     {st.calculation(args.as_of)}")

    unsorted = [s for s in data.signals if s.theme_id is None]
    print(f"\nUNSORTED SIGNALS: {len(unsorted)}")
    check = check_new_theme(unsorted)
    print(f"  Could they form a new theme? {'yes' if check.ok else 'no'} - {check.reason}")


if __name__ == "__main__":
    main()
