"""Map pipeline Chunk to API ResultItem (API spec)."""
from __future__ import annotations

from typing import TYPE_CHECKING, List

from peter_parser.api.schemas.response import ResultItem, ResultItemMetadata

if TYPE_CHECKING:
    from peter_parser_core.common.types import Chunk


def chunk_to_result_item(chunk: "Chunk") -> ResultItem:
    """Map pipeline Chunk to API ResultItem."""
    meta = getattr(chunk, "metadata", None) or {}
    extra = getattr(meta, "extra", None) or {}
    page_number = getattr(meta, "page_number", None)
    doc_page: List[int] = []
    if page_number is not None:
        doc_page = [page_number]
    if isinstance(extra.get("page_numbers"), list):
        doc_page = extra["page_numbers"]
    doc_title = getattr(chunk, "doc_title", None) or ""
    # Heading chunker sets heading_path (list); expose as category for API when present
    category = extra.get("category", []) if isinstance(extra.get("category"), list) else []
    if isinstance(extra.get("heading_path"), list) and extra["heading_path"]:
        category = extra["heading_path"]
    return ResultItem(
        uuid=getattr(chunk, "uuid", "") or "",
        doc_title=doc_title if isinstance(doc_title, str) else str(doc_title),
        chunk=getattr(chunk, "chunk", "") or "",
        chunk_order=getattr(chunk, "chunk_order", 0) or 0,
        metadata=ResultItemMetadata(
            proj_title="",
            doc_title=doc_title if isinstance(doc_title, str) else str(doc_title),
            process_title="",
            doc_unit=extra.get("doc_unit", "") if isinstance(extra.get("doc_unit"), str) else "",
            doc_page=doc_page,
            category=category,
            images=[],  # Fill from extra.images if needed
        ),
    )


def chunks_to_result_response(chunks: List["Chunk"]) -> "ResultResponse":
    """Map list of Chunks to ResultResponse."""
    from peter_parser.api.schemas.response import ResultResponse

    return ResultResponse(chunks=[chunk_to_result_item(c) for c in chunks])
