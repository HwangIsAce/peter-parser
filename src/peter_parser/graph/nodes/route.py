"""Route node: set document_type via LLM (parsed text) or VLM (page images) when not already provided."""
from __future__ import annotations

import sys
from typing import Any, Callable, Optional

from peter_parser_core import ParsedDocument
from peter_parser.graph.states import PipelineState
from peter_parser.impl.router.llm_router import LLMRouter
from peter_parser.impl.router.vlm_router import VLMRouter
from peter_parser.common.document_render import document_to_page_images
from peter_parser.common.router_text_sample import sample_router_text
from peter_parser.common.config import Config


def create_route_node(
    router: Optional[LLMRouter] = None,
    vlm_router: Optional[VLMRouter] = None,
) -> Callable[[PipelineState], dict[str, Any]]:
    """Create the route node.

    ROUTER_MODE=llm (default): uses parsed text, samples up to ROUTER_LLM_MAX_PAGES pages.
    ROUTER_MODE=vlm: uses page images + VLM (legacy).
    """

    _llm_router = router or LLMRouter()
    _vlm_router = vlm_router or VLMRouter()

    def route_node(state: PipelineState) -> dict[str, Any]:
        if Config.PIPELINE_PROGRESS:
            mode = Config.ROUTER_MODE or "llm"
            print(f"[Pipeline] Step: route ({mode.upper()} document-type)...", file=sys.stderr, flush=True)
        if state.get("document_type") is not None:
            return {}
        parsed: Optional[ParsedDocument] = state.get("parsed_document")
        if not parsed:
            return {"document_type": "plain"}
        meta = getattr(parsed, "metadata", None) or {}
        title = getattr(parsed, "title", None) or meta.get("title")
        file_extension = meta.get("file_extension")

        # VLM path: only when ROUTER_MODE=vlm and document is PDF
        router_mode = getattr(Config, "ROUTER_MODE", "llm") or "llm"
        if router_mode == "vlm":
            document = state.get("document")
            if isinstance(document, bytes) and len(document) >= 4 and document[:4] == b"%PDF":
                max_pages = getattr(Config, "ROUTER_VLM_MAX_PAGES", 4)
                sample = getattr(Config, "ROUTER_VLM_PAGE_SAMPLE", "uniform") or "uniform"
                page_images = document_to_page_images(
                    document,
                    max_pages=max_pages,
                    sample=sample if sample in ("uniform", "random") else "uniform",
                )
                if page_images:
                    document_type = _vlm_router.route(
                        page_images,
                        file_extension=file_extension,
                        title=title,
                    )
                    if document_type is not None:
                        return {"document_type": document_type}

        # LLM path: sample text from parsed_document (default)
        content = sample_router_text(
            parsed,
            max_pages=getattr(Config, "ROUTER_LLM_MAX_PAGES", 5),
            sample=(getattr(Config, "ROUTER_LLM_PAGE_SAMPLE", "random") or "random"),
            max_chars=Config.ROUTER_CONTENT_MAX_CHARS,
        )
        document_type = _llm_router.route(
            content,
            file_extension=file_extension,
            title=title,
        )
        return {"document_type": document_type}

    return route_node
