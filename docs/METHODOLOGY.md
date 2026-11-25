# Methodology

A trend tracker for a consumer brand, built so that an AI agent can run it every day and a person can still trust the output. This document describes the method. The code in `src/trend_tracker` implements the parts that have to be exact.

## 1. Three layers

| Layer | What it is | Who creates it |
|---|---|---|
| **Signal** | One specific, observable change: what changed, who, where, when, and the evidence. One story = one row. | The agent |
| **Theme** | A pattern shared by 3+ separate signals from 3+ different brands, people or institutions. | The agent, after checking that no existing theme (or synonym) already covers it |
| **Trend** | A shift in what people want or do that reaches beyond one industry. | People only. The agent can propose one. |

A fashion aesthetic can be a theme. It is not automatically a trend.

A fourth layer, **opportunities**, links the strongest signals to concrete tests for the brand: content, search, merchandising, landing pages, customer research. Each one has a horizon, a validation metric and a review date. Opportunities are brand-specific and are not part of this repository.

## 2. What counts as a signal

A signal documents a change, not a topic. "Trench coats are popular" is not a signal. "Brand X launched an unlined trench for spring and autumn on 3 November" is.

Every signal keeps three things apart:

- **Observation:** what the source shows.
- **Interpretation:** why it matters for the brand.
- **Hypothesis:** what might follow. This lives on the trend or the opportunity, never on the signal.

Evidence rules:

- Launches and collections are supply-side evidence. They show what brands are betting on, not what people want.
- Editorial repetition alone does not prove demand.
- For any number, keep the metric, geography, period, comparison and method.
- Never treat saves, searches, views and sales as the same thing.
- Separately normalised indices (e.g. two search-interest charts) are not market size and can't be compared as volumes.
- Record the geography a platform tool actually returned. A search term in Polish doesn't make the data Poland-only.
- Flag seasonality, small samples and paid promotion.
- If a source is paywalled, unavailable or stale, say so. Don't infer its content from a headline.
- Log fewer signals, or none, when evidence is thin. Never fill a quota with general news.

## 3. Strength (1–5 stars)

Strength measures how well **this story** is corroborated. It says nothing about how big the trend is.

| Stars | Rule |
|---|---|
| ★ | One traceable source |
| ★★ | Two independent sources |
| ★★★ | Three or more independent sources, including primary evidence (the brand, platform, retailer or dataset itself) |
| ★★★★ | ★★★ plus quantitative primary data (platform trends tools, search data, first-party analytics) |
| ★★★★★ | ★★★★ where that data covers 2+ markets or a sustained period (default 56+ days) |

**Independence:** sources are grouped by *origin*, meaning who produced the information. Ten articles that rewrite one press release share one origin. Syndicated copies are not corroboration.

Confidence is kept separate from coverage volume: a story can be widely covered and still uncertain.

Code: `score_strength()` in `strength.py`.

## 4. Duplicates

One story = one row. Before writing, every incoming signal is compared to existing ones:

| Result | When | Action |
|---|---|---|
| Same story | Same URL (after removing tracking parameters, `www`, trailing slashes) or same story key | Update the existing row with a dated evidence note |
| Possible match | Shared player, event dates within 3 days and similar titles, or near-identical titles | Flag for a person. Don't create a new row. |
| Different | Anything else | Create a new row |

If several existing rows claim to be the same story, the candidate is flagged instead of merged. Only clear duplicates are merged automatically.

Code: `triage()` in `dedupe.py`.

## 5. Proposing a trend

The agent never creates a trend. It may propose one when all four tests pass:

1. It is a shift in what people want or do, beyond one industry.
2. There is evidence in 2+ sectors.
3. The direction holds beyond one news cycle.
4. There is a clear human need behind it.

A proposal includes supporting evidence, contradicting evidence, and what would disprove it.

## 6. Status

Count **unique stories** across all the themes linked to a trend.

| Status | Rule |
|---|---|
| Watching | 1–4 stories |
| Strengthening | 5+ stories **and** 4+ players **and** 2+ sectors or audiences **and** an evidence span of 7+ days |
| Confirmed / Fading | Set by a person. Never overwritten; the agent may suggest a change. |

If a trend has 5+ stories but fails another test, it stays Watching and the run says which test failed. If it has zero linked stories, its status is kept and the run flags insufficient evidence.

Code: `compute_status()` in `status.py`.

## 7. Momentum

| Momentum | Rule |
|---|---|
| Rising | 3+ newly observed stories in the trailing 7 days |
| Below threshold | Otherwise |
| Falling | Set by a person only |

"Newly observed" uses the date a story was first seen. Follow-ups to an old story don't count as new.

Each run records the counts and calculation date on the trend, so anyone can check the result.

Code: `compute_momentum()` in `status.py`.

## 8. Daily run

1. Read the configuration: existing tags, relations, thresholds. Use only existing options; propose taxonomy changes instead of making them.
2. Cover the time since the last successful run, per source. Advance a source's checkpoint only after its records are saved. Retry failed sources without writing duplicates.
3. Collect and classify signals; triage each one for duplicates.
4. Update themes, then trend status and momentum.
5. Create or update opportunities for the strongest relevant signals.
6. Write a digest: the main developments, new and updated signals, merged duplicates, status changes with counts, proposals awaiting approval, the number of unsorted signals, access failures, and the coverage window. Keep what was saved separate from what is only proposed.

## Why some of this is code

An LLM is good at reading sources, judging relevance and writing interpretation. It is unreliable at counting distinct players across twelve rows or applying a 7-day window consistently every morning. So the counting rules are deterministic functions with unit tests, and the agent calls them. Thresholds live in one `Thresholds` object, so tuning them is a reviewed change rather than a prompt edit.
