# AI Daily — Personal AI-News Newsletter

A morning briefing on what actually moved in AI yesterday — new models, features, tools, skills, templates, cool uses, and 3–5 concrete monetization angles tied to that day's news. Friday issues recap the full week.

Built on the **WAT framework**: deterministic Python tools in `tools/`, markdown SOPs in `workflows/`, Claude as the reasoning layer.

## Schedule
- **Sat–Thu, 7 AM America/Chicago** → 5–7 min daily issue
- **Fri, 7 AM America/Chicago** → 10–15 min weekly recap (covers Fri-prior → Thu + that Friday's news)

## Stack
- **Sources**: RSS (Anthropic, OpenAI, DeepMind, Google AI, Mistral, Hugging Face, Simon Willison, Latent Space, The Batch, …) + Hacker News API + Reddit (r/LocalLLaMA, r/MachineLearning, r/singularity)
- **LLM**: Claude `claude-sonnet-4-6` for ranking, writing, and (when enabled) translation. System prompts cached → ~80 % input-cost savings on repeat calls. Per-issue API cost ≈ $0.20 daily / $0.40 weekly.
- **Email**: Gmail API (OAuth)
- **Web archive**: GitHub Pages (`docs/`). Each issue published in EN and ES; email links to both.
- **Schedule**: GitHub Actions cron at 12:00 + 13:00 UTC; the script no-ops unless local Houston hour == 7 (DST-safe).

## Quickstart

```bash
# 1. Install
pip install -r requirements.txt

# 2. Configure
cp .env.example .env                       # then fill in ANTHROPIC_API_KEY
cp subscribers.example.json subscribers.json

# 3. First-time Gmail OAuth (one-time, local)
#    Download credentials.json from Google Cloud Console (OAuth client, Desktop type)
#    Place it next to .env, then:
python tools/send_gmail.py --auth         # opens a browser, mints token.json

# 4. Dry-run yesterday's news
python tools/run_pipeline.py --dry-run --date 2026-05-21

# 5. Send a real email to yourself only
python tools/run_pipeline.py --to-self
```

## Project layout

```
workflows/      Markdown SOPs (the "what & why")
tools/          Deterministic Python (the "how")
config/         sources.yaml + cached Claude system prompts
templates/      Jinja2 HTML email templates
archive/        Daily JSON (gitignored) — fuels Friday weekly recap
docs/           GitHub Pages output (committed)
.github/workflows/  GitHub Actions cron
```

## Pipeline (one process, one .env load)
1. `fetch_rss` + `fetch_hackernews` + `fetch_reddit` → raw items
2. `dedupe_normalize` → unique, source-weighted items
3. `rank_and_summarize` → ranked sections + prose (Claude, cached prompt)
4. `generate_monetization` → 3–5 ideas tied to today's items (Claude, cached prompt)
5. `render_email` → HTML + plaintext (English)
6. `translate_to_spanish` → Spanish HTML
7. `publish_pages` → write `docs/YYYY-MM-DD-{en,es}.html`, update `index.html` + `archive.html`
8. `send_gmail` → email English version with EN/ES toggle links at top

## Editing the editorial voice
- `config/prompts/ranker.md` — what counts as "capability-impactful"
- `config/prompts/writer_daily.md` / `writer_weekly.md` — tone, length, format
- `config/prompts/monetization.md` — how to frame monetization ideas
- `config/prompts/translator.md` — Spanish-translation rules

Tweak these, re-run `--dry-run`, eyeball the preview HTML, iterate. The prompts are cached so iteration is cheap.

See [PROGRESS.md](PROGRESS.md) for current status.
