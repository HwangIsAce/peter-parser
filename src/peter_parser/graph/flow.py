"""Optimized pipeline flow execution engine."""
from langgraph.graph import StateGraph

from peter_parser_core import BaseParser

from peter_parser.graph.states import PipelineState
from peter_parser.graph.nodes.parse import create_parser_node
from peter_parser.impl.parser.upstage import UpstageParser
from peter_parser.common.config import Config
from peter_parser.graph.nodes.extract import create_extract_node, create_chunk_enrich_node
from peter_parser.graph.nodes.chunk import create_chunk_node

class PipelineFlow:
    """Optimized pipeline flow execution engine."""
    
    def __init__(self, parser: BaseParser = None):
        """Initialize pipeline flow
        
        Args:
            parser: 사용할 Parser instance
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
        
        graph.add_node("parse", create_parser_node(self.parser))
        graph.add_node("enrich", create_extract_node())
        graph.add_node("chunk", create_chunk_node())
        graph.add_node("chunk_enrich", create_chunk_enrich_node())
        
        graph.set_entry_point("parse")
        graph.add_edge("parse", "enrich")
        graph.add_edge("enrich", "chunk")
        graph.add_edge("chunk", "chunk_enrich")
        
        return graph.compile()
    
    def invoke(self, document: bytes | str) -> PipelineState:
        """Execute pipeline.
        
        Args:
            document: 파싱할 Document
            
        Returns:
            Final state with parsed_document
        """
        initial_state: PipelineState = {
            "document": document
        }
        return self.graph.invoke(initial_state)
