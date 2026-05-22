"""Translate rendered English HTML into Spanish HTML via Claude."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import claude_call, log, read_prompt


def translate(html_en: str, dry_run: bool = False) -> str:
    if dry_run:
        # Wrap with a banner so previews are obvious.
        return ("<!-- DRY RUN: Spanish translation skipped -->\n" + html_en)

    model = os.environ.get("MODEL_TRANSLATOR", "claude-sonnet-4-6")
    system_prompt = read_prompt("translator")
    log.info(f"translating to Spanish via {model} "
             f"({len(html_en)} chars)")
    out = claude_call(
        model=model,
        system_prompt=system_prompt,
        user_content=html_en,
        output_schema=None,
        max_tokens=16000,
    )
    return out  # raw text


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    html_en = Path(args.input).read_text(encoding="utf-8")
    html_es = translate(html_en, dry_run=args.dry_run)
    Path(args.output).write_text(html_es, encoding="utf-8")
    print(f"✓ Spanish → {args.output}")


if __name__ == "__main__":
    main()
