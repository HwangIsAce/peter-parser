"""Heading prompt-based chunker: 10-page windows, heading1/2/3 structure (Phase 1: schema + window util)."""
from __future__ import annotations

from typing import List, Literal, Tuple, Any

from pydantic import BaseModel, Field

from peter_parser.common.config import Config


# -----------------------------------------------------------------------------
# LLM structured output schema (Phase 1.2)
# -----------------------------------------------------------------------------


class HeadingChunkItem(BaseModel):
    """Single chunk with heading level and title. Indices are segment-based within the window text."""

    start_index: int = Field(description="0-based segment index where this chunk starts (within the window)")
    end_index: int = Field(description="0-based segment index where this chunk ends (exclusive)")
    level: Literal[1, 2, 3] = Field(description="1=heading1, 2=heading2, 3=heading3")
    title: str = Field(description="Heading text for this chunk (e.g. section title)")


class HeadingChunksOutput(BaseModel):
    """LLM response: list of chunks with heading hierarchy for one window."""

    chunks: List[HeadingChunkItem] = Field(default_factory=list, description="Chunks in order")


# -----------------------------------------------------------------------------
# Window building (Phase 1.1)
# -----------------------------------------------------------------------------


def build_heading_windows(
    pages: List[Any],
    max_pages: int | None = None,
) -> List[Tuple[int, int, str]]:
    """
    Split pages into windows of at most max_pages. Each window is (page_start, page_end, text).

    Args:
        pages: List of page-like objects with .text (e.g. parsed_document.pages).
        max_pages: Max pages per window; default from Config.HEADING_CHUNK_MAX_PAGES.

    Returns:
        List of (page_start_idx, page_end_idx, concatenated_text). page_end is exclusive.
    """
    if max_pages is None:
        max_pages = Config.HEADING_CHUNK_MAX_PAGES
    if not pages:
        return []
    out: List[Tuple[int, int, str]] = []
    for start in range(0, len(pages), max_pages):
        end = min(start + max_pages, len(pages))
        window_pages = pages[start:end]
        parts = [getattr(p, "text", None) or "" for p in window_pages]
        text = "\n\n".join(parts)
        out.append((start, end, text))
    return out
