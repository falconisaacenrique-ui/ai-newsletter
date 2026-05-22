"""Dedupe and assign a seed score to merged items.

Input: list of raw items from the fetchers (or a list of lists).
Output: list of unique items with `score_seed`.

Dedupe strategy:
1. Group by canonical URL (exact match).
2. Within remaining groups, fuzzy-merge by title similarity ≥ 0.85 using rapidfuzz.
3. When merging, keep the highest-weight source, sum signals (HN points, Reddit ups),
   and union tags / source labels.
"""
from __future__ import annotations

from pathlib import Path
import sys

from rapidfuzz import fuzz

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import canonical_url, log

TITLE_SIM_THRESHOLD = 85  # rapidfuzz returns 0–100


def _merge(a: dict, b: dict) -> dict:
    """Merge b into a, preferring higher-quality fields."""
    if (b.get("source_weight") or 0) > (a.get("source_weight") or 0):
        # Promote b's source as primary
        a, b = b, a
    # Keep primary source, but record companions
    companions = a.get("companion_sources", [])
    if b.get("source") and b["source"] != a.get("source"):
        companions.append(b["source"])
    a["companion_sources"] = list(dict.fromkeys(companions))
    # Sum engagement signals
    for k in ("hn_points", "hn_comments", "reddit_ups", "reddit_comments"):
        if k in b:
            a[k] = (a.get(k) or 0) + (b.get(k) or 0)
    # Union tags
    tags = set(a.get("tags", []) or []) | set(b.get("tags", []) or [])
    a["tags"] = sorted(t for t in tags if t)
    # Prefer longer summary
    if len(b.get("summary", "") or "") > len(a.get("summary", "") or ""):
        a["summary"] = b["summary"]
    return a


def dedupe(items: list[dict]) -> list[dict]:
    # Step 1: collapse by canonical URL
    by_url: dict[str, dict] = {}
    for it in items:
        u = canonical_url(it.get("url", ""))
        if not u:
            continue
        it["url"] = u
        if u in by_url:
            by_url[u] = _merge(by_url[u], it)
        else:
            by_url[u] = it

    bucket = list(by_url.values())

    # Step 2: fuzzy title merge among remaining
    merged: list[dict] = []
    for it in bucket:
        matched = False
        for m in merged:
            if fuzz.token_set_ratio(it["title"], m["title"]) >= TITLE_SIM_THRESHOLD:
                _merge(m, it)
                matched = True
                break
        if not matched:
            merged.append(it)

    # Step 3: assign score_seed
    for it in merged:
        weight = float(it.get("source_weight", 0.5))
        companions_boost = 0.1 * len(it.get("companion_sources", []))
        hn_signal = min(0.4, (it.get("hn_points", 0) or 0) / 500.0)
        reddit_signal = min(0.3, (it.get("reddit_ups", 0) or 0) / 2000.0)
        it["score_seed"] = round(weight + companions_boost + hn_signal + reddit_signal, 4)

    merged.sort(key=lambda x: x["score_seed"], reverse=True)
    log.info(f"dedupe: {len(items)} → {len(merged)} unique items")
    return merged
