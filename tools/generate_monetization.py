"""Generate the Monetization corner using a separate Claude call.

Reads the ranked sections and produces 3–5 angles + (weekly only) a synthesis.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import claude_call, log, read_prompt

ANGLE_PROPS = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string"},
        "kind": {"type": "string",
                 "enum": ["quick_service", "product", "side_gig",
                          "automation", "investing", "content"]},
        "tied_to": {"type": "array", "items": {"type": "string"}},
        "who_buys": {"type": "string"},
        "why_now": {"type": "string"},
        "first_step": {"type": "string"},
        "effort_level": {"type": "string",
                         "enum": ["hours", "weekend", "2_weeks", "month_plus"]},
        "revenue_size": {"type": "string"},
        "risk_note": {"type": "string"},
    },
    "required": ["title", "kind", "tied_to", "who_buys", "why_now",
                 "first_step", "effort_level", "revenue_size", "risk_note"],
}

DAILY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "angles": {"type": "array", "items": ANGLE_PROPS},
    },
    "required": ["angles"],
}

WEEKLY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "angles": {"type": "array", "items": ANGLE_PROPS},
        "synthesis": {"type": "string"},
    },
    "required": ["angles", "synthesis"],
}


def _placeholder(mode: str) -> dict:
    angles = [{
        "title": "[dry-run] Skill pack for Codex: bookkeeping triage",
        "kind": "product",
        "tied_to": ["placeholder-id"],
        "who_buys": "Solo bookkeepers serving 3–15 SMB clients",
        "why_now": "[dry-run]",
        "first_step": "[dry-run] Post a 1-pager on r/Bookkeeping.",
        "effort_level": "weekend",
        "revenue_size": "[dry-run] $1–3k MRR",
        "risk_note": "[dry-run] Competition from Intuit-adjacent tools.",
    }]
    out = {"angles": angles}
    if mode == "weekly":
        out["synthesis"] = "[dry-run weekly monetization synthesis]"
    return out


def _flatten_items(ranked: dict, mode: str) -> list[dict]:
    """Extract a flat list of items the angles can tie to (with id = url)."""
    keys = (["headline_story", "models_releases", "tools_resources",
             "cool_uses", "oneliners"] if mode == "daily"
            else ["biggest_release", "tools_shipped", "friday_fresh",
                  "reading_queue", "oneliners"])
    out = []
    for k in keys:
        v = ranked.get(k)
        if isinstance(v, dict):
            v = [v]
        for it in (v or []):
            out.append({
                "id": it.get("url", ""),
                "title": it.get("title", ""),
                "url": it.get("url", ""),
                "source": it.get("source", ""),
                "summary": it.get("body", "") or it.get("summary", ""),
            })
    return out


def generate(mode: str, date_iso: str, ranked: dict,
             dry_run: bool = False) -> dict:
    if dry_run:
        return _placeholder(mode)

    items = _flatten_items(ranked, mode)
    system_prompt = read_prompt("monetization")
    user_payload = {"mode": mode, "date": date_iso, "items": items}
    user_content = (
        f"Produce the monetization angles for the {mode} issue. "
        f"Tie each angle to specific items below.\n\n"
        + json.dumps(user_payload, indent=2, ensure_ascii=False)
    )
    model = os.environ.get("MODEL_RANKER", "claude-opus-4-7")
    schema = DAILY_SCHEMA if mode == "daily" else WEEKLY_SCHEMA
    log.info(f"calling Claude ({model}) for {mode} monetization "
             f"({len(items)} items)")
    return claude_call(
        model=model,
        system_prompt=system_prompt,
        user_content=user_content,
        output_schema=schema,
        max_tokens=4000,
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["daily", "weekly"], required=True)
    ap.add_argument("--ranked", required=True, help="ranked sections JSON")
    ap.add_argument("--date", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    ranked = json.loads(Path(args.ranked).read_text(encoding="utf-8"))
    result = generate(args.mode, args.date, ranked, dry_run=args.dry_run)
    Path(args.output).write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✓ monetization → {args.output} ({len(result.get('angles', []))} angles)")


if __name__ == "__main__":
    main()
