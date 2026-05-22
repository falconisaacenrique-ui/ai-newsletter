"""Fetch top posts from configured subreddits via the public /top.json endpoint."""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CONFIG, canonical_url, http_get, item_id, log, truncate

UTC = timezone.utc


def fetch(window_hours: int = 24) -> list[dict]:
    cfg = yaml.safe_load((CONFIG / "sources.yaml").read_text(encoding="utf-8"))
    r_cfg = cfg.get("reddit", {})
    subs = r_cfg.get("subreddits", [])
    min_up = int(r_cfg.get("min_upvotes", 100))
    tfilter = r_cfg.get("time_filter", "day")
    if window_hours > 24 and tfilter == "day":
        tfilter = "week"

    out: list[dict] = []
    for entry in subs:
        sub = entry["name"]
        weight = float(entry.get("weight", 0.5))
        url = (f"https://www.reddit.com/r/{sub}/top.json"
               f"?t={tfilter}&limit=50")
        try:
            resp = http_get(url, timeout=20)
            data = resp.json()
        except Exception as e:
            log.warning(f"reddit {sub} fetch failed: {e}")
            time.sleep(1)
            continue

        kept = 0
        for child in data.get("data", {}).get("children", []):
            p = child.get("data", {})
            if p.get("stickied"):
                continue
            ups = int(p.get("ups", 0))
            if ups < min_up:
                continue
            title = (p.get("title") or "").strip()
            external = p.get("url_overridden_by_dest") or p.get("url") or ""
            permalink = f"https://www.reddit.com{p.get('permalink', '')}"
            # Prefer external link if it's not back to reddit itself.
            link_target = external if external and "reddit.com" not in external else permalink
            link = canonical_url(link_target)
            if not link or not title:
                continue
            created = p.get("created_utc")
            published = (datetime.fromtimestamp(created, tz=UTC).isoformat()
                         if created else datetime.now(UTC).isoformat())
            selftext = truncate(p.get("selftext", "") or "", 400)
            summary = (selftext if selftext
                       else f"r/{sub}: {ups} upvotes, {p.get('num_comments', 0)} comments. "
                            f"Discussion: {permalink}")
            out.append({
                "id": item_id(link, title),
                "title": truncate(title, 240),
                "url": link,
                "source": f"r/{sub}",
                "source_kind": "reddit",
                "source_weight": weight,
                "published_at": published,
                "summary": truncate(summary, 600),
                "tags": [p.get("link_flair_text", "")] if p.get("link_flair_text") else [],
                "reddit_ups": ups,
                "reddit_comments": p.get("num_comments", 0),
                "reddit_permalink": permalink,
            })
            kept += 1
        log.info(f"reddit r/{sub}: {kept} posts")
        time.sleep(1)  # polite
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", default="24h")
    args = ap.parse_args()
    hours = int(args.window.rstrip("hH") or 24)
    items = fetch(hours)
    import json
    print(json.dumps({"count": len(items), "items": items}, indent=2,
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
