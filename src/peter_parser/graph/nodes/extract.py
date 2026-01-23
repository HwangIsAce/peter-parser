"""Extract node implementation."""
from typing import Any, Callable, Dict, Optional

from peter_parser_core import ParsedDocument
from peter_parser.graph.states import PipelineState
from peter_parser.impl.extractor.document_enricher import DocumentEnricher
from peter_parser.impl.extractor.chunk_enricher import ChunkEnricher


def create_extract_node(
    enricher: Optional[DocumentEnricher] = None,
) -> Callable[[PipelineState], Dict[str, Any]]:
    """Create an extract node function"""
    if enricher is None:
        enricher = DocumentEnricher()
    
    def extract_node(state: PipelineState) -> Dict[str, Any]:
        """Extract node function for langgraph."""
        parsed_doc = state.get("parsed_document")
        if not parsed_doc:
            raise ValueError("parsed_document is required")
        
        chunk_unit = state.get("chunk_unit")
        
        # Delegate to enricher
        result = enricher.enrich(
            parsed_document=parsed_doc,
            chunk_unit=chunk_unit,
        )
        
        return result
    
    return extract_node


def create_chunk_enrich_node(
    enricher: Optional[ChunkEnricher] = None,
) -> Callable[[PipelineState], Dict[str, Any]]:
    """Create a chunk enrichment node function."""
    if enricher is None:
        enricher = ChunkEnricher()
    
    def chunk_enrich_node(state: PipelineState) -> Dict[str, Any]:
        """Chunk enrichment node function."""
        chunks = state.get("chunks", [])
        if not chunks:
            return {}
        
        chunk_metadata = enricher.enrich_chunks(chunks)
        
        return {
            "chunk_metadata": chunk_metadata,
        }
    
    return chunk_enrich_node