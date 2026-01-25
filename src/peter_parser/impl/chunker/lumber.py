"""Lumber chunker implementation (production)."""

import uuid
from pydantic import BaseModel, Field
from peter_parser.impl.extractor.structured import StructuredLLM

from typing import List, Optional, Tuple, Dict

from peter_parser.common.utils import split_sentences, segment_to_element_boundaries
from peter_parser_core import ParsedDocument
from peter_parser_core.common.types import Chunk, ChunkMetadata, Element
from peter_parser.common.config import Config
from peter_parser.prompts.chunking import LUMBER_SECTION_PROMPT, LUMBER_SYSTEM_PROMPT


class SectionBoundaries(BaseModel):
    """Boundaries of a section between two heading1 boundaries."""
    boundaries: List[int] = Field(
        description=Config.SCHEMA_DESCRIPTIONS["chunk_boundaries"]
    )

class LumberChunker:
    """Customized Lumber chunker implementation"""    
    
    
    def __init__(
        self,
        llm: Optional[StructuredLLM] = None,
    ):
        if llm is None:
            llm = StructuredLLM(datamodel=SectionBoundaries)
        self.llm = llm
        
    def detect_boundaries(
        self,
        parsed_document: ParsedDocument,        
    ) -> List[int]:
        
        elements = getattr(parsed_document, "elements", None) or []
        if not elements:
            return []
        language = (parsed_document.metadata or {}).get("language", Config.LUMBER_LANGUAGE_DEFAULT)
        
        h1_indices = [i for i, element in enumerate(elements) if element.category == "heading1"]
        if not h1_indices:
            h1_indices = [0]
            
        all_boundaries: List[int] = []
        for i, start_idx in enumerate(h1_indices):
            end_idx = h1_indices[i + 1] if i + 1 < len(h1_indices) else len(elements)
            section_el = elements[start_idx:end_idx]
            section_text = "\n".join([el.text for el in section_el if el.text])
            if not section_text.strip():
                continue
            segments = split_sentences(section_text, language)
            if len(segments) <= 1:
                continue
        
            section_heading = section_el[0].text if section_el else ""
            id_segments = [f"ID {k}: {s}" for k, s in enumerate(segments)]
            document = "\n".join(id_segments)
            heading = section_heading[:100] + "..." if len(section_heading) > 100 else section_heading

            instruction = LUMBER_SECTION_PROMPT.format(
                section_heading=heading,
                document=document,
            )
            try:
                result = self.llm.structure_output(
                    instruction=instruction,
                    user_system_prompt=LUMBER_SYSTEM_PROMPT,
                    key_attr="name",
                    value_attr="description",
                )
                seg_b = [b for b in result.boundaries if 0 < b < len(segments)]
                seg_b = sorted(list(set(seg_b)))
            except Exception:
                seg_b = []
            el_b = segment_to_element_boundaries(section_el, segments, seg_b, language)
            for eb in el_b:
                all_boundaries.append(start_idx + eb)

        return sorted(list(set(all_boundaries)))
    
    def chunk(
        self,
        parsed_document: ParsedDocument, 
        chunk_boundaries: List[int],
        doc_title: Optional[str] = None,
    ) -> Tuple[List[Chunk], ParsedDocument]:
        """Create chunks from parsed document (section-based)"""
        
        elements = getattr(parsed_document, "elements", None) or []
        if not elements:
            return [], parsed_document
        doc_title = doc_title or getattr(parsed_document, "title", None) or ""
        all_b = [0] + sorted(chunk_boundaries) + [len(elements)]
        chunks: List[Chunk] = []
        element_chunk_map: Dict[int, str] = {}
        
        for i in range(len(all_b) - 1):
            start_idx, end_idx = all_b[i], all_b[i + 1]
            chunk_el = elements[start_idx:end_idx]
            chunk_text = "\n".join([el.text for el in chunk_el if el.text])
            first_page = chunk_el[0].page_number if chunk_el else None
            meta = ChunkMetadata(
                page_number=first_page,
                chunk_size=len(chunk_text),
                start_index=start_idx,
                end_index=end_idx - 1,
                extra={
                    "element_indices": list(range(start_idx, end_idx)),
                    "element_ids": [el.element_id for el in chunk_el],
                },
            )
            ch = Chunk(
                uuid=str(uuid.uuid4()),
                doc_title=doc_title,
                chunk=chunk_text,
                chunk_order=i,
                metadata=meta,
            )
            chunks.append(ch)
            for el in chunk_el:
                element_chunk_map[el.element_id] = ch.uuid

        updated_el: List[Element] = []
        for el in parsed_document.elements:
            if el.element_id in element_chunk_map:
                updated_el.append(el.model_copy(update={"chunk_uuid": element_chunk_map[el.element_id]}))
            else:
                updated_el.append(el)
        updated_doc = parsed_document.model_copy(update={"elements": updated_el})
        return chunks, updated_doc