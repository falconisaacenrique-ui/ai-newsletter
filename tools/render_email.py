"""Render the ranked sections + monetization block into HTML via Jinja2."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import TEMPLATES, log, pages_url

STRINGS = {
    "en": {
        "brand": "AI Daily",
        "brand_weekly": "AI Weekly",
        "issue_label": "Issue №",
        "tldr_sub": "the 30-second version",
        "tldr_week_label": "TL;DR · the week in 60 seconds",
        "headline": "Top story",
        "biggest_release": "The release of the week",
        "models": "Models & releases",
        "tools": "Tools, skills & resources",
        "tools_shipped": "Shipped this week",
        "cool_uses": "Cool uses & demos",
        "trends": "Trend tracker",
        "friday_fresh": "Friday's fresh news",
        "monetization_label": "Money corner",
        "monetization_synthesis_label": "Money corner · weekly",
        "monetization": "Ways to earn from today's news",
        "monetization_synthesis": "Ways to earn from the week",
        "monetization_intro": "Concrete angles tied to what shipped — small and same-day, weekend wedges, and longer plays.",
        "oneliners": "In brief",
        "reading_queue": "For the weekend",
        "who_buys": "Who buys",
        "why_now": "Why now",
        "first_step": "First step",
        "risk": "Risk",
        "archive": "archive",
        "footer_archive": "Read past issues in the",
        "footer_feedback": "Reply with what you'd cut or expand — I read everything.",
        "footer_made": "Curated and written with Claude · judged on capability, not vendor",
        "signoff_line": "Yours in plain language,",
        "signoff_line_weekly": "Have a good weekend,",
    },
    "es": {
        "brand": "AI Diario",
        "brand_weekly": "AI Semanal",
        "issue_label": "Edición №",
        "tldr_sub": "la versión de 30 segundos",
        "tldr_week_label": "TL;DR · la semana en 60 segundos",
        "headline": "Lo más importante",
        "biggest_release": "El lanzamiento de la semana",
        "models": "Modelos y lanzamientos",
        "tools": "Herramientas, skills y recursos",
        "tools_shipped": "Lo que se lanzó esta semana",
        "cool_uses": "Usos interesantes y demos",
        "trends": "Tendencias",
        "friday_fresh": "Lo más reciente del viernes",
        "monetization_label": "Esquina del dinero",
        "monetization_synthesis_label": "Esquina del dinero · semanal",
        "monetization": "Cómo ganar con lo de hoy",
        "monetization_synthesis": "Cómo ganar con lo de esta semana",
        "monetization_intro": "Ángulos concretos atados a lo que se lanzó: cosas pequeñas que se cierran hoy, wedges de fin de semana, y apuestas más largas.",
        "oneliners": "En breve",
        "reading_queue": "Para el fin de semana",
        "who_buys": "Quién compra",
        "why_now": "Por qué ahora",
        "first_step": "Primer paso",
        "risk": "Riesgo",
        "archive": "archivo",
        "footer_archive": "Lee ediciones pasadas en el",
        "footer_feedback": "Responde con qué cortarías o expandirías — leo todo.",
        "footer_made": "Curado y escrito con Claude · juzgado por capacidad, no por vendor",
        "signoff_line": "En lenguaje claro,",
        "signoff_line_weekly": "Buen fin de semana,",
    },
}


# Issue number = days since epoch (an arbitrary stable counter).
# Anchor: 2026-05-01 → No. 001
_EPOCH = datetime(2026, 5, 1)


def _issue_number(date_iso: str) -> str:
    try:
        dt = datetime.strptime(date_iso, "%Y-%m-%d")
        n = (dt - _EPOCH).days + 1
        if n < 1:
            n = 1
        return f"{n:03d}"
    except Exception:
        return "001"


def render(mode: str, ranked: dict, monetization: dict, date_iso: str,
           lang: str = "en") -> str:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(["html"]),
    )
    template_name = "daily.html.j2" if mode == "daily" else "weekly.html.j2"
    template = env.get_template(template_name)
    css = (TEMPLATES / "shared.css").read_text(encoding="utf-8")
    dt = datetime.strptime(date_iso, "%Y-%m-%d")
    date_display = dt.strftime("%A, %B %-d, %Y") if sys.platform != "win32" \
        else dt.strftime("%A, %B %#d, %Y")
    archive_url = pages_url(date_iso, lang).rsplit("/", 1)[0] + "/archive.html"

    return template.render(
        mode=mode,
        ranked=ranked,
        monetization=monetization,
        date=date_iso,
        date_display=date_display,
        issue_no=_issue_number(date_iso),
        lang=lang,
        strings=STRINGS[lang],
        css=css,
        url_en=pages_url(date_iso, "en"),
        url_es=pages_url(date_iso, "es"),
        archive_url=archive_url,
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["daily", "weekly"], required=True)
    ap.add_argument("--ranked", required=True)
    ap.add_argument("--monetization", required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--lang", default="en")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    ranked = json.loads(Path(args.ranked).read_text(encoding="utf-8"))
    monet = json.loads(Path(args.monetization).read_text(encoding="utf-8"))
    html = render(args.mode, ranked, monet, args.date, args.lang)
    Path(args.output).write_text(html, encoding="utf-8")
    print(f"✓ rendered {args.lang} {args.mode} → {args.output}")


if __name__ == "__main__":
    main()
