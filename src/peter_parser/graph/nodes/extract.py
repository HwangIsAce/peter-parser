"""Extract node implementation."""
import sys
from typing import Any, Callable, Dict, Optional

from peter_parser_core import ParsedDocument
from peter_parser.common.config import Config
from peter_parser.graph.states import (
    PipelineState,
    DOCUMENT_TYPE_SLIDE,
    DOCUMENT_TYPE_HEADING,
)
from peter_parser.impl.extractor.document_enricher import DocumentEnricher
from peter_parser.impl.extractor.chunk_enricher import ChunkEnricher


def create_extract_node(
    enricher: Optional[DocumentEnricher] = None,
) -> Callable[[PipelineState], Dict[str, Any]]:
    """Create an extract node function"""
    if enricher is None:
        enricher = DocumentEnricher()
    
    def extract_node(state: PipelineState) -> Dict[str, Any]:
        """Extract node function for langgraph.
        
        Note: This does NOT modify parsed_document. Enrichment data is returned
        separately and linked via keys (document_summary, item_metadata).
        """
        if Config.PIPELINE_PROGRESS:
            print("[Pipeline] Step: enrich (document summary + page metadata)...", file=sys.stderr, flush=True)
        parsed_doc = state.get("parsed_document")
        if not parsed_doc:
            raise ValueError("parsed_document is required")

        # Resolve chunk_unit for enricher: document_type (4-case) maps to page/element.
        document_type = state.get("document_type")
        chunk_unit = state.get("chunk_unit")
        if document_type == DOCUMENT_TYPE_SLIDE:
            chunk_unit = "page"
        elif document_type == DOCUMENT_TYPE_HEADING:
            chunk_unit = "element"
        # else: use state chunk_unit (or None → enricher default)

        # Delegate to enricher (does not modify parsed_document)
        result = enricher.enrich(
            parsed_document=parsed_doc,
            chunk_unit=chunk_unit,
        )
        
        # Return enrichment data (linked, not attached to parsed_document)
        # parsed_document remains unchanged in state
        return {
            "document_summary": result.get("document_summary"),
            "item_metadata": result.get("item_metadata", {}),
            "chunk_unit": result.get("chunk_unit", chunk_unit),
        }
    
    return extract_node


def create_chunk_enrich_node(
    enricher: Optional[ChunkEnricher] = None,
) -> Callable[[PipelineState], Dict[str, Any]]:
    """Create a chunk enrichment node function."""
    if enricher is None:
        enricher = ChunkEnricher()
    
    def chunk_enrich_node(state: PipelineState) -> Dict[str, Any]:
        """Chunk enrichment node function.
        
        Does NOT modify chunks. Returns chunk_metadata separately, linked by chunk_order.
        """
        if Config.PIPELINE_PROGRESS:
            chunks_preview = state.get("chunks", [])
            n = len(chunks_preview)
            print(f"[Pipeline] Step: chunk_enrich ({n} chunks, LLM summary+keywords)...", file=sys.stderr, flush=True)
        chunks = state.get("chunks", [])
        if not chunks:
            return {}
        
        # Enrich chunks (does not modify chunks, returns metadata separately)
        chunk_metadata = enricher.enrich_chunks(chunks)
        
        # Return chunk_metadata only (linked by chunk_order, not attached to chunks)
        # chunks remain unchanged in state
        return {
            "chunk_metadata": chunk_metadata,
        }
    
    return chunk_enrich_node