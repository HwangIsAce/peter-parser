"""Chunk metadata enrichment extractor."""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from peter_parser.impl.extractor.structured import StructuredLLM
from peter_parser.common.config import Config

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
        chunks: List[Dict[str, Any]],
    ) -> Dict[int, Dict[str, Any]]:
        """Enrich chunks with metadata.
        
        Args:
            chunks: List of chunk dictionaries
        
        Returns:
            Dict mapping chunk_index to metadata
        """
        chunk_metadata = {}
        
        for chunk in chunks:
            chunk_idx = chunk.get("chunk_index")
            chunk_text = chunk.get("text", "")
            
            # Extract metadata for each chunk
            result = self.llm.structure_output(
                instruction=f"Extract key information from this chunk:\n\n{chunk_text[:2000]}",
                key_attr="name",
                value_attr="description"
            )
            
            chunk_metadata[chunk_idx] = {
                "summary": result.summary,
                "keywords": result.keywords,
            }
        
        return chunk_metadata