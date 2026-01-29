"""LLM-based router implementation (production)."""

from __future__ import annotations

from typing import Optional

from peter_parser.common.config import Config
from peter_parser.impl.extractor.structured import StructuredLLM
from peter_parser.impl.router.schema import RouterSchema, DocumentTypeLiteral
from peter_parser.prompts.route import ROUTER_SYSTEM, build_router_instruction


class LLMRouter:
    """LLM-based router: classifies document content into one of heading/plain/slide/lifelog."""

    def __init__(self, llm: Optional[StructuredLLM] = None) -> None:
        self.llm = llm or StructuredLLM(datamodel=RouterSchema)

    def route(
        self,
        content: str,
        file_extension: Optional[str] = None,
        title: Optional[str] = None,
    ) -> DocumentTypeLiteral:
        """Classify document into document_type using LLM structured output.

        Args:
            content: Document text (e.g. from parsed_document.content.text). May be truncated.
            file_extension: Optional hint (e.g. "pdf", "pptx").
            title: Optional document title.

        Returns:
            One of "heading", "plain", "slide", "lifelog".
        """
        snippet = (content or "")[:Config.ROUTER_CONTENT_MAX_CHARS]
        instruction = build_router_instruction(
            content=snippet,
            file_extension=file_extension,
            title=title,
        )
        try:
            out = self.llm.structure_output(
                instruction=instruction,
                user_system_prompt=ROUTER_SYSTEM,
                datamodel=RouterSchema,
            )
        except Exception:
            return "plain"
        dt = getattr(out, "document_type", None) or "plain"
        if dt not in ("heading", "plain", "slide", "lifelog"):
            return "plain"
        return dt
