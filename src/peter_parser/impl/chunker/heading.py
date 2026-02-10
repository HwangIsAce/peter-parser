"""Heading prompt-based chunker: 10-page windows, heading1/2/3 structure."""
from __future__ import annotations

import asyncio
import logging
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


logger = logging.getLogger(__name__)


class HeadingChunkItem(BaseModel):
    """Single chunk with heading level and title. Indices are segment-based within the window text."""

    start_index: int = Field(description="0-based segment index where this chunk starts (within the window)")
    end_index: int = Field(description="0-based segment index where this chunk ends (exclusive)")
    level: Literal[1, 2, 3] = Field(description="1=heading1, 2=heading2, 3=heading3")
    title: str = Field(
        description="Heading text for this section (required; do not leave empty when a heading exists)"
    )


class HeadingChunksOutput(BaseModel):
    """LLM response: list of chunks with heading hierarchy for one window."""

    chunks: List[HeadingChunkItem] = Field(
        default_factory=list,
        description="One chunk per section; typically 3-10+ when document has headings",
    )


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


def _dedupe_heading_path(path: List[str]) -> List[str]:
    """Remove consecutive duplicates in heading_path (e.g. [A, B, B] -> [A, B])."""
    if not path:
        return path
    out: List[str] = [path[0]]
    for x in path[1:]:
        if x != out[-1]:
            out.append(x)
    return out


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
        path = _dedupe_heading_path([x for x in [h1, h2, h3] if x])
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

    async def _process_one_window(
        self,
        semaphore: asyncio.Semaphore,
        win_idx: int,
        global_start: int,
        text: str,
        max_pages: int,
    ) -> Tuple[int, int, List[int], List[Dict[str, Any]]]:
        """Process one window; returns (win_idx, global_start, local_b, infos)."""
        async with semaphore:
            try:
                result = await self.llm.astructure_output(
                    instruction=HEADING_CHUNK_USER_PROMPT.format(
                        max_pages=max_pages,
                        text=text,
                    ),
                    user_system_prompt=HEADING_CHUNK_SYSTEM_PROMPT,
                    key_attr="name",
                    value_attr="description",
                )
            except Exception as e:
                logger.exception("Heading chunk LLM call failed (win_idx=%d): %s", win_idx, e)
                result = HeadingChunksOutput(chunks=[])

            n_segments = text.count("\n") + (1 if text.strip() else 0)
            if n_segments >= 15 and len(result.chunks) <= 1:
                logger.warning(
                    "LLM returned only %d chunk(s) for %d segments (win_idx=%d); expected more for heading docs",
                    len(result.chunks),
                    n_segments,
                    win_idx,
                )

            local_b = sorted(set(c.start_index for c in result.chunks if c.start_index > 0))
            infos = _heading_infos_from_items(result.chunks)
            return (win_idx, global_start, local_b, infos)

    def detect_boundaries(self, parsed_document: ParsedDocument) -> List[int]:
        """
        Run LLM per window (element-based, parallel); return global element boundaries and set _last_heading_infos.
        """
        pages = getattr(parsed_document, "pages", None) or []
        elements = getattr(parsed_document, "elements", None) or []
        if not elements or not pages:
            self._last_heading_infos = []
            return []
        max_pages = Config.HEADING_CHUNK_MAX_PAGES
        windows = build_heading_windows(pages, max_pages)

        # Build tasks for windows with content
        tasks_data: List[Tuple[int, int, str]] = []
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
            tasks_data.append((win_idx, global_start, text))

        if not tasks_data:
            self._last_heading_infos = []
            return []

        batch_url = getattr(Config, "OPENAI_BATCH_URL", None) or ""
        use_batch = bool(batch_url and len(tasks_data) > 1)

        if use_batch:
            batch_requests = [
                {
                    "instruction": HEADING_CHUNK_USER_PROMPT.format(
                        max_pages=max_pages,
                        text=text,
                    ),
                    "user_system_prompt": HEADING_CHUNK_SYSTEM_PROMPT,
                    "key_attr": "name",
                    "value_attr": "description",
                }
                for _, _, text in tasks_data
            ]
            try:
                batch_results = self.llm._run_async(
                    self.llm.astructure_output_batch(
                        batch_requests,
                        datamodel=HeadingChunksOutput,
                    )
                )
            except Exception as e:
                logger.exception("Heading chunk batch LLM call failed: %s", e)
                batch_results = [HeadingChunksOutput(chunks=[]) for _ in tasks_data]
            results = []
            for (win_idx, global_start, text), result in zip(tasks_data, batch_results):
                n_segments = text.count("\n") + (1 if text.strip() else 0)
                if n_segments >= 15 and len(result.chunks) <= 1:
                    logger.warning(
                        "LLM returned only %d chunk(s) for %d segments (win_idx=%d)",
                        len(result.chunks),
                        n_segments,
                        win_idx,
                    )
                local_b = sorted(set(c.start_index for c in result.chunks if c.start_index > 0))
                infos = _heading_infos_from_items(result.chunks)
                results.append((win_idx, global_start, local_b, infos))
        else:
            max_concurrency = max(1, getattr(Config, "CHUNKER_LLM_MAX_CONCURRENCY", 5))
            semaphore = asyncio.Semaphore(max_concurrency)
            tasks = [
                self._process_one_window(semaphore, win_idx, global_start, text, max_pages)
                for win_idx, global_start, text in tasks_data
            ]

            async def _gather_all():
                return await asyncio.gather(*tasks)

            results = self.llm._run_async(_gather_all())

        all_boundaries: List[int] = []
        all_heading_infos: List[Dict[str, Any]] = []
        for win_idx, global_start, local_b, infos in results:
            if win_idx > 0:
                all_boundaries.append(global_start)
            for b in local_b:
                all_boundaries.append(global_start + b)
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
        Merges empty chunks into the previous chunk; dedupes consecutive heading_path entries.
        """
        elements = getattr(parsed_document, "elements", None) or []
        if not elements:
            return [], parsed_document
        n_el = len(elements)
        doc_title = doc_title or getattr(parsed_document, "title", None) or ""
        valid_b = [b for b in chunk_boundaries if 0 < b < n_el]
        all_b = [0] + sorted(valid_b) + [n_el]
        raw_chunks: List[Tuple[int, int, str, Dict[str, Any]]] = []
        heading_infos = getattr(self, "_last_heading_infos", []) or []
        for i in range(len(all_b) - 1):
            start_idx, end_idx = all_b[i], all_b[i + 1]
            chunk_el = elements[start_idx:end_idx]
            chunk_text = "\n".join([getattr(el, "text", "") or "" for el in chunk_el])
            extra: Dict[str, Any] = {
                "element_indices": list(range(start_idx, end_idx)),
                "element_ids": [el.element_id for el in chunk_el],
            }
            if i < len(heading_infos):
                hp = heading_infos[i].get("heading_path", [])
                extra["heading1"] = heading_infos[i].get("heading1", "")
                extra["heading2"] = heading_infos[i].get("heading2", "")
                extra["heading3"] = heading_infos[i].get("heading3", "")
                extra["heading_path"] = _dedupe_heading_path(hp) if hp else []
            raw_chunks.append((start_idx, end_idx, chunk_text, extra))

        # Merge empty chunks into next chunk (keeps content; absorbs preceding empties)
        chunks: List[Chunk] = []
        element_chunk_map: Dict[int, str] = {}
        i = 0
        while i < len(raw_chunks):
            start_idx, end_idx, chunk_text, extra = raw_chunks[i]
            merged_start, merged_end = start_idx, end_idx
            merged_extra = dict(extra)
            while chunk_text.strip() == "" and i + 1 < len(raw_chunks):
                _, next_end, _, next_extra = raw_chunks[i + 1]
                merged_end = min(next_end, n_el)
                merged_extra = dict(next_extra)
                merged_extra["element_indices"] = list(
                    range(merged_start, merged_end)
                )
                merged_extra["element_ids"] = [
                    elements[j].element_id for j in range(merged_start, merged_end)
                ]
                i += 1
                _, _, chunk_text, _ = raw_chunks[i]
            merged_end = min(merged_end, n_el)
            merged_text = "\n".join(
                getattr(elements[j], "text", "") or ""
                for j in range(merged_start, merged_end)
            )
            chunk_el = elements[merged_start:merged_end]
            first_page = chunk_el[0].page_number if chunk_el else None
            meta = ChunkMetadata(
                page_number=first_page,
                chunk_size=len(merged_text),
                start_index=merged_start,
                end_index=merged_end - 1,
                extra=merged_extra,
            )
            ch = Chunk(
                uuid=str(uuid.uuid4()),
                doc_title=doc_title,
                chunk=merged_text,
                chunk_order=len(chunks),
                metadata=meta,
            )
            chunks.append(ch)
            for el in chunk_el:
                element_chunk_map[el.element_id] = ch.uuid
            i += 1
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
