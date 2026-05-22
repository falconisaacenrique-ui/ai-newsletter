# Workflow — Weekly Recap (Friday)

## Objective
Deliver a 10–15 min read recap covering the previous Friday → Thursday plus that morning's fresh news. Synthesize the monetization ideas seeded across the week.

## Inputs
- Last 6 days of `archive/YYYY-MM-DD.json`
- Fresh 24 h pull (Thu evening → Fri morning)
- `subscribers.json`, `sources.yaml`, cached prompts

## Outputs
- Email + Pages publish, same shape as the daily workflow but using `daily.html.j2` → `weekly.html.j2`
- `archive/YYYY-MM-DD-weekly.json`

## Steps
1. **Mode gate** — Chicago hour == 7 AND weekday == Friday.
2. **Fetch fresh** — `fetch_*.py --window 24h` for Thursday → Friday.
3. **Load week** — read prior 6 days of ranked items from `archive/`. If a day is missing, log it and continue with what exists.
4. **Dedupe + normalize** — `dedupe_normalize.py` collapses duplicates across the week so a single big release doesn't dominate via repetition. **Cross-day dedup does NOT apply on Friday** — the weekly issue is deliberately allowed to re-surface anything that ran Sat–Thu, since this is the consolidated view subscribers expect.
5. **Rank + write** — `rank_and_summarize.py --mode weekly`. Uses `ranker.md` + `writer_weekly.md`. Output sections: `tldr`, `biggest_release`, `tools_shipped`, `trend_tracker`, `friday_fresh`, `oneliners`.
6. **Monetization synthesis** — `generate_monetization.py --mode weekly`. Uses `monetization.md` with `--synthesis` flag. Output: which 3–5 ideas across the week look most promising, plus the first practical step for each.
7–10. Same as daily (render → translate → publish → send → archive).

## Quality bar
- Length: 2,500–3,500 words English body.
- Trend tracker must call out specifically what accelerated vs decelerated this week with named evidence (specific releases/posts).
- Monetization synthesis must reference items from at least 3 different days of the week (proving it's a synthesis, not a re-run of Thursday).
