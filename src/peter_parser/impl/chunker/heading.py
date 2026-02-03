"""Heading prompt-based chunker: 10-page windows, heading1/2/3 structure."""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field

from peter_parser.common.config import Config
from peter_parser.impl.extractor.structured import StructuredLLM
from peter_parser.prompts.heading_chunking import (
    HEADING_CHUNK_SYSTEM_PROMPT,
    HEADING_CHUNK_USER_PROMPT,
)

from peter_parser_core import ParsedDocument
from peter_parser_core.common.types import Chunk, ChunkMetadata, Element


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


# -----------------------------------------------------------------------------
# HeadingPromptChunker (Phase 2)
# -----------------------------------------------------------------------------


def _elements_in_page_range(
    elements: List[Any],
    page_start_0based: int,
    page_end_0based_excl: int,
) -> Tuple[List[int], List[Any]]:
    """Return (global_indices, window_elements) for elements in [page_start+1, page_end] (1-based)."""
    # page_end_0based_excl is exclusive; 1-based page numbers are page_start+1 .. page_end
    lo = page_start_0based + 1
    hi = page_end_0based_excl  # inclusive 1-based
    indices = [i for i, el in enumerate(elements) if lo <= getattr(el, "page_number", 0) <= hi]
    return indices, [elements[i] for i in indices]


def _heading_infos_from_items(items: List[HeadingChunkItem]) -> List[Dict[str, Any]]:
    """Build list of {heading1, heading2, heading3, heading_path} per chunk from LLM items."""
    h1, h2, h3 = "", "", ""
    infos: List[Dict[str, Any]] = []
    for c in items:
        if c.level == 1:
            h1, h2, h3 = c.title, "", ""
        elif c.level == 2:
            h2, h3 = c.title, ""
        else:
            h3 = c.title
        path = [x for x in [h1, h2, h3] if x]
        infos.append({
            "heading1": h1,
            "heading2": h2,
            "heading3": h3,
            "heading_path": path,
        })
    return infos


class HeadingPromptChunker:
    """Chunker for heading docs: up to 10 pages per window, LLM extracts heading1/2/3 and boundaries."""

    def __init__(self, llm: Optional[StructuredLLM] = None):
        if llm is None:
            llm = StructuredLLM(datamodel=HeadingChunksOutput)
        self.llm = llm
        self._last_heading_infos: List[Dict[str, Any]] = []

    def detect_boundaries(self, parsed_document: ParsedDocument) -> List[int]:
        """
        Run LLM per window (element-based); return global element boundaries and set _last_heading_infos.
        """
        pages = getattr(parsed_document, "pages", None) or []
        elements = getattr(parsed_document, "elements", None) or []
        if not elements or not pages:
            self._last_heading_infos = []
            return []
        max_pages = Config.HEADING_CHUNK_MAX_PAGES
        windows = build_heading_windows(pages, max_pages)
        all_boundaries: List[int] = []
        all_heading_infos: List[Dict[str, Any]] = []
        for win_idx, (page_start, page_end, _) in enumerate(windows):
            global_indices, window_elements = _elements_in_page_range(
                elements, page_start, page_end
            )
            if not window_elements:
                continue
            global_start = global_indices[0]
            text = "\n".join(
                f"ID {i}: {getattr(el, 'text', '') or ''}" for i, el in enumerate(window_elements)
            )
            if not text.strip():
                continue
            instruction = HEADING_CHUNK_USER_PROMPT.format(
                max_pages=max_pages,
                text=text,
            )
            try:
                result = self.llm.structure_output(
                    instruction=instruction,
                    user_system_prompt=HEADING_CHUNK_SYSTEM_PROMPT,
                    key_attr="name",
                    value_attr="description",
                )
            except Exception:
                result = HeadingChunksOutput(chunks=[])
            local_b = sorted(set(c.start_index for c in result.chunks if c.start_index > 0))
            if win_idx > 0:
                all_boundaries.append(global_start)
            for b in local_b:
                all_boundaries.append(global_start + b)
            infos = _heading_infos_from_items(result.chunks)
            all_heading_infos.extend(infos)
        self._last_heading_infos = all_heading_infos
        return sorted(list(set(all_boundaries)))

    def chunk(
        self,
        parsed_document: ParsedDocument,
        chunk_boundaries: List[int],
        doc_title: Optional[str] = None,
    ) -> Tuple[List[Chunk], ParsedDocument]:
        """Create chunks from boundaries; add heading hierarchy to metadata.extra.

        extra keys (heading docs only): heading1, heading2, heading3 (str; empty if absent),
        heading_path (list of strings, e.g. [h1, h2, h3]). Export and API may use these.
        """
        elements = getattr(parsed_document, "elements", None) or []
        if not elements:
            return [], parsed_document
        doc_title = doc_title or getattr(parsed_document, "title", None) or ""
        all_b = [0] + sorted(chunk_boundaries) + [len(elements)]
        chunks: List[Chunk] = []
        element_chunk_map: Dict[int, str] = {}
        heading_infos = getattr(self, "_last_heading_infos", []) or []
        for i in range(len(all_b) - 1):
            start_idx, end_idx = all_b[i], all_b[i + 1]
            chunk_el = elements[start_idx:end_idx]
            chunk_text = "\n".join([getattr(el, "text", "") or "" for el in chunk_el])
            first_page = chunk_el[0].page_number if chunk_el else None
            extra: Dict[str, Any] = {
                "element_indices": list(range(start_idx, end_idx)),
                "element_ids": [el.element_id for el in chunk_el],
            }
            if i < len(heading_infos):
                extra["heading1"] = heading_infos[i].get("heading1", "")
                extra["heading2"] = heading_infos[i].get("heading2", "")
                extra["heading3"] = heading_infos[i].get("heading3", "")
                extra["heading_path"] = heading_infos[i].get("heading_path", [])
            meta = ChunkMetadata(
                page_number=first_page,
                chunk_size=len(chunk_text),
                start_index=start_idx,
                end_index=end_idx - 1,
                extra=extra,
            )
            ch = Chunk(
                uuid=str(uuid.uuid4()),
                doc_title=doc_title,
                chunk=chunk_text,
                chunk_order=i,
                metadata=meta,
            )
            chunks.append(ch)
            for el in chunk_el:
                element_chunk_map[el.element_id] = ch.uuid
        updated_el: List[Element] = []
        for el in parsed_document.elements:
            if el.element_id in element_chunk_map:
                updated_el.append(
                    el.model_copy(update={"chunk_uuid": element_chunk_map[el.element_id]})
                )
            else:
                updated_el.append(el)
        updated_doc = parsed_document.model_copy(update={"elements": updated_el})
        return chunks, updated_doc
