"""PDF adapter — for Town Meeting warrants, budget books, agendas/minutes.

Phase-1 status: the extraction core works (pypdf), but discovering *which* PDFs
to pull from the Document Portal / Agenda Center is left for Phase 2, because the
site blocks automated listing. For now, pass explicit PDF urls via
source["params"]["urls"] and this will fetch + extract them.
"""
from __future__ import annotations

import logging

import requests

from .base import Item, clean_text, now_utc

log = logging.getLogger("adapters.pdf")


def _extract(pdf_bytes: bytes, limit: int = 8000) -> str:
    try:
        import io

        from pypdf import PdfReader  # lazy import

        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = " ".join((page.extract_text() or "") for page in reader.pages)
        return clean_text(text, limit)
    except Exception as exc:  # noqa: BLE001
        log.warning("pdf extract failed: %s", exc)
        return ""


def fetch(source: dict, user_agent: str, timeout: int = 20) -> list[Item]:
    urls = source.get("params", {}).get("urls", [])
    if not urls:
        log.info("pdf %s: no urls configured (Phase 2)", source["id"])
        return []
    items: list[Item] = []
    headers = {"User-Agent": user_agent}
    for u in urls:
        try:
            r = requests.get(u, headers=headers, timeout=timeout)
            r.raise_for_status()
            body = _extract(r.content)
        except Exception as exc:  # noqa: BLE001
            log.warning("pdf fetch failed (%s): %s", u, exc)
            continue
        if not body:
            continue
        items.append(
            Item(
                source_id=source["id"],
                source_name=source["name"],
                tier=source.get("tier", 1),
                url=u,
                title=u.rsplit("/", 1)[-1],
                body=body,
                published=now_utc(),
                raw_id=u,
            )
        )
    log.info("pdf %s -> %d docs", source["id"], len(items))
    return items
