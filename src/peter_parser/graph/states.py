"""Shared state definitions for pipeline execution."""

from typing_extensions import NotRequired
from typing import TypedDict, Optional, Union

from peter_parser_core import ParsedDocument

class PipelineState(TypedDict):
    """Pipeline execution state"""
    
    document: Union[str, bytes]
    parsed_document: NotRequired[Optional[ParsedDocument]] 
