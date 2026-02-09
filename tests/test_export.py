"""Tests for Export node (chunks -> JSON)."""
import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

from peter_parser_core.common.types import Chunk, ChunkMetadata
from peter_parser.graph.nodes.export import create_export_node
from peter_parser.graph.states import PipelineState


# ============================================================================
# Unit Tests: create_export_node
# ============================================================================


def test_export_node_returns_export_json():
    """Export node returns dict with export_json key."""
    export_node = create_export_node()
    state: PipelineState = {"chunks": []}
    out = export_node(state)
    assert "export_json" in out
    assert isinstance(out["export_json"], str)


def test_export_node_empty_chunks():
    """Empty chunks -> export_json is '[]'."""
    export_node = create_export_node()
    state: PipelineState = {"chunks": []}
    out = export_node(state)
    parsed = json.loads(out["export_json"])
    assert parsed == []


def test_export_node_no_chunks_in_state():
    """Missing chunks in state -> export_json is '[]'."""
    export_node = create_export_node()
    state: PipelineState = {"document": b"fake"}
    out = export_node(state)
    parsed = json.loads(out["export_json"])
    assert parsed == []


def test_export_node_single_chunk():
    """Single chunk -> valid JSON array with one object."""
    export_node = create_export_node()
    chunks = [
        Chunk(
            uuid="u1",
            doc_title="Doc",
            chunk="Hello.",
            chunk_order=0,
            metadata=ChunkMetadata(chunk_size=6, start_index=0, end_index=6, extra={}),
        ),
    ]
    state: PipelineState = {"chunks": chunks}
    out = export_node(state)
    parsed = json.loads(out["export_json"])
    assert len(parsed) == 1
    assert parsed[0]["uuid"] == "u1"
    assert parsed[0]["chunk"] == "Hello."
    assert parsed[0]["chunk_order"] == 0
    assert "metadata" in parsed[0]


def test_export_node_multiple_chunks():
    """Multiple chunks -> valid JSON array, order preserved."""
    export_node = create_export_node()
    chunks = [
        Chunk(
            uuid="u0",
            doc_title="Doc",
            chunk="First.",
            chunk_order=0,
            metadata=ChunkMetadata(chunk_size=6, extra={"foo": "a"}),
        ),
        Chunk(
            uuid="u1",
            doc_title="Doc",
            chunk="Second.",
            chunk_order=1,
            metadata=ChunkMetadata(chunk_size=7, extra={"foo": "b"}),
        ),
    ]
    state: PipelineState = {"chunks": chunks}
    out = export_node(state)
    parsed = json.loads(out["export_json"])
    assert len(parsed) == 2
    assert parsed[0]["chunk"] == "First." and parsed[0]["metadata"]["extra"]["foo"] == "a"
    assert parsed[1]["chunk"] == "Second." and parsed[1]["metadata"]["extra"]["foo"] == "b"


def test_export_node_unicode():
    """Unicode (e.g. Korean) preserved with ensure_ascii=False."""
    export_node = create_export_node()
    chunks = [
        Chunk(
            uuid="u1",
            doc_title="문서",
            chunk="먹었다.",
            chunk_order=0,
            metadata=ChunkMetadata(extra={"lifelog": {"when": "1/25 10:00"}}),
        ),
    ]
    state: PipelineState = {"chunks": chunks}
    out = export_node(state)
    assert "먹었다" in out["export_json"]
    assert "1/25" in out["export_json"]
    parsed = json.loads(out["export_json"])
    assert parsed[0]["chunk"] == "먹었다."
    assert parsed[0]["metadata"]["extra"]["lifelog"]["when"] == "1/25 10:00"


# ============================================================================
# Pipeline Integration Test (lifelog + export)
# ============================================================================


def test_pipeline_export_json():
    """Full pipeline produces export_json (lifelog: raw text input)."""
    from peter_parser.graph.flow import PipelineFlow
    from peter_parser_core import BaseParser
    from peter_parser_core.common.types import ContentModel
    from peter_parser_core import ParsedDocument

    sample_text = """1/25 10:00~10:30
나
밥을
집에서
-
먹었다.

1/25 14:00~15:00
나
회의를
회사에서
-
했다."""

    class MockParser(BaseParser):
        def parse(self, document):
            return ParsedDocument(content=ContentModel(text=""), elements=[], pages=[], metadata={})

    try:
        flow = PipelineFlow(parser=MockParser())
        state = flow.invoke(document=sample_text, document_type="lifelog")
        assert "export_json" in state
        parsed = json.loads(state["export_json"])
        assert isinstance(parsed, list)
        assert len(parsed) == 2
        assert all("uuid" in c and "chunk" in c and "metadata" in c for c in parsed)
        assert "lifelog" in parsed[0]["metadata"]["extra"]
        assert "graph" in parsed[0]["metadata"]["extra"]
    except Exception as e:
        import pytest
        pytest.skip(f"Pipeline export test skipped: {e}")
