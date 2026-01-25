"""Chunk node implementation."""
from typing import Any, Callable, Dict, Optional

from peter_parser.graph.states import PipelineState
from peter_parser.impl.chunker.vlm import VLMChunker
from peter_parser.impl.chunker.lumber import LumberChunker
from peter_parser.common.config import Config

def create_chunk_node(
    chunker: Optional[Any] = None,
) -> Callable[[PipelineState], Dict[str, Any]]:
    """Create a chunk node function.
    
    Args:
        chunker: VLMChunker instance
    
    Returns:
        Node function for langgraph
    """
    def chunk_node(state: PipelineState) -> Dict[str, Any]:
        """Chunk node function for langgraph."""
        parsed_document = state.get("parsed_document")
        if not parsed_document:
            raise ValueError("parsed_document is required")
        
        # Get enrichment data from state (linked, not from parsed_document)
        chunk_unit = state.get("chunk_unit") or Config.DEFAULT_CHUNK_UNIT
        document_summary = state.get("document_summary", "")
        item_metadata = state.get("item_metadata", {})
        
        # Initialize chunker if needed
        if chunker is not None:
            current_chunker = chunker
        elif chunk_unit == "page":
            current_chunker = VLMChunker()
        else:
            current_chunker = LumberChunker()
        
        # Detect boundaries (uses linked document_summary and item_metadata from state)
        if chunk_unit == "page":
            boundaries = current_chunker.detect_boundaries(
                parsed_document=parsed_document,
                document_summary=document_summary,
                item_metadata=item_metadata,
            )
        else:
            boundaries = current_chunker.detect_boundaries(
                parsed_document=parsed_document,
            )
        
        # Create chunks (returns chunks and updated parsed_document)
        chunks, updated_parsed_document = current_chunker.chunk(
            parsed_document=parsed_document,
            chunk_boundaries=boundaries,
            doc_title=getattr(parsed_document, "title", None),
        )
        
        return {
            "parsed_document": updated_parsed_document,
            "chunk_boundaries": boundaries,
            "chunks": chunks,
        }
    
    return chunk_node