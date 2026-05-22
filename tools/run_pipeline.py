"""End-to-end orchestrator.

Behavior:
- If --force is not passed AND we're being run by cron, exit silently unless
  current America/Chicago hour == 7. This lets us register two cron firings
  (12 + 13 UTC) so DST handles itself.
- Mode is auto-selected by weekday (Fri = weekly, else daily) unless --mode given.
- Output: writes archive/<date>.json, rendered HTML, publishes to docs/, sends email.

Common invocations:
  python tools/run_pipeline.py --dry-run                    # full preview, no API spend, no send
  python tools/run_pipeline.py --dry-run --date 2026-05-21  # specific date
  python tools/run_pipeline.py --to-self                    # real run, send only to self
  python tools/run_pipeline.py --force                      # real run, ignore the 7-AM gate
  python tools/run_pipeline.py --mode weekly --force        # force weekly mode
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (ARCHIVE, CONFIG, DOCS, ROOT, archive_path, canonical_url,
                     log, now_chicago, read_json, today_iso, write_json)

import fetch_rss
import fetch_hackernews
import fetch_reddit
import dedupe_normalize
import rank_and_summarize
import generate_monetization
import render_email
import translate_to_spanish
import publish_pages
import send_gmail


def _section(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}", flush=True)


def _load_archive_week(week_ending_iso: str) -> list[dict]:
    end = datetime.strptime(week_ending_iso, "%Y-%m-%d")
    items = []
    for i in range(1, 7):
        d = (end - timedelta(days=i)).strftime("%Y-%m-%d")
        p = archive_path(d)
        if p.exists():
            try:
                data = read_json(p)
                items.extend(data.get("items", []))
            except Exception as e:
                log.warning(f"archive {p.name} unreadable: {e}")
    return items


def _shipped_urls_this_week(date_iso: str) -> set[str]:
    """Return canonical URLs of items published in daily issues since the last Friday.

    The weekly cycle is Sat → Thu (daily issues) → Fri (weekly recap). Daily
    issues must not repeat each other within a cycle; the Friday weekly is
    allowed to re-surface anything (so this function returns empty for Friday).
    """
    dt = datetime.strptime(date_iso, "%Y-%m-%d")
    weekday = dt.weekday()  # Mon=0..Sun=6
    if weekday == 4:  # Friday → weekly mode, no daily-dedup needed
        return set()
    # Days since the most recent Saturday (the start of the cycle).
    lookback = (weekday - 5) % 7  # Sat=0 Sun=1 Mon=2 Tue=3 Wed=4 Thu=5
    urls: set[str] = set()
    fields_single = ("headline_story", "biggest_release")
    fields_list = ("models_releases", "tools_resources", "cool_uses",
                   "oneliners", "tools_shipped", "friday_fresh",
                   "reading_queue")
    for i in range(1, lookback + 1):
        d = (dt - timedelta(days=i)).strftime("%Y-%m-%d")
        p = archive_path(d)
        if not p.exists():
            continue
        try:
            data = read_json(p)
        except Exception:
            continue
        ranked = data.get("ranked") or {}
        for k in fields_single:
            v = ranked.get(k)
            if isinstance(v, dict) and v.get("url"):
                urls.add(canonical_url(v["url"]))
        for k in fields_list:
            for it in (ranked.get(k) or []):
                if isinstance(it, dict) and it.get("url"):
                    urls.add(canonical_url(it["url"]))
    return urls


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["daily", "weekly"],
                    help="override (default: weekday-based)")
    ap.add_argument("--date", help="ISO date for the issue (default: today Chicago)")
    ap.add_argument("--dry-run", action="store_true",
                    help="skip all Claude calls and Gmail send")
    ap.add_argument("--to-self", action="store_true",
                    help="send only to NEWSLETTER_FROM (skip Pages publish)")
    ap.add_argument("--force", action="store_true",
                    help="ignore the 7-AM gate")
    ap.add_argument("--skip-send", action="store_true",
                    help="render + publish but don't send")
    ap.add_argument("--skip-publish", action="store_true",
                    help="don't write to docs/ (preview only)")
    ap.add_argument("--skip-translation", action="store_true",
                    help="skip the Spanish translation pass (saves ~5 min on iteration)")
    args = ap.parse_args()

    now = now_chicago()
    if not args.force and now.hour != 7:
        log.info(f"local hour {now.hour} != 7; exiting silently (DST gate)")
        return

    date_iso = args.date or today_iso(now)
    mode = args.mode or ("weekly" if now.weekday() == 4 else "daily")
    log.info(f"mode={mode} date={date_iso} dry_run={args.dry_run}")

    # 1. Fetch
    _section(f"[1/8] Fetch ({mode})")
    window = 24 if mode == "daily" else 168
    raw = (fetch_rss.fetch(window) +
           fetch_hackernews.fetch(window) +
           fetch_reddit.fetch(window))
    write_json(archive_path(date_iso, "-raw"), {"items": raw})
    log.info(f"raw pool: {len(raw)} items")

    # 2. Dedupe
    _section("[2/8] Dedupe + normalize")
    items = dedupe_normalize.dedupe(raw)
    if mode == "weekly":
        # Weekly recap: merge in prior 6 days' items, then re-dedupe.
        # Cross-day exclusion does NOT apply — the weekly is meant to re-surface.
        prior = _load_archive_week(date_iso)
        log.info(f"weekly: loaded {len(prior)} items from prior 6 days")
        items = dedupe_normalize.dedupe(items + prior)
    else:
        # Daily: drop anything already shipped in a daily issue since the last Friday.
        shipped = _shipped_urls_this_week(date_iso)
        if shipped:
            before = len(items)
            items = [it for it in items
                     if canonical_url(it.get("url", "")) not in shipped]
            log.info(f"cross-day dedup: removed {before - len(items)} items "
                     f"already shipped this week (pool {before} → {len(items)})")
    write_json(archive_path(date_iso, "-deduped"), {"items": items})

    # 3. Rank + write
    _section(f"[3/8] Rank + write ({mode})")
    import yaml
    cfg = yaml.safe_load((CONFIG / "sources.yaml").read_text(encoding="utf-8"))
    targets = cfg.get("ranker", {}).get(
        "daily_target_items" if mode == "daily" else "weekly_target_items", {})
    ranked = rank_and_summarize.rank(mode, date_iso, items, targets,
                                     dry_run=args.dry_run)
    write_json(archive_path(date_iso, "-ranked"), ranked)

    # 4. Monetization
    _section("[4/8] Monetization corner")
    monet = generate_monetization.generate(mode, date_iso, ranked,
                                           dry_run=args.dry_run)
    write_json(archive_path(date_iso, "-monetization"), monet)

    # 5. Render English
    _section("[5/8] Render English")
    html_en = render_email.render(mode, ranked, monet, date_iso, lang="en")

    # 6. Translate
    _section("[6/8] Translate to Spanish")
    html_es = translate_to_spanish.translate(
        html_en,
        dry_run=(args.dry_run or args.skip_translation),
    )

    # Persist preview copies regardless of mode
    preview_en = ARCHIVE / f"preview-{date_iso}-en.html"
    preview_es = ARCHIVE / f"preview-{date_iso}-es.html"
    preview_en.write_text(html_en, encoding="utf-8")
    preview_es.write_text(html_es, encoding="utf-8")
    log.info(f"preview HTML → {preview_en} / {preview_es}")

    # 7. Publish to docs/
    if args.dry_run or args.skip_publish or args.to_self:
        _section("[7/8] Publish to docs/ — SKIPPED")
    else:
        _section("[7/8] Publish to docs/")
        publish_pages.publish(date_iso, mode, html_en, html_es, ranked)

    # 8. Send
    if args.dry_run or args.skip_send:
        _section("[8/8] Send email — SKIPPED")
    else:
        _section("[8/8] Send email")
        subscribers = []
        sub_file = ROOT / "subscribers.json"
        if sub_file.exists():
            subscribers = read_json(sub_file).get("subscribers", [])
        else:
            log.warning("subscribers.json missing; falling back to --to-self")
            args.to_self = True
        subject_default = ("AI Daily — " + date_iso if mode == "daily"
                           else "AI Weekly — " + date_iso)
        # Try to use the ranked headline as subject
        title = (ranked.get("headline_story", {}).get("title") if mode == "daily"
                 else ranked.get("biggest_release", {}).get("title"))
        subject = f"{'AI Daily' if mode == 'daily' else 'AI Weekly'} — {title}" \
            if title else subject_default
        send_gmail.send(html_en, subject, subscribers, to_self=args.to_self)

    # Persist a clean daily archive entry that the weekly pipeline can re-use
    archive_entry = {
        "date": date_iso,
        "mode": mode,
        "items": items,
        "ranked": ranked,
        "monetization": monet,
    }
    write_json(archive_path(date_iso), archive_entry)

    print(f"\n✓ DONE — {mode} issue for {date_iso}")
    print(f"  preview EN: {preview_en}")
    print(f"  preview ES: {preview_es}")


if __name__ == "__main__":
    main()
