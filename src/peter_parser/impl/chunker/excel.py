"""Excel chunker: sheet-based or row-based chunking."""
from __future__ import annotations

import uuid
from typing import List, Optional, Tuple

from peter_parser.common.config import Config
from peter_parser_core import ParsedDocument
from peter_parser_core.common.types import Chunk, ChunkMetadata


def _build_excel_units(parsed_document: ParsedDocument) -> List[Tuple[int, str]]:
    """Build chunk units from Excel pages. Each unit is (page_number, text).

    - EXCEL_CHUNK_ROWS > 0: group rows into units of that size
    - Else: one unit per sheet (page)
    """
    pages = getattr(parsed_document, "pages", None) or []
    if not pages:
        return []
    rows_per_chunk = getattr(Config, "EXCEL_CHUNK_ROWS", 0) or 0
    units: List[Tuple[int, str]] = []

    for page in pages:
        page_num = getattr(page, "page_number", 1)
        text = getattr(page, "text", "") or ""
        lines = [ln for ln in (text or "").strip().split("\n") if ln.strip()]

        if rows_per_chunk > 0:
            for i in range(0, len(lines), rows_per_chunk):
                chunk_lines = lines[i : i + rows_per_chunk]
                units.append((page_num, "\n".join(chunk_lines)))
        else:
            units.append((page_num, text.strip() if text else ""))

    return units


class ExcelChunker:
    """Chunker for Excel: sheet-based (default) or row-based via EXCEL_CHUNK_ROWS."""

    def __init__(self) -> None:
        self._last_units: List[Tuple[int, str]] = []

    def detect_boundaries(self, parsed_document: ParsedDocument) -> List[int]:
        """Compute chunk boundaries. Boundaries are start indices of chunks (excl. first)."""
        self._last_units = _build_excel_units(parsed_document)
        n = len(self._last_units)
        if n <= 1:
            return []
        return list(range(1, n))

    def chunk(
        self,
        parsed_document: ParsedDocument,
        chunk_boundaries: List[int],
        doc_title: Optional[str] = None,
    ) -> Tuple[List[Chunk], ParsedDocument]:
        """Create chunks from units. parsed_document is returned unchanged (no elements)."""
        units = getattr(self, "_last_units", None) or _build_excel_units(parsed_document)
        if not units:
            return [], parsed_document

        all_b = [0] + sorted(chunk_boundaries) + [len(units)]
        doc_title = doc_title or getattr(parsed_document, "title", None) or ""
        sheet_names = (parsed_document.metadata or {}).get("sheet_names") or []
        chunks: List[Chunk] = []

        for i in range(len(all_b) - 1):
            start_idx, end_idx = all_b[i], all_b[i + 1]
            unit_slice = units[start_idx:end_idx]
            chunk_text = "\n\n".join(t for _, t in unit_slice if t.strip())
            first_page = unit_slice[0][0] if unit_slice else None
            sheet_name = ""
            if sheet_names and first_page and 1 <= first_page <= len(sheet_names):
                sheet_name = sheet_names[first_page - 1]

            meta = ChunkMetadata(
                page_number=first_page,
                chunk_size=len(chunk_text),
                start_index=start_idx,
                end_index=end_idx - 1,
                extra={
                    "excel": {"sheet_name": sheet_name, "unit_range": [start_idx, end_idx]},
                },
            )
            ch = Chunk(
                uuid=str(uuid.uuid4()),
                doc_title=doc_title,
                chunk=chunk_text,
                chunk_order=i,
                metadata=meta,
            )
            chunks.append(ch)

        return chunks, parsed_document
