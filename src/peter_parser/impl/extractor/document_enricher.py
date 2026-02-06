"""Document enrichment extractor."""
import asyncio
from pydantic import BaseModel, Field

from typing import Dict, Any, Optional, List, Tuple

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

    async def _enrich_one_page(
        self,
        semaphore: asyncio.Semaphore,
        page: Any,
        page_images: Optional[List[bytes]],
    ) -> Tuple[int, Dict[str, Any]]:
        """Enrich a single page; returns (page_number, page_meta)."""
        async with semaphore:
            page_meta = None
            try:
                if page_images:
                    script_result = await self.vlm.astructure_output(
                        instruction=PAGE_SCRIPT_PROMPT,
                        images=page_images,
                        key_attr="name",
                        value_attr="description",
                    )
                else:
                    script_result = await self.llm.astructure_output(
                        instruction=f"{PAGE_SCRIPT_PROMPT}\n\n<SLIDE_TEXT>\n{getattr(page, 'text', '') or ''}\n</SLIDE_TEXT>",
                        key_attr="name",
                        value_attr="description",
                        datamodel=PageScript,
                    )
                page_meta = {"title": script_result.title, "script": script_result.script or ""}
            except Exception:
                page_meta = {"title": None, "script": (getattr(page, "text", None) or "")[:2000]}
            return (page.page_number, page_meta)

    def enrich(
        self,
        parsed_document: ParsedDocument,
        chunk_unit: str = None,
    ) -> Dict[str, Any]:
        """Enrich document with summary and metadata.
        
        Does NOT modify parsed_document. Returns enrichment separately, linked by id:
        - document_summary: linked to document (1:1).
        - item_metadata: linked to elements; key = element_id. Same page -> same
          metadata; each element on that page gets an entry.
        
        Args:
            parsed_document: Parsed document (read-only, not modified)
            chunk_unit: Chunking unit ("page" or "element")
        
        Returns:
            Dict with document_summary, item_metadata, chunk_unit.
            parsed_document is NOT returned (original kept unchanged).
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
        
        # 2. Page metadata (VLM/LLM per page, parallel)
        item_metadata = {}
        if chunk_unit == "page" and hasattr(parsed_document, "elements") and parsed_document.elements:
            max_concurrency = max(1, getattr(Config, "DOCUMENT_ENRICH_MAX_CONCURRENCY", 5))
            semaphore = asyncio.Semaphore(max_concurrency)
            pages_with_images = [
                (page, self._get_page_images(parsed_document, page.page_number))
                for page in parsed_document.pages
            ]
            tasks = [
                self._enrich_one_page(semaphore, page, imgs)
                for page, imgs in pages_with_images
            ]

            async def _gather_all():
                return await asyncio.gather(*tasks)

            results: List[Tuple[int, Dict[str, Any]]] = self.llm._run_async(_gather_all())
            for page_number, page_meta in results:
                for el in parsed_document.elements:
                    if el.page_number == page_number:
                        item_metadata[el.element_id] = page_meta
        
        # Return enrichment data separately (linked, not attached to ParsedDocument)
        return {
            "document_summary": document_summary,
            "item_metadata": item_metadata,
            "chunk_unit": chunk_unit,
        }