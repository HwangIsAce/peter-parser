"""VLM-based router: classify document type from sampled page images."""
from __future__ import annotations

from typing import List, Optional

from peter_parser.common.config import Config
from peter_parser.impl.extractor.structured import StructuredLLM
from peter_parser.impl.router.schema import DocumentTypeLiteral, RouterSchema
from peter_parser.impl.router.fewshot_loader import get_router_fewshot_images, TYPES
from peter_parser.prompts.route import ROUTER_VLM_SYSTEM, build_router_vlm_instruction


class VLMRouter:
    """Router that classifies document_type from page images (VLM) with optional few-shot."""

    def __init__(self, llm: Optional[StructuredLLM] = None) -> None:
        self.llm = llm or StructuredLLM(datamodel=RouterSchema)

    def route(
        self,
        page_images: List[bytes],
        file_extension: Optional[str] = None,
        title: Optional[str] = None,
    ) -> Optional[DocumentTypeLiteral]:
        """Classify document from sampled page images. Returns None if no images (caller should use LLM fallback)."""
        if not page_images:
            return None
        # Few-shot: heading, slide, lifelog (fixed order)
        fewshot = get_router_fewshot_images()
        extra: List[bytes] = []
        for t in TYPES:
            extra.extend(fewshot.get(t, []))
        all_images = page_images + extra
        instruction = build_router_vlm_instruction(
            num_doc_images=len(page_images),
            has_fewshot=len(extra) > 0,
        )
        try:
            out = self.llm.structure_output(
                instruction=instruction,
                user_system_prompt=ROUTER_VLM_SYSTEM,
                datamodel=RouterSchema,
                images=all_images,
            )
        except Exception:
            return "plain"
        dt = getattr(out, "document_type", None) or "plain"
        if dt not in ("heading", "plain", "slide", "lifelog"):
            return "plain"
        return dt
