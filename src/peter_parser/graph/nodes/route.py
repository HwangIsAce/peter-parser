"""Route node: set document_type via LLM when not already provided."""
from __future__ import annotations

from typing import Any, Callable, Optional

from peter_parser_core import ParsedDocument
from peter_parser.graph.states import PipelineState
from peter_parser.impl.router.llm_router import LLMRouter


def create_route_node(router: Optional[LLMRouter] = None) -> Callable[[PipelineState], dict[str, Any]]:
    """Create the route node. If document_type is already in state, skip LLM; else call LLMRouter."""

    _router = router or LLMRouter()

    def route_node(state: PipelineState) -> dict[str, Any]:
        if state.get("document_type") is not None:
            return {}
        parsed: Optional[ParsedDocument] = state.get("parsed_document")
        if not parsed:
            return {"document_type": "plain"}
        content = getattr(getattr(parsed, "content", None), "text", None) or ""
        meta = getattr(parsed, "metadata", None) or {}
        title = getattr(parsed, "title", None) or meta.get("title")
        file_extension = meta.get("file_extension")
        document_type = _router.route(content, file_extension=file_extension, title=title)
        return {"document_type": document_type}

    return route_node
