"""Prepare node: document_type별로 parsed_document 준비.

- lifelog: raw text → 최소 ParsedDocument (parse 스킵)
- excel: ExcelParser.parse() 호출 (.xlsx)
- heading/plain/slide: Parser.parse() 호출 (Upstage)
"""
from __future__ import annotations

import sys
from typing import Any, Callable

from peter_parser_core import BaseParser, ParsedDocument
from peter_parser_core.common.types import ContentModel

from peter_parser.common.config import Config
from peter_parser.graph.nodes.parse import create_parser_node
from peter_parser.graph.states import PipelineState, DOCUMENT_TYPE_LIFELOG, DOCUMENT_TYPE_EXCEL
from peter_parser.impl.parser.excel import ExcelParser


def create_prepare_node(parser: BaseParser) -> Callable[[PipelineState], dict[str, Any]]:
    """Create prepare node: lifelog→text, excel→ExcelParser, 그 외→parse 노드 위임.

    Args:
        parser: heading/plain/slide용 Parser instance

    Returns:
        Node function for langgraph
    """
    parse_node = create_parser_node(parser)
    excel_parser = ExcelParser()

    def prepare_node(state: PipelineState) -> dict[str, Any]:
        document_type = state.get("document_type") or "plain"
        document = state["document"]

        if document_type == DOCUMENT_TYPE_LIFELOG:
            if Config.PIPELINE_PROGRESS:
                print("[Pipeline] Step: prepare (lifelog text, skip parse)...", file=sys.stderr, flush=True)
            text = document if isinstance(document, str) else document.decode("utf-8", errors="replace")
            parsed_doc = ParsedDocument(
                content=ContentModel(text=text),
                elements=[],
                pages=[],
                metadata={"source": "lifelog", "input_type": "text"},
            )
            return {"parsed_document": parsed_doc}
        elif document_type == DOCUMENT_TYPE_EXCEL:
            if Config.PIPELINE_PROGRESS:
                print("[Pipeline] Step: prepare (excel, ExcelParser)...", file=sys.stderr, flush=True)
            parsed_doc = excel_parser.parse(document)
            return {"parsed_document": parsed_doc}
        else:
            return parse_node(state)

    return prepare_node
