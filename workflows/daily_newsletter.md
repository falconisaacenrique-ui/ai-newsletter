# Workflow — Daily AI Newsletter (Sat–Thu)

## Objective
Deliver a 5–7 min read briefing to every active subscriber in `subscribers.json` covering the most capability-impactful AI developments from the prior ~24 h. Includes a monetization corner with 3–5 concrete ideas tied to that day's items.

## Inputs
- Current date (America/Chicago)
- Active subscriber list (`subscribers.json`)
- Configured sources (`config/sources.yaml`)
- Cached Claude system prompts (`config/prompts/*.md`)

## Outputs
- Email sent to every subscriber whose `active=true` and `lang_pref="en"` (Spanish-pref subscribers receive a link-only nudge to the Spanish Pages URL; same email body)
- Two static HTML pages committed to `docs/`:
  - `docs/YYYY-MM-DD-en.html`
  - `docs/YYYY-MM-DD-es.html`
- `docs/index.html` updated to point at the new English issue
- `archive/YYYY-MM-DD.json` written for Friday's recap pipeline
- One line appended to `PROGRESS.md`

## Steps
1. **Mode gate** — `run_pipeline.py` checks local Chicago time; abort silently unless hour == 7. Verify weekday ≠ Friday (else hand off to `weekly_recap.md`).
2. **Fetch (parallel)** — call `fetch_rss.py`, `fetch_hackernews.py`, `fetch_reddit.py` with `--window 24h`. Persist raw pulls to `archive/YYYY-MM-DD-raw.json`.
3. **Dedupe + normalize** — `dedupe_normalize.py`. Canonicalize URLs (strip utm_*, normalize trailing slashes), merge near-duplicates by title similarity ≥ 0.85, assign source weight from `sources.yaml`.
3a. **Cross-day dedup** — `run_pipeline.py:_shipped_urls_this_week`. Drop any item whose canonical URL already appeared in a daily issue published since the most recent Friday. Sat starts fresh; Sun looks back 1 day; Mon looks back 2; …; Thu looks back 5. Reason: subscribers reading every day should not see Tuesday's lead story re-appear on Wednesday. The Friday weekly is exempt — it is meant to re-surface the week.
4. **Rank + write** — `rank_and_summarize.py --mode daily`. Uses cached prompts `ranker.md` + `writer_daily.md`. Output: JSON with `tldr`, `headline_story`, `models_releases`, `tools_resources`, `cool_uses`, `oneliners`.
5. **Monetization** — `generate_monetization.py --mode daily`. Uses cached `monetization.md`. Output: 3–5 ideas, each tying to a specific item from step 4.
6. **Render English** — `render_email.py --template daily.html.j2 --lang en`.
7. **Translate** — `translate_to_spanish.py`. Uses cached `translator.md`.
8. **Publish to Pages** — `publish_pages.py`. Updates `docs/index.html` and `docs/archive.html`.
9. **Send** — `send_gmail.py`. EN/ES toggle links at top point to the Pages URLs from step 8.
10. **Archive + log** — write `archive/YYYY-MM-DD.json` and append a status line to `PROGRESS.md`.

## Edge cases & known constraints
- **Empty fetch**: if combined dedupe output < 10 items, log a warning and send anyway with whatever exists. Don't fabricate.
- **Translator failure**: if Spanish render fails, still send English; Spanish Pages URL falls back to English.
- **Gmail token expiry**: 7-day expiry on unverified OAuth apps. Use the stored refresh_token to mint a fresh access token at the top of `send_gmail.py`. If refresh fails, send a Discord/Telegram alert (TODO) and abort the send.
- **Source flakiness**: each fetcher must `continue` past per-source errors. One dead RSS feed should not break the whole run.
- **Rate limits**: HN Algolia ~10k req/hour (we use 1). Reddit ~60 req/min unauth (we use 3). Claude — handled by retry/backoff in `_common.py`.

## Quality bar
- Length: 1,200–1,700 words English body.
- Monetization: every idea names a specific tool/model/release from today AND a concrete first step.
- Voice: pragmatic, capability-focused, no vendor cheerleading. Anthropic and competitors judged the same way.
