"""Optimized pipeline flow execution engine."""
from langgraph.graph import StateGraph

from typing import Optional

from peter_parser_core import BaseParser

from peter_parser.graph.states import (
    PipelineState,
    DocumentType,
    DOCUMENT_TYPE_SLIDE,
)
from peter_parser.graph.nodes.prepare import create_prepare_node
from peter_parser.impl.parser.upstage import UpstageParser
from peter_parser.common.config import Config
from peter_parser.graph.nodes.extract import create_extract_node, create_chunk_enrich_node
from peter_parser.graph.nodes.chunk import create_chunk_node
from peter_parser.graph.nodes.export import create_export_node

def _route_after_parse(state: PipelineState) -> str:
    """4-case: only slide → enrich; heading/plain/lifelog → chunk. Legacy: chunk_unit page → enrich."""
    document_type: str | None = state.get("document_type")
    if document_type is not None:
        if document_type == DOCUMENT_TYPE_SLIDE:
            return "enrich"
        return "chunk"
    chunk_unit = state.get("chunk_unit") or Config.DEFAULT_CHUNK_UNIT
    if chunk_unit in ("element", "lifelog"):
        return "chunk"
    return "enrich"

class PipelineFlow:
    """Optimized pipeline flow execution engine."""

    def __init__(self, parser: BaseParser = None):
        """Initialize pipeline flow

        Args:
            parser: 사용할 Parser instance. If None, UpstageParser is used.
        """
        if parser is None:
            Config.validate()  # 필수 설정 확인
            parser = UpstageParser(
                api_key=Config.UPSTAGE_API_KEY,
                api_url=Config.UPSTAGE_API_URL,
                default_ocr=Config.UPSTAGE_DEFAULT_OCR,
                default_base64_encoding=Config.UPSTAGE_DEFAULT_BASE64_ENCODING,
                default_model=Config.UPSTAGE_DEFAULT_MODEL,
            )

        self.parser = parser
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build langgraph StateGraph"""
        graph = StateGraph(PipelineState)

        graph.add_node("prepare", create_prepare_node(self.parser))
        graph.add_node("enrich", create_extract_node())
        graph.add_node("chunk", create_chunk_node())
        graph.add_node("chunk_enrich", create_chunk_enrich_node())
        graph.add_node("export", create_export_node())

        graph.set_entry_point("prepare")
        graph.add_conditional_edges("prepare", _route_after_parse, {"enrich": "enrich", "chunk": "chunk"})
        graph.add_edge("enrich", "chunk")
        graph.add_edge("chunk", "chunk_enrich")
        graph.add_edge("chunk_enrich", "export")

        return graph.compile()
    
    def invoke(
        self,
        document: bytes | str,
        document_type: DocumentType = "plain",
        chunk_unit: Optional[str] = None,
    ) -> PipelineState:
        """Execute pipeline.

        Args:
            document: PDF bytes/path (heading/plain/slide) or raw text str (lifelog)
            document_type: "heading" | "plain" | "slide" | "lifelog". Caller must provide.
            chunk_unit: Legacy. "page" | "element" | "lifelog". Prefer document_type.

        Returns:
            Final state with parsed_document, chunks, export_json.
        """
        initial_state: PipelineState = {"document": document, "document_type": document_type}
        if chunk_unit is not None:
            initial_state["chunk_unit"] = chunk_unit
        return self.graph.invoke(initial_state)
