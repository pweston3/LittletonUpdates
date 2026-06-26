"""Runtime configuration, driven by environment variables with safe defaults.

Nothing here is secret by itself; secrets (API key, mailbox password) come from
the environment / GitHub Actions secrets and are never written to disk.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE_DIR = ROOT / "state"
DOCS_DIR = ROOT / "docs"
ARCHIVE_DIR = DOCS_DIR / "archive"
SOURCES_FILE = ROOT / "sources.yaml"

SEEN_FILE = STATE_DIR / "seen.json"
HEALTH_FILE = STATE_DIR / "health.json"


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# --- Claude API -------------------------------------------------------------
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
# If no key is present the pipeline degrades to heuristics and still produces a digest.
USE_LLM = bool(ANTHROPIC_API_KEY)

# --- Email (optional) -------------------------------------------------------
# The inbox the agent READS (Notify Me forwards + your manual forwards):
IMAP_HOST = os.environ.get("IMAP_HOST", "imap.gmail.com")
IMAP_USER = os.environ.get("IMAP_USER", "")
IMAP_PASSWORD = os.environ.get("IMAP_PASSWORD", "")  # Gmail app password
IMAP_FOLDER = os.environ.get("IMAP_FOLDER", "INBOX")
INBOX_ENABLED = bool(IMAP_USER and IMAP_PASSWORD)

# Where the digest is SENT:
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
DIGEST_TO = os.environ.get("DIGEST_TO", "")  # comma-separated
EMAIL_ENABLED = _bool("EMAIL_ENABLED", bool(SMTP_USER and SMTP_PASSWORD and DIGEST_TO))

# --- Run behaviour ----------------------------------------------------------
# How many days back a fetched item may be and still count as "new-ish" context.
LOOKBACK_DAYS = int(os.environ.get("LOOKBACK_DAYS", "10"))
# Network timeout per request (seconds).
HTTP_TIMEOUT = int(os.environ.get("HTTP_TIMEOUT", "20"))
# A source returning zero items this many runs in a row is flagged unhealthy.
ZERO_YIELD_ALERT_RUNS = int(os.environ.get("ZERO_YIELD_ALERT_RUNS", "3"))

# Public URL the digest will live at (used for archive links in the email).
SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "").rstrip("/")
