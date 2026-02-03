"""VLM-based chunker implementation (production)."""
import uuid
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from peter_parser_core import ParsedDocument
from peter_parser_core.common.types import Chunk, ChunkMetadata
from peter_parser.common.config import Config
from peter_parser.common.prompt_store import (
    get_prompt,
    PROMPT_KEY_VLM_BOUNDARY_SYSTEM,
    PROMPT_KEY_VLM_BOUNDARY_USER,
)
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
            parsed_document: Parsed document (used for structure info like page count)
            document_summary: Document-level summary (linked to document)
            item_metadata: Metadata dict with element_id as key (linked to elements)
        
        Returns:
            List of page indices where new chunks start (0-based)
        """
        total_pages = len(parsed_document.pages)
        
        if total_pages == 0:
            return []
        
        # Build page-level view for prompt: item_metadata is keyed by element_id.
        # For each page_index, pick one element on that page and use its metadata.
        metadata_lines = []
        if hasattr(parsed_document, "elements") and parsed_document.elements:
            for page_index in range(total_pages):
                page_number = page_index + 1
                meta = None
                for el in parsed_document.elements:
                    if el.page_number == page_number and el.element_id in item_metadata:
                        meta = item_metadata[el.element_id]
                        break
                if meta is not None:
                    metadata_lines.append(f"  page {page_index}: {meta}")
        metadata_str = "\n".join(metadata_lines) if metadata_lines else "No metadata"

        system_prompt = get_prompt(PROMPT_KEY_VLM_BOUNDARY_SYSTEM) or BOUNDARY_DETECTION_SYSTEM_PROMPT
        user_prompt_template = get_prompt(PROMPT_KEY_VLM_BOUNDARY_USER) or BOUNDARY_DETECTION_USER_PROMPT
        instruction = user_prompt_template.format(
            document_summary=document_summary or "No summary",
            item_metadata=metadata_str,
            chunk_unit="page",
            total_items=total_pages
        )

        result = self.llm.structure_output(
            instruction=instruction,
            user_system_prompt=system_prompt,
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
        doc_title: Optional[str] = None,
    ) -> tuple[List[Chunk], ParsedDocument]:
        """Create chunks from parsed document (page-based).
        
        Args:
            parsed_document: Parsed document
            chunk_boundaries: List of page indices where new chunks start
            doc_title: Document title (optional, defaults to empty string)
        
        Returns:
            Tuple of (List[Chunk], updated ParsedDocument with element.chunk_uuid set)
        """
        pages = parsed_document.pages
        
        if not pages:
            return [], parsed_document
        
        # Get document title
        if doc_title is None:
            doc_title = getattr(parsed_document, 'title', '') or ''
        
        # Create boundaries list (0 + boundaries + end)
        all_boundaries = [0] + sorted(chunk_boundaries) + [len(pages)]
        
        chunks = []
        element_chunk_map = {}  # element_id -> chunk_uuid mapping
        
        for i in range(len(all_boundaries) - 1):
            start_idx = all_boundaries[i]
            end_idx = all_boundaries[i + 1]
            
            # Extract pages for this chunk
            chunk_pages = pages[start_idx:end_idx]
            chunk_text = "\n\n".join([page.text for page in chunk_pages])
            
            # Get first page number (1-based)
            first_page_number = chunk_pages[0].page_number if chunk_pages else None
            chunk_size = len(chunk_text)
            
            # Create ChunkMetadata
            metadata = ChunkMetadata(
                page_number=first_page_number,
                chunk_size=chunk_size,
                start_index=start_idx,
                end_index=end_idx - 1,
                extra={
                    "page_indices": [page.page_number - 1 for page in chunk_pages],  # 0-based indices
                    "page_numbers": [page.page_number for page in chunk_pages],  # 1-based page numbers
                }
            )
            
            # Create Chunk object
            chunk_obj = Chunk(
                uuid=str(uuid.uuid4()),
                doc_title=doc_title,
                chunk=chunk_text,
                chunk_order=i,
                metadata=metadata,
            )
            
            chunks.append(chunk_obj)
            
            # Map elements to chunk_uuid
            chunk_page_numbers = [page.page_number for page in chunk_pages]
            if hasattr(parsed_document, 'elements') and parsed_document.elements:
                for element in parsed_document.elements:
                    if element.page_number in chunk_page_numbers:
                        element_chunk_map[element.element_id] = chunk_obj.uuid
        
        # Update parsed_document with element.chunk_uuid
        updated_document = parsed_document
        if element_chunk_map and hasattr(parsed_document, 'elements') and parsed_document.elements:
            updated_elements = []
            for element in parsed_document.elements:
                if element.element_id in element_chunk_map:
                    if hasattr(element, 'model_copy'):
                        updated_element = element.model_copy(
                            update={"chunk_uuid": element_chunk_map[element.element_id]}
                        )
                    else:
                        # Fallback
                        element_dict = element.model_dump() if hasattr(element, 'model_dump') else element.dict()
                        element_dict["chunk_uuid"] = element_chunk_map[element.element_id]
                        updated_element = type(element)(**element_dict)
                    updated_elements.append(updated_element)
                else:
                    updated_elements.append(element)
            
            # Update parsed_document
            if hasattr(parsed_document, 'model_copy'):
                updated_document = parsed_document.model_copy(update={"elements": updated_elements})
            else:
                updated_document = parsed_document
        
        return chunks, updated_document