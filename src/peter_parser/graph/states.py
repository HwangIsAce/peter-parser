"""Shared state definitions for pipeline execution."""

from typing_extensions import NotRequired
from typing import TypedDict, Optional, Union, Literal, Dict, Any, List

from peter_parser_core import ParsedDocument
from peter_parser_core.common.types import Chunk

# 4-case routing: LLM or caller sets one of these.
DocumentType = Literal["heading", "plain", "slide", "lifelog"]

# Routing constants (for use in flow/chunk nodes).
DOCUMENT_TYPE_HEADING = "heading"
DOCUMENT_TYPE_PLAIN = "plain"
DOCUMENT_TYPE_SLIDE = "slide"
DOCUMENT_TYPE_LIFELOG = "lifelog"


class PipelineState(TypedDict):
    """Pipeline execution state"""
    
    # --------------- parse stage ---------------
    
    document: Union[str, bytes]
    parsed_document: NotRequired[Optional[ParsedDocument]]

    # --------------- enrichment stage ---------------
    
    # 4-case document type (set by LLM router or by invoke(document_type=...)).
    document_type: NotRequired[Optional[DocumentType]]
    chunk_unit: NotRequired[Literal["page", "element"]]  # Legacy; prefer document_type when present.
    
    document_summary: NotRequired[Optional[str]]  # Linked to document (1:1). Not stored in ParsedDocument.
    item_metadata: NotRequired[Dict[int, Dict[str, Any]]]  # Linked to elements; key = element_id. Not stored in ParsedDocument.
    
    # --------------- chunk stage ---------------
    chunk_boundaries: NotRequired[List[int]]
    
    chunks: NotRequired[List[Chunk]]  # Changed from List[Dict[str, Any]]
    chunk_metadata: NotRequired[Dict[int, Dict[str, Any]]]  # Linked to chunks; key = chunk_order. Not stored in Chunk.

    # --------------- export stage ---------------
    export_json: NotRequired[Optional[str]]  # JSON-serialized chunks for export