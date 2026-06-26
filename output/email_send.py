"""Send the digest by email over SMTP (e.g. Gmail with an app password).

Optional: if EMAIL_ENABLED is false, run.py skips this. The HTML body is the same
document written to the Pages site.
"""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage
from datetime import datetime

log = logging.getLogger("output.email")


def send(html_body: str, cfg, item_count: int) -> bool:
    if not getattr(cfg, "EMAIL_ENABLED", False):
        log.info("email disabled; skipping send")
        return False

    today = datetime.now().strftime("%b %-d")
    msg = EmailMessage()
    msg["Subject"] = f"Littleton Signal — {today} ({item_count} item{'s' if item_count != 1 else ''})"
    msg["From"] = cfg.SMTP_USER
    msg["To"] = cfg.DIGEST_TO
    msg.set_content("This briefing is best viewed as HTML. See the linked digest page.")
    if cfg.SITE_BASE_URL:
        msg.get_payload()  # text part exists
    msg.add_alternative(html_body, subtype="html")

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(cfg.SMTP_HOST, cfg.SMTP_PORT, context=ctx) as server:
            server.login(cfg.SMTP_USER, cfg.SMTP_PASSWORD)
            server.send_message(msg)
        log.info("email sent to %s", cfg.DIGEST_TO)
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("email send failed: %s", exc)
        return False
