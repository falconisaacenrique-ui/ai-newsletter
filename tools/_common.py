"""Shared helpers for the AI Newsletter pipeline."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

# Make print() with non-ASCII characters work on Windows cp1252 consoles.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = ROOT / "archive"
DOCS = ROOT / "docs"
CONFIG = ROOT / "config"
TEMPLATES = ROOT / "templates"
TMP = ROOT / ".tmp"
ARCHIVE.mkdir(exist_ok=True)
DOCS.mkdir(exist_ok=True)
TMP.mkdir(exist_ok=True)

load_dotenv(ROOT / ".env")

LOG_LEVEL = os.environ.get("LOG_LEVEL", "info").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("newsletter")

CHICAGO = ZoneInfo("America/Chicago")
UTC = timezone.utc


# ---------- env ----------

def env(key: str, required: bool = True, default: str = "") -> str:
    val = os.environ.get(key, default).strip()
    if not val and required:
        sys.exit(f"[fatal] missing env var {key} (set it in .env)")
    return val


# ---------- time ----------

def now_chicago() -> datetime:
    return datetime.now(CHICAGO)


def today_iso(d: datetime | None = None) -> str:
    return (d or now_chicago()).strftime("%Y-%m-%d")


def iso_to_dt(s: str) -> datetime:
    # Accepts "2026-05-22" or full ISO
    if len(s) == 10:
        return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=CHICAGO)
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(UTC)


# ---------- json / file ----------

def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str),
                    encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def archive_path(date_iso: str, suffix: str = "") -> Path:
    name = f"{date_iso}{suffix}.json"
    return ARCHIVE / name


def read_prompt(name: str) -> str:
    return (CONFIG / "prompts" / f"{name}.md").read_text(encoding="utf-8")


# ---------- strings / urls ----------

def slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-") or "unknown"


_TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term",
                    "utm_content", "ref", "ref_src", "ref_url", "fbclid",
                    "gclid", "mc_cid", "mc_eid"}


def canonical_url(url: str) -> str:
    """Strip tracking params, lowercase host, normalize trailing slash."""
    if not url:
        return ""
    try:
        u = urlparse(url.strip())
        host = (u.netloc or "").lower()
        if host.startswith("www."):
            host = host[4:]
        qs = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=False)
              if k.lower() not in _TRACKING_PARAMS]
        path = u.path or "/"
        if path != "/" and path.endswith("/"):
            path = path[:-1]
        return urlunparse((u.scheme or "https", host, path, "",
                           urlencode(qs), ""))
    except Exception:
        return url.strip()


def item_id(url: str, title: str) -> str:
    seed = (canonical_url(url) or title or "").encode("utf-8")
    return hashlib.sha1(seed).hexdigest()[:12]


# ---------- Claude client ----------

_anthropic_client = None


def claude_client():
    """Lazy-loaded Anthropic client."""
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic  # local import so dry-run doesn't require the package
        env("ANTHROPIC_API_KEY")
        _anthropic_client = anthropic.Anthropic()
    return _anthropic_client


def claude_call(
    *,
    model: str,
    system_prompt: str,
    user_content: str,
    output_schema: dict | None = None,
    max_tokens: int = 8000,
    cache_system: bool = True,
    max_retries: int = 3,
) -> dict | str:
    """Single Claude call with prompt caching on the system prompt + retries.

    Returns parsed JSON if output_schema is provided, else raw text.
    """
    import anthropic
    from anthropic import APIStatusError, RateLimitError

    client = claude_client()
    system_block = [{"type": "text", "text": system_prompt}]
    if cache_system:
        system_block[0]["cache_control"] = {"type": "ephemeral"}

    kwargs: dict[str, Any] = dict(
        model=model,
        max_tokens=max_tokens,
        system=system_block,
        messages=[{"role": "user", "content": user_content}],
    )
    if output_schema is not None:
        kwargs["output_config"] = {
            "format": {"type": "json_schema", "schema": output_schema}
        }

    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = client.messages.create(**kwargs)
            text = next((b.text for b in resp.content if b.type == "text"), "")
            if output_schema is not None:
                return json.loads(text)
            return text
        except RateLimitError as e:
            last_err = e
            wait = 2 ** attempt + 1
            log.warning(f"rate limited, sleeping {wait}s (attempt {attempt+1})")
            time.sleep(wait)
        except APIStatusError as e:
            if e.status_code >= 500:
                last_err = e
                wait = 2 ** attempt + 1
                log.warning(f"server error {e.status_code}, sleeping {wait}s")
                time.sleep(wait)
                continue
            raise
    raise RuntimeError(f"Claude call failed after {max_retries} retries: {last_err}")


# ---------- HTTP ----------

def http_get(url: str, *, timeout: int = 20, headers: dict | None = None,
             max_retries: int = 3) -> "requests.Response":
    """GET with exponential backoff. Raises on final failure."""
    import requests
    h = {"User-Agent": os.environ.get("REDDIT_USER_AGENT",
                                       "ai-newsletter/0.1")}
    if headers:
        h.update(headers)
    last = None
    for attempt in range(max_retries):
        try:
            r = requests.get(url, timeout=timeout, headers=h)
            if r.status_code == 200:
                return r
            if r.status_code in (429, 500, 502, 503, 504):
                last = RuntimeError(f"http {r.status_code} for {url}")
                time.sleep(2 ** attempt + 0.5)
                continue
            r.raise_for_status()
            return r
        except Exception as e:
            last = e
            time.sleep(2 ** attempt + 0.5)
    raise RuntimeError(f"GET failed after {max_retries}: {url}: {last}")


# ---------- pages URLs ----------

def pages_url(date_iso: str, lang: str = "en") -> str:
    """Returns the public Pages URL for an issue.

    Returns empty string if PAGES_BASE_URL isn't configured — templates use
    that as a signal to hide the EN/ES toggle entirely (relative paths break
    inside Gmail's redirect proxy).
    """
    base = env("PAGES_BASE_URL", required=False, default="").rstrip("/")
    if not base:
        return ""
    return f"{base}/{date_iso}-{lang}.html"


# ---------- truncate / wordcount ----------

def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or ""))


def truncate(s: str, n: int) -> str:
    s = (s or "").strip()
    if len(s) <= n:
        return s
    return s[: n - 1].rstrip() + "…"
