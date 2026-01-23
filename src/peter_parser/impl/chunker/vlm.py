"""VLM-based chunker implementation (production)."""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from peter_parser_core import ParsedDocument
from peter_parser.common.config import Config
from peter_parser.impl.extractor.structured import StructuredLLM
from peter_parser.prompts.chunking import (
    BOUNDARY_DETECTION_SYSTEM_PROMPT,
    BOUNDARY_DETECTION_USER_PROMPT,
)


class ChunkBoundaries(BaseModel):
    """Chunk boundaries model."""
    boundaries: List[int] = Field(
        description=Config.SCHEMA_DESCRIPTIONS["chunk_boundaries"]
    )


class VLMChunker:
    """VLM-based chunker for page-level chunking (PPTX, etc.)."""
    
    def __init__(self, llm: Optional[StructuredLLM] = None):
        """Initialize VLMChunker.
        
        Args:
            llm: StructuredLLM instance
        """
        if llm is None:
            llm = StructuredLLM(datamodel=ChunkBoundaries)
        self.llm = llm
    
    def detect_boundaries(
        self,
        parsed_document: ParsedDocument,
        document_summary: str,
        item_metadata: Dict[int, Dict[str, Any]],
    ) -> List[int]:
        """Detect chunk boundaries using LLM (page-based).
        
        Args:
            parsed_document: Parsed document
            document_summary: Document summary
            item_metadata: Metadata per page
        
        Returns:
            List of page indices where new chunks start (0-based)
        """
        total_pages = len(parsed_document.pages)
        
        if total_pages == 0:
            return []
        
        # Format metadata
        metadata_lines = []
        for idx, meta in sorted(item_metadata.items()):
            metadata_lines.append(f"  page {idx}: {meta}")
        metadata_str = "\n".join(metadata_lines) if metadata_lines else "No metadata"
        
        instruction = BOUNDARY_DETECTION_USER_PROMPT.format(
            document_summary=document_summary or "No summary",
            item_metadata=metadata_str,
            chunk_unit="page",
            total_items=total_pages
        )
        
        result = self.llm.structure_output(
            instruction=instruction,
            user_system_prompt=BOUNDARY_DETECTION_SYSTEM_PROMPT,
            key_attr="name",
            value_attr="description"
        )
        
        # Validate and clean boundaries
        boundaries = [b for b in result.boundaries if 0 < b < total_pages]
        return sorted(list(set(boundaries)))
    
    def chunk(
        self,
        parsed_document: ParsedDocument,
        chunk_boundaries: List[int],
    ) -> List[Dict[str, Any]]:
        """Create chunks from parsed document (page-based).
        
        Args:
            parsed_document: Parsed document
            chunk_boundaries: List of page indices where new chunks start
        
        Returns:
            List of chunk dictionaries
        """
        pages = parsed_document.pages
        
        if not pages:
            return []
        
        # Create boundaries list (0 + boundaries + end)
        all_boundaries = [0] + sorted(chunk_boundaries) + [len(pages)]
        
        chunks = []
        for i in range(len(all_boundaries) - 1):
            start_idx = all_boundaries[i]
            end_idx = all_boundaries[i + 1]
            
            # Extract pages for this chunk
            chunk_pages = pages[start_idx:end_idx]
            chunk_text = "\n\n".join([page.text for page in chunk_pages])
            chunk_indices = [page.page_number - 1 for page in chunk_pages]  # 0-based
            
            chunks.append({
                "text": chunk_text,
                "start_index": start_idx,
                "end_index": end_idx - 1,
                "indices": chunk_indices,
                "chunk_index": i,
            })
        
        return chunks