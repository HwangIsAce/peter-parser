"""Route node: set document_type via VLM (page images) or LLM (text) when not already provided."""
from __future__ import annotations

from typing import Any, Callable, Optional

from peter_parser_core import ParsedDocument
from peter_parser.graph.states import PipelineState
from peter_parser.impl.router.llm_router import LLMRouter
from peter_parser.impl.router.vlm_router import VLMRouter
from peter_parser.common.document_render import document_to_page_images
from peter_parser.common.config import Config


def create_route_node(
    router: Optional[LLMRouter] = None,
    vlm_router: Optional[VLMRouter] = None,
) -> Callable[[PipelineState], dict[str, Any]]:
    """Create the route node. Uses VLM when document is PDF bytes and page images available; else LLM."""

    _llm_router = router or LLMRouter()
    _vlm_router = vlm_router or VLMRouter()

    def route_node(state: PipelineState) -> dict[str, Any]:
        if state.get("document_type") is not None:
            return {}
        parsed: Optional[ParsedDocument] = state.get("parsed_document")
        if not parsed:
            return {"document_type": "plain"}
        meta = getattr(parsed, "metadata", None) or {}
        title = getattr(parsed, "title", None) or meta.get("title")
        file_extension = meta.get("file_extension")

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

        content = getattr(getattr(parsed, "content", None), "text", None) or ""
        document_type = _llm_router.route(
            content,
            file_extension=file_extension,
            title=title,
        )
        return {"document_type": document_type}

    return route_node
