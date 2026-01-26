"""Parse node implementation."""
from typing import Any, Callable

from peter_parser_core import BaseParser, ParserError, ParsedDocument
from peter_parser_core.common.types import ContentModel

from peter_parser.graph.states import PipelineState

def create_parser_node(parser: BaseParser) -> Callable[[PipelineState], dict[str, Any]]:
    """Create a parser node function
    
    Args:
        parser: 사용할 Parser Instance (UpstageParser, docling, etc.)
        
    Returns:
        Node function for langgraph
    """
    
    def parse_node(state: PipelineState) -> dict[str, Any]:
        """Parse node function for langgraph"
        
        Args:
            state: 현재 상태 (문서 경로, 파서 설정 등)
            
        Returns:
            partial state with parsed_document
        """
        
        document = state["document"]
        
        try:
            parsed_doc = parser.parse(document)
            return {
                "parsed_document": parsed_doc
            }
        except ParserError as e:
            raise  # langgraph가 예외를 처리하거나, 필요하면 dict 반환
        except Exception as e:
            raise ParserError(f"Unexpected error: {str(e)}") from e
            
    return parse_node

