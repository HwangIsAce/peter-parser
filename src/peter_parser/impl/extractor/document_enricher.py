"""Document enrichment extractor."""
from pydantic import BaseModel, Field

from typing import Dict, Any, Optional, List

from peter_parser_core import ParsedDocument
from peter_parser.impl.extractor.structured import StructuredLLM
from peter_parser.prompts.enrichment import DOCUMENT_SUMMARY_PROMPT, PAGE_SCRIPT_PROMPT
from peter_parser.common.config import Config


class DocumentSummary(BaseModel):
    """Document summary model."""
    summary: str = Field(description=Config.SCHEMA_DESCRIPTIONS["document_summary"])


class PageScript(BaseModel):
    """Page script and title model."""
    title: Optional[str] = Field(default=None, description=Config.SCHEMA_DESCRIPTIONS["page_title"])
    script: str = Field(description=Config.SCHEMA_DESCRIPTIONS["page_script"])


class DocumentEnricher:
    """Extractor for document-level enrichment."""
    
    def __init__(
        self,
        llm: Optional[StructuredLLM] = None,
        vlm: Optional[StructuredLLM] = None,
    ):
        """Initialize DocumentEnricher"""
        if llm is None:
            llm = StructuredLLM(datamodel=DocumentSummary)
        if vlm is None:
            vlm = StructuredLLM(datamodel=PageScript)
        
        self.llm = llm
        self.vlm = vlm
    
    def _get_page_images(
        self,
        parsed_document: ParsedDocument,
        page_number: int,
    ) -> Optional[List[bytes]]:
        """Get images for a specific page.
        
        Args:
            parsed_document: Parsed document
            page_number: Page number (1-based)
        
        Returns:
            List of image bytes, or None if no images
        """
        page_images = [
            img for img in parsed_document.images
            if img.page_number == page_number
        ]
        
        if not page_images:
            return None
        
        # Extract image data (assuming base64 encoded or bytes)
        image_data = []
        for img in page_images:
            # Try base64 field first (most common)
            if hasattr(img, 'base64') and img.base64:
                if isinstance(img.base64, bytes):
                    image_data.append(img.base64)
                elif isinstance(img.base64, str):
                    import base64
                    image_data.append(base64.b64decode(img.base64))
            # Try base64_data field
            elif hasattr(img, 'base64_data') and img.base64_data:
                if isinstance(img.base64_data, bytes):
                    image_data.append(img.base64_data)
                elif isinstance(img.base64_data, str):
                    import base64
                    image_data.append(base64.b64decode(img.base64_data))
            # Fallback: check if image has raw data
            elif hasattr(img, 'data') and img.data:
                if isinstance(img.data, bytes):
                    image_data.append(img.data)
                elif isinstance(img.data, str):
                    import base64
                    image_data.append(base64.b64decode(img.data))
        
        return image_data if image_data else None
    
    def enrich(
        self,
        parsed_document: ParsedDocument,
        chunk_unit: str = None,
    ) -> Dict[str, Any]:
        """Enrich document with summary and metadata.
        
        Args:
            parsed_document: Parsed document
            chunk_unit: Chunking unit ("page" or "element")
        
        Returns:
            Dict with document_summary, item_metadata, chunk_unit
        """
        chunk_unit = chunk_unit or Config.DEFAULT_CHUNK_UNIT
        
        # 1. Document summary (LLM)
        document_content = parsed_document.content or ""
        content = document_content[:Config.CHUNK_MAX_CONTENT_LENGTH]
        
        summary_result = self.llm.structure_output(
            instruction=DOCUMENT_SUMMARY_PROMPT.format(document_content=content),
            key_attr="name",
            value_attr="description"
        )
        document_summary = summary_result.summary
        
        # 2. Page metadata (VLM per page if images available, else LLM)
        item_metadata = {}
        
        if chunk_unit == "page":
            for page in parsed_document.pages:
                page_idx = page.page_number - 1
                page_number = page.page_number
                
                # Try to get page images
                page_images = self._get_page_images(parsed_document, page_number)
                
                if page_images:
                    # Use VLM with images
                    script_result = self.vlm.structure_output(
                        instruction=PAGE_SCRIPT_PROMPT,
                        images=page_images,
                        key_attr="name",
                        value_attr="description"
                    )
                else:
                    # Fallback to LLM with text
                    script_result = self.llm.structure_output(
                        instruction=f"{PAGE_SCRIPT_PROMPT}\n\n<SLIDE_TEXT>\n{page.text}\n</SLIDE_TEXT>",
                        key_attr="name",
                        value_attr="description"
                    )
                
                item_metadata[page_idx] = {
                    "title": script_result.title,
                    "script": script_result.script
                }
        
        return {
            "document_summary": document_summary,
            "item_metadata": item_metadata,
            "chunk_unit": chunk_unit,
        }