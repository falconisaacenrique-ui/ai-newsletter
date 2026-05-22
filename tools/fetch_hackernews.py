"""Fetch HN top stories matching AI/LLM keywords via the Algolia HN Search API.

No API key required. Polite single request per run.
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CONFIG, canonical_url, http_get, item_id, log, truncate

UTC = timezone.utc
API = "https://hn.algolia.com/api/v1/search"


def fetch(window_hours: int = 24) -> list[dict]:
    cfg = yaml.safe_load((CONFIG / "sources.yaml").read_text(encoding="utf-8"))
    hn_cfg = cfg.get("hackernews", {})
    query = hn_cfg.get("query", "AI OR LLM")
    min_points = int(hn_cfg.get("min_points", 75))
    weight = float(hn_cfg.get("weight", 0.7))

    since = int((datetime.now(UTC) - timedelta(hours=window_hours)).timestamp())
    # Algolia: filter by points >= N and created_at_i > since
    url = (f"{API}?query={query.replace(' ', '+')}"
           f"&tags=story"
           f"&numericFilters=points>={min_points},created_at_i>{since}"
           f"&hitsPerPage=50")
    try:
        resp = http_get(url, timeout=20)
        data = resp.json()
    except Exception as e:
        log.warning(f"HN fetch failed: {e}")
        return []

    out: list[dict] = []
    for h in data.get("hits", []):
        link = canonical_url(h.get("url") or
                             f"https://news.ycombinator.com/item?id={h['objectID']}")
        title = (h.get("title") or "").strip()
        if not link or not title:
            continue
        created = h.get("created_at_i")
        published = (datetime.fromtimestamp(created, tz=UTC).isoformat()
                     if created else datetime.now(UTC).isoformat())
        out.append({
            "id": item_id(link, title),
            "title": truncate(title, 240),
            "url": link,
            "source": "Hacker News",
            "source_kind": "hn",
            "source_weight": weight,
            "published_at": published,
            "summary": truncate(
                f"HN: {h.get('points', 0)} points, {h.get('num_comments', 0)} comments. "
                f"Discussion: https://news.ycombinator.com/item?id={h.get('objectID')}",
                400),
            "tags": [],
            "hn_points": h.get("points", 0),
            "hn_comments": h.get("num_comments", 0),
        })
    log.info(f"hn: {len(out)} stories in window (min {min_points} points)")
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
