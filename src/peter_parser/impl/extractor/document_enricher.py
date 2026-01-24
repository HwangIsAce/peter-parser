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
            Dict with parsed_document (updated), chunk_unit
        """
        chunk_unit = chunk_unit or Config.DEFAULT_CHUNK_UNIT
        
        # 1. Document summary (LLM)
        # Get content text (from property or content field)
        document_content = ""
        if hasattr(parsed_document, 'content'):
            if isinstance(parsed_document.content, dict):
                document_content = parsed_document.content.get("text", "")
            elif hasattr(parsed_document.content, 'text'):
                document_content = parsed_document.content.text or ""
        
        # Fallback to property if content field doesn't have text
        if not document_content:
            content_prop = getattr(parsed_document, 'content', None)
            if callable(content_prop):
                document_content = content_prop() or ""
            elif isinstance(content_prop, str):
                document_content = content_prop
        
        content = document_content[:Config.CHUNK_MAX_CONTENT_LENGTH] if document_content else ""
        
        summary_result = self.llm.structure_output(
            instruction=DOCUMENT_SUMMARY_PROMPT.format(document_content=content),
            key_attr="name",
            value_attr="description"
        )
        document_summary = summary_result.summary
        
        # 2. Update ParsedDocument with summary
        # Try to update content.summary
        updated_content = None
        if hasattr(parsed_document, 'content'):
            if isinstance(parsed_document.content, dict):
                updated_content = {**parsed_document.content, "summary": document_summary}
            elif hasattr(parsed_document.content, 'model_copy'):
                # Pydantic model
                updated_content = parsed_document.content.model_copy(update={"summary": document_summary})
            elif hasattr(parsed_document.content, 'copy'):
                # Regular object with copy
                updated_content = parsed_document.content.copy()
                updated_content.summary = document_summary
        
        # 3. Page metadata (VLM per page if images available, else LLM)
        updated_elements = []
        if chunk_unit == "page" and hasattr(parsed_document, 'elements') and parsed_document.elements:
            # Group elements by page_number
            page_metadata = {}
            
            for page in parsed_document.pages:
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
                
                # Store metadata for this page
                page_metadata[page_number] = {
                    "title": script_result.title,
                    "script": script_result.script
                }
            
            # Update elements with enrichment_metadata
            for element in parsed_document.elements:
                if element.page_number in page_metadata:
                    # Update element with metadata
                    if hasattr(element, 'model_copy'):
                        updated_element = element.model_copy(
                            update={"enrichment_metadata": page_metadata[element.page_number]}
                        )
                    else:
                        # Fallback: create new element
                        element_dict = element.model_dump() if hasattr(element, 'model_dump') else element.dict()
                        element_dict["enrichment_metadata"] = page_metadata[element.page_number]
                        updated_element = type(element)(**element_dict)
                    updated_elements.append(updated_element)
                else:
                    updated_elements.append(element)
        else:
            # No elements or not page unit - keep as is
            updated_elements = list(parsed_document.elements) if hasattr(parsed_document, 'elements') else []
        
        # 4. Create updated ParsedDocument
        try:
            # Try to create with updated fields
            if updated_content is not None:
                updated_doc = parsed_document.model_copy(
                    update={
                        "content": updated_content,
                        "elements": updated_elements,
                    }
                ) if hasattr(parsed_document, 'model_copy') else parsed_document
            else:
                # If content update failed, just update elements
                if updated_elements:
                    updated_doc = parsed_document.model_copy(
                        update={"elements": updated_elements}
                    ) if hasattr(parsed_document, 'model_copy') else parsed_document
                else:
                    updated_doc = parsed_document
        except Exception:
            # Fallback: return original document
            updated_doc = parsed_document
        
        return {
            "parsed_document": updated_doc,
            "chunk_unit": chunk_unit,
        }