"""Inbox adapter — reads a dedicated mailbox over IMAP.

This is the PRIMARY route for town content, because the CivicPlus site blocks
automated page fetching. Subscribe the mailbox to Notify Me + CivicReady, and
forward anything from the human-only tiers (Facebook group, Nextdoor) into it.

Reads UNSEEN messages, turns each into an Item, and marks them seen. Requires
IMAP_USER / IMAP_PASSWORD; if unset, run.py skips this adapter cleanly.
"""
from __future__ import annotations

import email
import imaplib
import logging
from email.header import decode_header
from email.utils import parsedate_to_datetime

from .base import Item, clean_text

log = logging.getLogger("adapters.inbox")


def _decode(value: str | None) -> str:
    if not value:
        return ""
    parts = []
    for text, enc in decode_header(value):
        if isinstance(text, bytes):
            parts.append(text.decode(enc or "utf-8", errors="replace"))
        else:
            parts.append(text)
    return "".join(parts)


def _body_text(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True) or b""
                return payload.decode(part.get_content_charset() or "utf-8", "replace")
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True) or b""
                return clean_text(payload.decode(part.get_content_charset() or "utf-8", "replace"))
        return ""
    payload = msg.get_payload(decode=True) or b""
    return payload.decode(msg.get_content_charset() or "utf-8", "replace")


def fetch(source: dict, cfg, timeout: int = 20) -> list[Item]:
    if not getattr(cfg, "INBOX_ENABLED", False):
        log.info("inbox disabled (no IMAP creds); skipping %s", source["id"])
        return []

    from_contains = [s.lower() for s in source.get("params", {}).get("from_contains", [])]
    items: list[Item] = []
    try:
        conn = imaplib.IMAP4_SSL(cfg.IMAP_HOST)
        conn.login(cfg.IMAP_USER, cfg.IMAP_PASSWORD)
        conn.select(cfg.IMAP_FOLDER)
        typ, data = conn.search(None, "UNSEEN")
        if typ != "OK":
            log.warning("imap search failed"); conn.logout(); return []
        for num in data[0].split():
            typ, msg_data = conn.fetch(num, "(RFC822)")
            if typ != "OK":
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            sender = _decode(msg.get("From", "")).lower()
            # If the source declares senders, only keep matching mail; else keep all
            # (lets you forward anything in by hand).
            if from_contains and not any(f in sender for f in from_contains):
                continue
            subject = _decode(msg.get("Subject", ""))
            try:
                published = parsedate_to_datetime(msg.get("Date"))
            except Exception:
                published = None
            items.append(
                Item(
                    source_id=source["id"],
                    source_name=source["name"],
                    tier=source.get("tier", 1),
                    url="",  # email has no canonical URL; left blank
                    title=clean_text(subject, 400) or "(no subject)",
                    body=clean_text(_body_text(msg)),
                    published=published,
                    raw_id=_decode(msg.get("Message-ID", "")),
                )
            )
            conn.store(num, "+FLAGS", "\\Seen")
        conn.logout()
    except Exception as exc:  # noqa: BLE001
        log.warning("inbox fetch failed for %s: %s", source["id"], exc)
        return []
    log.info("inbox %s -> %d messages", source["id"], len(items))
    return items
