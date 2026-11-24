"""FAQ keyword suggest endpoint.

GET /faq/suggest?q=<keyword>[&limit=20]

Searches FAQ documents (document_type == "faq", is_active == true) loaded from
data/seed/documents.json.  Matching is simple case-folded substring search over
title and body.  Results are ranked by:
  title_hit_count * 2 + body_hit_count * 1  (descending)
Ties are broken by faq_id ascending (preserves original order).

The customer-facing answer is extracted from the body field:
  body has the form "質問: …\n回答: <answer text>\n窓口対応: …"
If either marker is missing, `answer` is returned as null and the item is flagged
as `answer_unavailable=True` so the UI can show a warning instead of a copy button.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from helpdesk.config import get_settings

logger = logging.getLogger("helpdesk")

router = APIRouter(tags=["faq"])

# ---------------------------------------------------------------------------
# Answer extraction
# ---------------------------------------------------------------------------
_ANSWER_START = "\n回答: "
_ANSWER_END = "\n窓口対応:"


def _extract_answer(body: str) -> str | None:
    """Extract the customer-facing answer from a FAQ body field.

    Returns None if either marker is not found (signals answer_unavailable).
    """
    start_idx = body.find(_ANSWER_START)
    if start_idx == -1:
        return None
    answer_start = start_idx + len(_ANSWER_START)
    end_idx = body.find(_ANSWER_END, answer_start)
    if end_idx == -1:
        return None
    return body[answer_start:end_idx].strip()


# ---------------------------------------------------------------------------
# Document loading (called once at startup via app.state)
# ---------------------------------------------------------------------------

def load_faq_documents(seed_data_dir: str) -> list[dict[str, Any]]:
    """Load and filter FAQ documents from documents.json."""
    path = Path(seed_data_dir) / "documents.json"
    try:
        raw: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning("FAQ documents file not found: %s", path)
        return []
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse FAQ documents: %s", exc)
        return []

    return [
        doc for doc in raw
        if doc.get("document_type") == "faq" and doc.get("is_active") is True
    ]


# ---------------------------------------------------------------------------
# Scoring / search
# ---------------------------------------------------------------------------

def _score(doc: dict[str, Any], keyword: str) -> int:
    """Return title_hits*2 + body_hits*1 for a single keyword."""
    kw = keyword.casefold()
    title_hits = (doc.get("title") or "").casefold().count(kw)
    body_hits = (doc.get("body") or "").casefold().count(kw)
    return title_hits * 2 + body_hits


def search_faq(
    docs: list[dict[str, Any]],
    query: str,
    limit: int,
) -> list[dict[str, Any]]:
    """Return up to `limit` FAQ docs that match query, sorted by relevance."""
    keywords = [kw for kw in query.casefold().split() if kw]
    if not keywords:
        return []

    scored: list[tuple[int, str, dict[str, Any]]] = []
    for doc in docs:
        total = sum(_score(doc, kw) for kw in keywords)
        if total > 0:
            scored.append((total, doc.get("faq_id") or "", doc))

    # Sort: score descending, faq_id ascending for ties
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [doc for _, _, doc in scored[:limit]]


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class FaqSuggestItem(BaseModel):
    faq_id: str
    title: str
    answer: str | None
    answer_unavailable: bool
    category: str | None


class FaqSuggestResponse(BaseModel):
    items: list[FaqSuggestItem]


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get("/faq/suggest", response_model=FaqSuggestResponse)
def suggest_faq(
    request: Request,
    q: str = Query(min_length=1, max_length=200, description="検索キーワード"),
    limit: int = Query(default=20, ge=1, le=50, description="最大返却件数"),
) -> FaqSuggestResponse:
    """Return FAQ candidates that match the keyword query."""
    docs: list[dict[str, Any]] = getattr(request.app.state, "faq_documents", [])
    matched = search_faq(docs, q, limit)

    items: list[FaqSuggestItem] = []
    for doc in matched:
        answer = _extract_answer(doc.get("body") or "")
        items.append(
            FaqSuggestItem(
                faq_id=doc.get("faq_id") or "",
                title=doc.get("title") or "",
                answer=answer,
                answer_unavailable=(answer is None),
                category=doc.get("category"),
            )
        )

    return FaqSuggestResponse(items=items)
