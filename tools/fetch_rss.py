"""Fetch RSS feeds listed in config/sources.yaml.

Returns normalized news items as a list. Each item:
  {id, title, url, source, source_weight, published_at, summary, tags}

Standalone:
    python tools/fetch_rss.py --window 24h
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import feedparser
import yaml
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CONFIG, canonical_url, item_id, log, truncate

UTC = timezone.utc


def _to_dt(entry) -> datetime | None:
    for k in ("published_parsed", "updated_parsed"):
        v = entry.get(k)
        if v:
            try:
                return datetime(*v[:6], tzinfo=UTC)
            except Exception:
                continue
    return None


def _clean_summary(entry) -> str:
    raw = (entry.get("summary") or entry.get("description")
           or (entry.get("content", [{}])[0].get("value") if entry.get("content") else "")
           or "")
    if not raw:
        return ""
    try:
        text = BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)
    except Exception:
        text = raw
    return truncate(text, 600)


def fetch(window_hours: int = 24) -> list[dict]:
    cfg = yaml.safe_load((CONFIG / "sources.yaml").read_text(encoding="utf-8"))
    cutoff = datetime.now(UTC) - timedelta(hours=window_hours)
    out: list[dict] = []

    for src in cfg.get("rss", []):
        name = src["name"]
        url = src["url"]
        weight = float(src.get("weight", 0.5))
        try:
            parsed = feedparser.parse(url)
            entries = parsed.entries or []
        except Exception as e:
            log.warning(f"RSS fetch failed for {name}: {e}")
            continue

        kept = 0
        for e in entries:
            dt = _to_dt(e) or datetime.now(UTC)
            if dt < cutoff:
                continue
            link = canonical_url(e.get("link") or "")
            title = (e.get("title") or "").strip()
            if not link or not title:
                continue
            out.append({
                "id": item_id(link, title),
                "title": truncate(title, 240),
                "url": link,
                "source": name,
                "source_kind": "rss",
                "source_weight": weight,
                "published_at": dt.astimezone(UTC).isoformat(),
                "summary": _clean_summary(e),
                "tags": [t.get("term", "") for t in e.get("tags", []) if t.get("term")],
            })
            kept += 1
        log.info(f"rss {name}: {kept} items in window")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", default="24h", help="e.g. 24h or 168h")
    args = ap.parse_args()
    hours = int(args.window.rstrip("hH") or 24)
    items = fetch(hours)
    import json
    print(json.dumps({"count": len(items), "items": items}, indent=2,
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
