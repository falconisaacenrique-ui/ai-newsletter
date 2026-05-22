"""Write today's EN/ES HTML into docs/, refresh docs/index.html and docs/archive.html."""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DOCS, log


ARCHIVE_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>AI Newsletter — Archive</title>
<style>body{{font-family:-apple-system,sans-serif;max-width:680px;margin:40px auto;padding:0 20px;color:#1c1917}}
h1{{font-size:24px}}.row{{padding:10px 0;border-bottom:1px solid #e7e5e4}}
.date{{color:#78716c;font-size:13px;margin-right:8px}}a{{color:#0c4a6e}}</style>
</head><body>
<h1>AI Newsletter — Archive</h1>
<p style="color:#78716c">Every issue lives here in English and Spanish.</p>
{rows}
</body></html>"""

ARCHIVE_ROW = ('<div class="row"><span class="date">{date}</span>'
               '<strong><a href="{en}">{title}</a></strong></div>')

ISSUE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(en|es)\.html$")


def publish(date_iso: str, mode: str, html_en: str, html_es: str | None,
            ranked: dict) -> Path:
    en_path = DOCS / f"{date_iso}-en.html"
    en_path.write_text(html_en, encoding="utf-8")

    if html_es:
        es_path = DOCS / f"{date_iso}-es.html"
        es_path.write_text(html_es, encoding="utf-8")

    # index.html → latest English issue
    (DOCS / "index.html").write_text(html_en, encoding="utf-8")

    _rebuild_archive()
    log.info(f"published {date_iso} + refreshed index/archive")
    return en_path


def _title_of(html: str) -> str:
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    return re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else "(untitled)"


def _rebuild_archive() -> None:
    issues = {}
    for p in DOCS.glob("*.html"):
        m = ISSUE_RE.match(p.name)
        if not m:
            continue
        date, lang = m.group(1), m.group(2)
        issues.setdefault(date, {})[lang] = p.name
    rows = []
    for date in sorted(issues.keys(), reverse=True):
        e = issues[date]
        if "en" not in e:
            continue
        title = _title_of((DOCS / e["en"]).read_text(encoding="utf-8"))
        rows.append(ARCHIVE_ROW.format(date=date, title=title, en=e["en"]))
    (DOCS / "archive.html").write_text(
        ARCHIVE_TEMPLATE.format(rows="\n".join(rows) or
                                "<p>No issues yet.</p>"),
        encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    ap.add_argument("--mode", choices=["daily", "weekly"], required=True)
    ap.add_argument("--en", required=True)
    ap.add_argument("--es", required=True)
    args = ap.parse_args()
    html_en = Path(args.en).read_text(encoding="utf-8")
    html_es = Path(args.es).read_text(encoding="utf-8")
    publish(args.date, args.mode, html_en, html_es, {})
    print(f"✓ published {args.date}")


if __name__ == "__main__":
    main()
