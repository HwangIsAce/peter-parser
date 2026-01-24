"""Chunk metadata enrichment extractor."""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from peter_parser.impl.extractor.structured import StructuredLLM
from peter_parser.common.config import Config
from peter_parser_core.common.types import Chunk

class ChunkMetadata(BaseModel):
    """Chunk metadata model."""
    summary: Optional[str] = Field(
        default=None, 
        description=Config.SCHEMA_DESCRIPTIONS["chunk_summary"]
    )
    keywords: List[str] = Field(
        default_factory=list, 
        description=Config.SCHEMA_DESCRIPTIONS["chunk_keywords"]
    )

class ChunkEnricher:
    """Extractor for chunk-level metadata enrichment."""
    
    def __init__(self, llm: Optional[StructuredLLM] = None):
        """Initialize ChunkEnricher."""
        if llm is None:
            llm = StructuredLLM(datamodel=ChunkMetadata)
        self.llm = llm
    
    def enrich_chunks(
        self,
        chunks: List[Chunk],
    ) -> Dict[int, Dict[str, Any]]:
        """Enrich chunks with metadata.
        
        Does NOT modify chunks. Returns metadata separately, linked by chunk_order.
        
        Args:
            chunks: List of Chunk objects (read-only, not modified)
        
        Returns:
            Dict mapping chunk_order to metadata {summary, keywords}
        """
        chunk_metadata = {}
        
        for chunk in chunks:
            chunk_idx = chunk.chunk_order
            chunk_text = chunk.chunk
            
            # Extract metadata for each chunk
            result = self.llm.structure_output(
                instruction=f"Extract key information from this chunk:\n\n{chunk_text[:2000]}",
                key_attr="name",
                value_attr="description"
            )
            
            # Store metadata separately (linked by chunk_order, not attached to chunk)
            chunk_metadata[chunk_idx] = {
                "summary": result.summary,
                "keywords": result.keywords,
            }
        
        return chunk_metadata