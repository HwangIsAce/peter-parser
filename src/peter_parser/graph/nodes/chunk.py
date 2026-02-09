"""Chunk node implementation."""
import sys
from typing import Any, Callable, Dict, Optional

from peter_parser.common.config import Config
from peter_parser.graph.states import (
    PipelineState,
    DOCUMENT_TYPE_HEADING,
    DOCUMENT_TYPE_PLAIN,
    DOCUMENT_TYPE_SLIDE,
    DOCUMENT_TYPE_LIFELOG,
    DOCUMENT_TYPE_EXCEL,
)
from peter_parser.impl.chunker.vlm import VLMChunker
from peter_parser.impl.chunker.lumber import LumberChunker
from peter_parser.impl.chunker.lifelog import LifelogChunker
from peter_parser.impl.chunker.heading import HeadingPromptChunker
from peter_parser.impl.chunker.excel import ExcelChunker
from peter_parser.impl.db.lifelog_store import LifelogStore

def create_chunk_node(
    chunker: Optional[Any] = None,
) -> Callable[[PipelineState], Dict[str, Any]]:
    """Create a chunk node function.
    
    Args:
        chunker: VLMChunker instance
    
    Returns:
        Node function for langgraph
    """
    def chunk_node(state: PipelineState) -> Dict[str, Any]:
        """Chunk node function for langgraph."""
        if Config.PIPELINE_PROGRESS:
            dt = state.get("document_type")
            cu = state.get("chunk_unit") or Config.DEFAULT_CHUNK_UNIT
            mode = "lifelog" if (dt == DOCUMENT_TYPE_LIFELOG or cu == "lifelog") else ("excel" if dt == DOCUMENT_TYPE_EXCEL else ("slide" if dt == DOCUMENT_TYPE_SLIDE else ("heading" if dt == DOCUMENT_TYPE_HEADING else "plain")))
            print(f"[Pipeline] Step: chunk (mode={mode}, LLM per event/page)...", file=sys.stderr, flush=True)
        parsed_document = state.get("parsed_document")
        if not parsed_document:
            raise ValueError("parsed_document is required")
        
        # Resolve mode: document_type (4-case) takes precedence over chunk_unit (legacy).
        document_type = state.get("document_type")
        chunk_unit = state.get("chunk_unit") or Config.DEFAULT_CHUNK_UNIT
        document_summary = state.get("document_summary", "")
        item_metadata = state.get("item_metadata", {})

        use_slide = document_type == DOCUMENT_TYPE_SLIDE or chunk_unit == "page"
        use_lifelog = document_type == DOCUMENT_TYPE_LIFELOG or chunk_unit == "lifelog"
        use_heading = document_type == DOCUMENT_TYPE_HEADING
        use_excel = document_type == DOCUMENT_TYPE_EXCEL

        # Initialize chunker if needed
        if chunker is not None:
            current_chunker = chunker
        elif use_excel:
            current_chunker = ExcelChunker()
        elif use_lifelog:
            try:
                lifelog_store = LifelogStore()
            except Exception:
                lifelog_store = None
            current_chunker = LifelogChunker(lifelog_store=lifelog_store)
        elif use_slide:
            current_chunker = VLMChunker()
        elif use_heading:
            current_chunker = HeadingPromptChunker()
        else:
            current_chunker = LumberChunker()

        # Detect boundaries (VLM/slide needs document_summary and item_metadata)
        if use_slide:
            boundaries = current_chunker.detect_boundaries(
                parsed_document=parsed_document,
                document_summary=document_summary,
                item_metadata=item_metadata,
            )
        else:
            boundaries = current_chunker.detect_boundaries(
                parsed_document=parsed_document,
            )
        
        # Create chunks (returns chunks and updated parsed_document)
        chunks, updated_parsed_document = current_chunker.chunk(
            parsed_document=parsed_document,
            chunk_boundaries=boundaries,
            doc_title=getattr(parsed_document, "title", None),
        )
        
        return {
            "parsed_document": updated_parsed_document,
            "chunk_boundaries": boundaries,
            "chunks": chunks,
        }
    
    return chunk_node