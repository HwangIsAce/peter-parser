"""Sample text from parsed_document for LLM-based router."""
from __future__ import annotations

import random
from typing import List, Literal, Optional

from peter_parser.common.config import Config


def sample_router_text(
    parsed_document: object,
    max_pages: Optional[int] = None,
    sample: Literal["random", "uniform"] = "random",
    max_chars: Optional[int] = None,
) -> str:
    """Extract sampled text from parsed_document for router classification.

    If parsed_document has pages, samples up to max_pages (random or uniform).
    Otherwise falls back to content.text.

    Args:
        parsed_document: ParsedDocument with pages and/or content.
        max_pages: Max pages to sample (default: Config.ROUTER_LLM_MAX_PAGES).
        sample: "random" or "uniform" page sampling.
        max_chars: Max chars to return (default: Config.ROUTER_CONTENT_MAX_CHARS).

    Returns:
        Sampled text string for LLM router.
    """
    if max_pages is None:
        max_pages = Config.ROUTER_LLM_MAX_PAGES
    if max_chars is None:
        max_chars = Config.ROUTER_CONTENT_MAX_CHARS

    pages = getattr(parsed_document, "pages", None) or []
    if not pages:
        # Fallback: use content.text
        content = getattr(getattr(parsed_document, "content", None), "text", None) or ""
        return (content or "")[:max_chars]

    total = len(pages)
    n = min(max_pages, total)
    if n >= total:
        indices = list(range(total))
    elif sample == "random":
        indices = sorted(random.sample(range(total), n))
    else:
        step = (total - 1) / (n - 1) if n > 1 else 0
        indices = [int(round(i * step)) for i in range(n)]

    parts: List[str] = []
    for i in indices:
        p = pages[i]
        text = getattr(p, "text", None) or ""
        if text:
            parts.append(text.strip())

    result = "\n\n".join(parts)
    return result[:max_chars]
