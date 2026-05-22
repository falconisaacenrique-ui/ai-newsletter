# PROGRESS — AI Newsletter

## Phase 1 — Scaffold & local pipeline
- [x] Directory structure created — DONE (2026-05-22)
- [x] Root files (.env.example, .gitignore, requirements.txt, subscribers.example.json) — DONE (2026-05-22)
- [x] Workflow SOPs (workflows/daily_newsletter.md, workflows/weekly_recap.md) — DONE (2026-05-22)
- [x] Config (sources.yaml + 5 cached prompt files) — DONE (2026-05-22)
- [x] tools/_common.py (Claude client + caching + Gmail OAuth helpers) — DONE (2026-05-22)
- [x] Fetchers (rss, hackernews, reddit) — DONE (2026-05-22)
- [x] tools/dedupe_normalize.py — DONE (2026-05-22)
- [x] Claude tools (rank_and_summarize, generate_monetization, translate_to_spanish) — DONE (2026-05-22)
- [x] tools/render_email.py + Jinja2 templates — DONE (2026-05-22)
- [x] tools/publish_pages.py and tools/send_gmail.py — DONE (2026-05-22)
- [x] tools/run_pipeline.py orchestrator — DONE (2026-05-22)
- [x] .github/workflows/newsletter.yml — DONE (2026-05-22)

## Phase 2 — Verification
- [x] Installed dependencies — DONE (2026-05-22)
- [x] Created `.env` (with REPLACE_ME for `ANTHROPIC_API_KEY`) — DONE (2026-05-22)
- [x] Created `subscribers.json` with falconisaacenrique@gmail.com — DONE (2026-05-22)
- [x] Dry-run daily preview rendered (2026-05-21, 11.6 KB EN + 11.7 KB ES) — DONE (2026-05-22)
- [x] Dry-run weekly preview rendered (2026-05-22, 13.2 KB EN + 13.3 KB ES) — DONE (2026-05-22)
- [x] Fetchers confirmed live: 90+ RSS items, 189 Reddit items, 279 total raw → 266 unique — DONE (2026-05-22)
- [x] `ANTHROPIC_API_KEY` pulled from TRADING TRIAL 2/.env, verified live (HTTP 200 + PONG) — DONE (2026-05-22)
- [x] `credentials.json` copied from ULTRANET (Gmail OAuth client) — DONE (2026-05-22)
- [ ] **YOU**: run `python tools/send_gmail.py --auth` (ULTRANET's token.json had expired; need a 60-second browser flow to mint a fresh one)
- [ ] After that: `python tools/run_pipeline.py --to-self --force` — real run to your inbox
- [ ] Hand-grade 3 consecutive daily previews — iterate on prompts in `config/prompts/`

### Tuning notes from first dry-run
- HN Algolia query returned 0 items at min 75 points. Either lower `min_points` in `config/sources.yaml` or rework the query string (today's quiet result may also just be reality).
- Anthropic / Mistral / Meta / Cohere RSS feeds returned 0 items in the 24h window — feeds are fine but those orgs didn't post recently. Confirmed working with OpenAI / DeepMind / HF / Simon Willison.

## Phase 3 — Cloud cutover (TODO)
- [ ] Create GitHub repo, push code
- [ ] Add secrets: `ANTHROPIC_API_KEY`, `GMAIL_CREDENTIALS_JSON`, `GMAIL_TOKEN_JSON`, `PAGES_BASE_URL`
- [ ] Enable GitHub Pages from `docs/` on `main`
- [ ] Trigger `workflow_dispatch` for first cloud run
- [ ] Verify both Pages URLs render + email lands
- [ ] Let scheduled cron take over

## Current State
- Last completed: full local scaffold
- Next up: install deps, dry-run
- Blockers: none
- Test status: not yet wired (manual dry-run is the test for now)
