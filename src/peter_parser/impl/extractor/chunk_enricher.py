"""Chunk metadata enrichment extractor."""
import asyncio
from typing import Dict, Any, List, Optional, Tuple
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
        Runs all LLM calls in a single event loop to avoid Connection errors when
        using AsyncOpenAI with repeated asyncio.run() (one per chunk).

        Args:
            chunks: List of Chunk objects (read-only, not modified)

        Returns:
            Dict mapping chunk_order to metadata {summary, keywords}
        """
        if not chunks:
            return {}
        return self.llm._run_async(self._enrich_chunks_async(chunks))

    async def _enrich_one(
        self,
        semaphore: asyncio.Semaphore,
        chunk: Chunk,
    ) -> Tuple[int, Dict[str, Any]]:
        """Enrich a single chunk; semaphore limits concurrency. Returns (chunk_order, metadata)."""
        async with semaphore:
            result = await self.llm.astructure_output(
                instruction=f"Extract key information from this chunk:\n\n{chunk.chunk[:2000]}",
                key_attr="name",
                value_attr="description",
            )
            return (
                chunk.chunk_order,
                {"summary": result.summary, "keywords": result.keywords},
            )

    async def _enrich_chunks_async(
        self,
        chunks: List[Chunk],
    ) -> Dict[int, Dict[str, Any]]:
        """Run chunk enrichment in parallel with semaphore; order preserved via gather."""
        max_concurrency = max(1, getattr(Config, "CHUNK_ENRICH_MAX_CONCURRENCY", 5))
        semaphore = asyncio.Semaphore(max_concurrency)
        tasks = [self._enrich_one(semaphore, ch) for ch in chunks]
        results: List[Tuple[int, Dict[str, Any]]] = await asyncio.gather(*tasks)
        return dict(results)