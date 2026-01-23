"""Shared state definitions for pipeline execution."""

from typing_extensions import NotRequired
from typing import TypedDict, Optional, Union, Literal, Dict, Any, List

from peter_parser_core import ParsedDocument

class PipelineState(TypedDict):
    """Pipeline execution state"""
    
    # --------------- parse stage ---------------
    
    document: Union[str, bytes]
    parsed_document: NotRequired[Optional[ParsedDocument]]

    # --------------- enrichment stage ---------------
    
    chunk_unit: NotRequired[Literal["page", "element"]] # PPTX는 page 단위로 처리, 나머지는 element 단위로 처리
    
    document_summary: NotRequired[Optional[str]] # 문서 요약
    
    item_metadata: NotRequired[Dict[int, Dict[str, Any]]]
    
    # --------------- chunk stage ---------------
    chunk_boundaries: NotRequired[List[int]]
    
    chunks: NotRequired[List[Dict[str, Any]]]
    
    # --------------- chunk enrichment stage ---------------

    chunk_metadata: NotRequired[Dict[int, Dict[str, Any]]]
