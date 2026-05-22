"""Call Claude to rank items and write each newsletter section.

Two modes:
  --mode daily   → uses ranker.md + writer_daily.md, expects ~30 items
  --mode weekly  → uses ranker.md + writer_weekly.md, expects ~100 items
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import claude_call, log, read_prompt

# JSON schemas for the two output shapes

_ITEM_PROPS = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string"},
        "dek": {"type": "string"},
        "body": {"type": "string"},
        "url": {"type": "string"},
        "source": {"type": "string"},
        "so_what": {"type": "string"},
    },
    "required": ["title", "body", "url", "source"],
}

_ONELINER_PROPS = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "url": {"type": "string"},
        "source": {"type": "string"},
    },
    "required": ["title", "summary", "url", "source"],
}

DAILY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "tldr": {"type": "array", "items": {"type": "string"}},
        "headline_story": _ITEM_PROPS,
        "models_releases": {"type": "array", "items": _ITEM_PROPS},
        "tools_resources": {"type": "array", "items": _ITEM_PROPS},
        "cool_uses": {"type": "array", "items": _ITEM_PROPS},
        "oneliners": {"type": "array", "items": _ONELINER_PROPS},
        "body_words_estimate": {"type": "integer"},
    },
    "required": ["tldr", "headline_story", "models_releases",
                 "tools_resources", "cool_uses", "oneliners",
                 "body_words_estimate"],
}

_TREND_PROPS = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "name": {"type": "string"},
        "direction": {"type": "string"},
        "body": {"type": "string"},
        "evidence_links": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["name", "direction", "body"],
}

WEEKLY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "tldr": {"type": "array", "items": {"type": "string"}},
        "biggest_release": _ITEM_PROPS,
        "tools_shipped": {"type": "array", "items": _ITEM_PROPS},
        "trend_tracker": {"type": "array", "items": _TREND_PROPS},
        "friday_fresh": {"type": "array", "items": _ITEM_PROPS},
        "reading_queue": {"type": "array", "items": _ONELINER_PROPS},
        "oneliners": {"type": "array", "items": _ONELINER_PROPS},
        "body_words_estimate": {"type": "integer"},
    },
    "required": ["tldr", "biggest_release", "tools_shipped",
                 "trend_tracker", "friday_fresh", "reading_queue",
                 "oneliners", "body_words_estimate"],
}


def _placeholder_daily(items: list[dict]) -> dict:
    top = items[0] if items else {"title": "Quiet day", "url": "#",
                                   "source": "system"}
    return {
        "tldr": [
            "[DRY-RUN] Placeholder TL;DR — no Claude call made.",
            f"[DRY-RUN] {len(items)} items in the input pool.",
        ],
        "headline_story": {
            "title": top.get("title", "Placeholder headline"),
            "dek": "[dry-run]",
            "body": "[dry-run] This would be Claude's headline writeup.",
            "url": top.get("url", "#"),
            "source": top.get("source", "system"),
            "so_what": "[dry-run]",
        },
        "models_releases": [
            {**i, "dek": "[dry-run dek]",
             "body": "[dry-run body]", "so_what": "[dry-run]"}
            for i in items[1:4]
        ],
        "tools_resources": [
            {**i, "dek": "[dry-run dek]",
             "body": "[dry-run body]", "so_what": "[dry-run]"}
            for i in items[4:9]
        ],
        "cool_uses": [
            {**i, "dek": "[dry-run dek]", "body": "[dry-run body]"}
            for i in items[9:12]
        ],
        "oneliners": [
            {"title": i.get("title", ""), "summary": "[dry-run]",
             "url": i.get("url", ""), "source": i.get("source", "")}
            for i in items[12:20]
        ],
        "body_words_estimate": 0,
    }


def _placeholder_weekly(items: list[dict]) -> dict:
    top = items[0] if items else {"title": "Quiet week", "url": "#",
                                   "source": "system"}
    return {
        "tldr": ["[DRY-RUN] weekly placeholder"],
        "biggest_release": {
            "title": top.get("title", "Placeholder"),
            "body": "[dry-run deep dive]",
            "url": top.get("url", "#"),
            "source": top.get("source", "system"),
            "so_what": "[dry-run]",
        },
        "tools_shipped": [
            {**i, "body": "[dry-run]"} for i in items[1:9]
        ],
        "trend_tracker": [
            {"name": "[dry-run trend]", "direction": "accelerating",
             "body": "[dry-run]"},
        ],
        "friday_fresh": [
            {**i, "body": "[dry-run]", "so_what": "[dry-run]"}
            for i in items[9:12]
        ],
        "reading_queue": [
            {"title": i.get("title", ""), "summary": "[dry-run]",
             "url": i.get("url", ""), "source": i.get("source", "")}
            for i in items[12:18]
        ],
        "oneliners": [
            {"title": i.get("title", ""), "summary": "[dry-run]",
             "url": i.get("url", ""), "source": i.get("source", "")}
            for i in items[18:30]
        ],
        "body_words_estimate": 0,
    }


def rank(mode: str, date_iso: str, items: list[dict],
         targets: dict, dry_run: bool = False) -> dict:
    if dry_run:
        return _placeholder_daily(items) if mode == "daily" \
               else _placeholder_weekly(items)

    model = os.environ.get("MODEL_RANKER", "claude-opus-4-7")
    writer_prompt = read_prompt("writer_daily" if mode == "daily"
                                else "writer_weekly")
    system_prompt = read_prompt("ranker") + "\n\n---\n\n" + writer_prompt

    user_payload = {
        "mode": mode,
        "date": date_iso,
        "targets": targets,
        "items": items,
    }
    user_content = (
        f"Today's input pool ({len(items)} items). Rank, select, and write "
        f"the {mode} newsletter sections per the rules.\n\n"
        + json.dumps(user_payload, indent=2, ensure_ascii=False)
    )

    schema = DAILY_SCHEMA if mode == "daily" else WEEKLY_SCHEMA
    log.info(f"calling Claude ({model}) to rank/write {mode} issue "
             f"with {len(items)} items")
    result = claude_call(
        model=model,
        system_prompt=system_prompt,
        user_content=user_content,
        output_schema=schema,
        max_tokens=12000,
    )
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["daily", "weekly"], required=True)
    ap.add_argument("--input", required=True, help="path to deduped items JSON")
    ap.add_argument("--date", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    items = data["items"] if isinstance(data, dict) else data

    import yaml
    cfg = yaml.safe_load(
        (Path(__file__).resolve().parent.parent / "config" / "sources.yaml")
        .read_text(encoding="utf-8")
    )
    targets = (cfg.get("ranker", {}).get(
        "daily_target_items" if args.mode == "daily"
        else "weekly_target_items", {}))

    result = rank(args.mode, args.date, items, targets, dry_run=args.dry_run)
    Path(args.output).write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✓ ranked → {args.output} (≈{result.get('body_words_estimate', 0)} words)")


if __name__ == "__main__":
    main()
