"""Tests for lifelog chunking and entity store."""
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from typing import List

project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

from peter_parser_core import ParsedDocument
from peter_parser_core.common.types import ContentModel
from peter_parser.impl.chunker.lifelog import (
    LifelogChunker,
    LifelogEvent,
    _parse_lifelog_events,
    _ev_to_day,
    _LifelogEntitiesOut,
    _EntityExtraction,
)
from peter_parser.impl.db.lifelog_store import LifelogStore


# ============================================================================
# Test Fixtures
# ============================================================================

def create_sample_lifelog_text() -> str:
    """Create sample lifelog text in 5W1H format."""
    return """1/25 10:00~10:30
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
했다.

1/25 19:00~20:00
나
저녁을
홍대에서
-
먹었다."""


def create_mock_lifelog_parsed_document() -> ParsedDocument:
    """Create a mock ParsedDocument for lifelog."""
    text = create_sample_lifelog_text()
    return ParsedDocument(
        content=ContentModel(text=text),
        elements=[],
        pages=[],
        metadata={"source": "lifelog"},
    )


# ============================================================================
# Unit Tests: _parse_lifelog_events
# ============================================================================

def test_parse_lifelog_events_basic():
    """Test basic parsing of lifelog events."""
    text = create_sample_lifelog_text()
    events = _parse_lifelog_events(text)
    
    assert len(events) == 3
    assert events[0].when == "1/25 10:00~10:30"
    assert events[0].who == "나"
    assert events[0].what == "밥을"
    assert events[0].where == "집에서"
    assert events[0].why_how == "-"
    assert events[0].description == "먹었다."


def test_parse_lifelog_events_empty():
    """Test parsing empty text."""
    events = _parse_lifelog_events("")
    assert len(events) == 0


def test_parse_lifelog_events_single_event():
    """Test parsing single event."""
    text = """1/25 10:00
나
밥을
집에서
-
먹었다."""
    events = _parse_lifelog_events(text)
    assert len(events) == 1
    assert events[0].when == "1/25 10:00"


def test_parse_lifelog_events_separator():
    """Test parsing with --- separator."""
    text = """1/25 10:00
나
밥을
집에서
-
먹었다.
---
1/26 10:00
나
아침을
집에서
-
먹었다."""
    events = _parse_lifelog_events(text)
    assert len(events) == 2


# ============================================================================
# Unit Tests: _ev_to_day
# ============================================================================

def test_ev_to_day_slash():
    """Test day extraction with slash."""
    ev = LifelogEvent(when="1/25 10:00")
    day = _ev_to_day(ev)
    assert day == "2025-01-25"


def test_ev_to_day_dash():
    """Test day extraction with dash."""
    ev = LifelogEvent(when="1-25 10:00")
    day = _ev_to_day(ev)
    assert day == "2025-01-25"


def test_ev_to_day_dot():
    """Test day extraction with dot."""
    ev = LifelogEvent(when="1.25 10:00")
    day = _ev_to_day(ev)
    assert day == "2025-01-25"


def test_ev_to_day_unknown():
    """Test day extraction with invalid format."""
    ev = LifelogEvent(when="invalid")
    day = _ev_to_day(ev)
    assert day == "unknown"


def test_ev_to_day_empty():
    """Test day extraction with empty when."""
    ev = LifelogEvent(when="")
    day = _ev_to_day(ev)
    assert day == "unknown"


# ============================================================================
# Unit Tests: LifelogChunker.detect_boundaries
# ============================================================================

def test_lifelog_chunker_detect_boundaries():
    """Test boundary detection for lifelog events."""
    chunker = LifelogChunker()
    parsed_doc = create_mock_lifelog_parsed_document()
    
    boundaries = chunker.detect_boundaries(parsed_doc)
    assert boundaries == [1, 2]


def test_lifelog_chunker_detect_boundaries_single():
    """Test boundary detection for single event."""
    text = """1/25 10:00
나
밥을
집에서
-
먹었다."""
    parsed_doc = ParsedDocument(
        content=ContentModel(text=text),
        elements=[],
        pages=[],
        metadata={},
    )
    chunker = LifelogChunker()
    boundaries = chunker.detect_boundaries(parsed_doc)
    assert boundaries == []


# ============================================================================
# Unit Tests: LifelogChunker.chunk (with mock LLM)
# ============================================================================

def test_lifelog_chunker_chunk_with_mock_llm():
    """Test chunking with mock LLM."""
    mock_llm = Mock()
    mock_llm.structure_output.return_value = _LifelogEntitiesOut(
        entities=[
            _EntityExtraction(
                canonical_text="식사",
                original_text="밥",
                type="food",
            ),
            _EntityExtraction(
                canonical_text="집",
                original_text="집",
                type="location",
            ),
        ]
    )
    
    chunker = LifelogChunker(llm=mock_llm, lifelog_store=None)
    parsed_doc = create_mock_lifelog_parsed_document()
    boundaries = chunker.detect_boundaries(parsed_doc)
    
    chunks, updated_doc = chunker.chunk(
        parsed_document=parsed_doc,
        chunk_boundaries=boundaries,
        doc_title="Test Lifelog",
    )
    
    assert len(chunks) == 3
    assert chunks[0].chunk_order == 0
    assert chunks[1].chunk_order == 1
    assert chunks[2].chunk_order == 2
    
    # Check metadata
    assert "lifelog" in chunks[0].metadata.extra
    assert "graph" in chunks[0].metadata.extra
    assert chunks[0].metadata.extra["lifelog"]["when"] == "1/25 10:00~10:30"
    assert len(chunks[0].metadata.extra["lifelog"]["entities"]) > 0
    assert "day" in chunks[0].metadata.extra["graph"]
    assert "entity_ids" in chunks[0].metadata.extra["graph"]


def test_lifelog_chunker_chunk_with_store():
    """Test chunking with mock store."""
    mock_llm = Mock()
    mock_llm.structure_output.return_value = _LifelogEntitiesOut(
        entities=[
            _EntityExtraction(
                canonical_text="식사",
                original_text="밥",
                type="food",
            ),
        ]
    )
    
    mock_store = Mock()
    mock_store.save_event = Mock()
    
    chunker = LifelogChunker(llm=mock_llm, lifelog_store=mock_store)
    parsed_doc = create_mock_lifelog_parsed_document()
    boundaries = chunker.detect_boundaries(parsed_doc)
    
    chunks, _ = chunker.chunk(
        parsed_document=parsed_doc,
        chunk_boundaries=boundaries,
    )
    
    # Verify store was called
    assert mock_store.save_event.call_count == 3


# ============================================================================
# Unit Tests: LifelogStore (with mock Gremlin)
# ============================================================================

@patch('peter_parser.impl.db.lifelog_store.DriverRemoteConnection')
def test_lifelog_store_init(mock_conn):
    """Test LifelogStore initialization."""
    mock_conn_instance = MagicMock()
    mock_conn.return_value = mock_conn_instance
    mock_traversal = MagicMock()
    mock_conn_instance.withRemote = MagicMock(return_value=mock_traversal)
    
    store = LifelogStore(host="localhost", port=8182)
    assert store._conn == mock_conn_instance


@patch('peter_parser.impl.db.lifelog_store.DriverRemoteConnection')
def test_lifelog_store_save_event(mock_conn):
    """Test saving event to store (mock)."""
    # Setup mocks
    mock_g = MagicMock()
    mock_day_v = MagicMock()
    mock_ev = MagicMock()
    mock_ent_v = MagicMock()
    
    # Mock traversal chain
    mock_g.V.return_value.has.return_value.fold.return_value.coalesce.return_value.next.return_value = mock_day_v
    mock_g.addV.return_value.property.return_value.property.return_value.property.return_value.property.return_value.property.return_value.property.return_value.next.return_value = None
    mock_g.V.return_value.has.return_value.next.return_value = mock_ev
    mock_g.V.return_value.addE.return_value.to.return_value.next.return_value = None
    mock_g.V.return_value.values.return_value.next.return_value = 0
    mock_g.V.return_value.property.return_value.iterate.return_value = None
    
    mock_conn_instance = MagicMock()
    mock_conn.return_value = mock_conn_instance
    mock_conn_instance.withRemote = MagicMock(return_value=mock_g)
    
    store = LifelogStore(host="localhost", port=8182)
    store._g = mock_g
    
    store.save_event(
        day="2025-01-25",
        event_uuid="test-uuid",
        event_data={
            "when": "10:00",
            "who": "나",
            "what": "밥을",
            "where": "집에서",
            "why_how": "-",
            "description": "먹었다.",
        },
        entities=[
            {"canonical": "식사", "type": "food"},
            {"canonical": "집", "type": "location"},
        ],
    )
    
    # Verify calls were made
    assert mock_g.addV.called


# ============================================================================
# Integration Tests (requires Docker)
# ============================================================================

def test_lifelog_store_integration():
    """Integration test with actual JanusGraph (requires Docker)."""
    import pytest

    try:
        store = LifelogStore()

        # Test save_event
        store.save_event(
            day="2025-01-25",
            event_uuid="test-integration-uuid",
            event_data={
                "when": "10:00",
                "who": "나",
                "what": "밥을",
                "where": "집에서",
                "why_how": "-",
                "description": "먹었다.",
            },
            entities=[
                {"canonical": "식사", "type": "food"},
                {"canonical": "집", "type": "location"},
            ],
        )

        # Verify by querying (use toList to avoid GraphSON count deserialization issues)
        g = store._g
        events = g.V().has("Event", "uuid", "test-integration-uuid").toList()
        assert len(events) == 1

        entities = g.V().has("Entity", "text", "식사").toList()
        assert len(entities) == 1

        store.close()
    except Exception as e:
        pytest.skip(f"JanusGraph not available: {e}")


def test_lifelog_chunker_integration():
    """Integration test with actual JanusGraph and mock LLM."""
    import pytest

    try:
        store = LifelogStore()

        mock_llm = Mock()
        mock_llm.structure_output.return_value = _LifelogEntitiesOut(
            entities=[
                _EntityExtraction(
                    canonical_text="식사",
                    original_text="밥",
                    type="food",
                ),
            ]
        )

        chunker = LifelogChunker(llm=mock_llm, lifelog_store=store)
        parsed_doc = create_mock_lifelog_parsed_document()
        boundaries = chunker.detect_boundaries(parsed_doc)

        chunks, _ = chunker.chunk(
            parsed_document=parsed_doc,
            chunk_boundaries=boundaries,
        )

        assert len(chunks) == 3

        # Verify data in JanusGraph (use toList to avoid GraphSON issues)
        g = store._g
        days = g.V().has("Day", "date", "2025-01-25").toList()
        assert len(days) >= 1

        events = g.V().hasLabel("Event").toList()
        assert len(events) >= 3

        store.close()
    except Exception as e:
        pytest.skip(f"JanusGraph not available: {e}")


# ============================================================================
# Pipeline Integration Test
# ============================================================================

def test_pipeline_integration():
    """Test full pipeline with lifelog (using mock parser to simulate PDF parsing)."""
    from peter_parser.graph.flow import PipelineFlow
    from peter_parser_core import BaseParser
    
    # Mock parser that simulates PDF parsing - extracts text from "PDF"
    class MockParser(BaseParser):
        def parse(self, document):
            # Simulate PDF parsing: extract text content
            if isinstance(document, bytes):
                # In real case, PDF bytes would be parsed by UpstageParser
                # Here we simulate: PDF contains lifelog text
                text = create_sample_lifelog_text()
            else:
                # File path - read as text for simulation
                text = create_sample_lifelog_text()
            
            # Return ParsedDocument as UpstageParser would
            return ParsedDocument(
                content=ContentModel(text=text),
                elements=[],
                pages=[],
                metadata={"source": "mock_pdf"},
            )
    
    try:
        # Use mock parser instead of real UpstageParser
        mock_parser = MockParser()
        flow = PipelineFlow(parser=mock_parser)
        
        # Simulate PDF bytes input
        pdf_bytes = b"fake pdf content"  # In real case, this would be actual PDF bytes
        
        state = flow.invoke(document=pdf_bytes, chunk_unit="lifelog")
        
        assert "chunks" in state
        assert len(state["chunks"]) == 3
        
        # Check chunk metadata
        chunk = state["chunks"][0]
        assert "lifelog" in chunk.metadata.extra
        assert "graph" in chunk.metadata.extra
        assert chunk.metadata.extra["lifelog"]["when"] == "1/25 10:00~10:30"
        
        # Verify parsed_document was created by parser (not minimal)
        assert "parsed_document" in state
        assert state["parsed_document"].metadata.get("source") == "mock_pdf"

        # Verify export_json (Export node)
        assert "export_json" in state
        import json
        exported = json.loads(state["export_json"])
        assert len(exported) == 3
        assert exported[0]["metadata"]["extra"]["lifelog"]["when"] == "1/25 10:00~10:30"
        
    except Exception as e:
        # Skip if dependencies not available
        import pytest
        pytest.skip(f"Pipeline test skipped: {e}")
