"""Render document (PDF) pages to images for VLM routing."""
from __future__ import annotations

import random
from pathlib import Path
from typing import List, Literal, Optional

# PDF magic
PDF_MAGIC = b"%PDF"


def _is_pdf(document: bytes) -> bool:
    return (document or b"")[:4] == PDF_MAGIC


def document_to_page_images(
    document: bytes,
    max_pages: int = 4,
    file_extension: Optional[str] = None,
    sample: Literal["uniform", "random"] = "uniform",
) -> List[bytes]:
    """Render up to max_pages from document, sampled across the document.

    Only PDF is supported. Pages are sampled uniformly (spread across the doc)
    or randomly. Returns list of PNG image bytes.

    Args:
        document: Raw document bytes (PDF).
        max_pages: Max number of pages to sample and render.
        file_extension: Optional hint (e.g. "pdf"); ignored for PDF detection (magic used).
        sample: "uniform" = evenly spaced indices, "random" = random indices.

    Returns:
        List of PNG image bytes (one per sampled page). Empty if not PDF or on error.
    """
    if not document or not _is_pdf(document):
        return []
    try:
        import fitz  # pymupdf  # type: ignore[import-untyped]
    except ImportError:
        return []
    try:
        doc = fitz.open(stream=document, filetype="pdf")
        total = len(doc)
        doc.close()
    except Exception:
        return []
    if total == 0:
        return []
    # Sample page indices (0-based)
    n = min(max_pages, total)
    if n >= total:
        indices = list(range(total))
    elif sample == "random":
        indices = sorted(random.sample(range(total), n))
    else:
        # uniform: evenly spaced
        step = (total - 1) / (n - 1) if n > 1 else 0
        indices = [int(round(i * step)) for i in range(n)]
    out: List[bytes] = []
    try:
        doc = fitz.open(stream=document, filetype="pdf")
        for i in indices:
            page = doc.load_page(i)
            pix = page.get_pixmap(dpi=150, alpha=False)
            out.append(pix.tobytes("png"))
        doc.close()
    except Exception:
        return []
    return out
