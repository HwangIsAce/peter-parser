"""Tests for ExcelChunker."""
from __future__ import annotations

from peter_parser_core import ParsedDocument
from peter_parser_core.common.types import ContentModel, Page

from peter_parser.impl.chunker.excel import ExcelChunker


def _make_excel_doc(pages_text: list[str], sheet_names: list[str] | None = None) -> ParsedDocument:
    """Build ParsedDocument with given page texts (like Excel output)."""
    pages = []
    for i, text in enumerate(pages_text):
        pages.append(
            Page(
                page_number=i + 1,
                text=text,
                tables=[],
                images=[],
            )
        )
    full_text = "\n\n".join(pages_text)
    metadata: dict = {"source": "excel", "num_sheets": len(pages)}
    if sheet_names:
        metadata["sheet_names"] = sheet_names
    return ParsedDocument(
        pages=pages,
        elements=[],
        content=ContentModel(text=full_text),
        metadata=metadata,
    )


def test_excel_chunker_sheet_based():
    """ExcelChunker with default (sheet-based): one chunk per sheet."""
    doc = _make_excel_doc(
        ["Name\tValue\nfoo\t100\nbar\t200", "ID\tAmount\n1\t100"],
        sheet_names=["Sheet1", "Sheet2"],
    )
    chunker = ExcelChunker()
    boundaries = chunker.detect_boundaries(doc)
    assert boundaries == [1]
    chunks, updated = chunker.chunk(doc, boundaries)
    assert len(chunks) == 2
    assert "Name" in chunks[0].chunk
    assert "foo" in chunks[0].chunk
    assert "ID" in chunks[1].chunk
    assert "Amount" in chunks[1].chunk
    assert chunks[0].metadata.page_number == 1
    assert chunks[1].metadata.page_number == 2
    assert chunks[0].metadata.extra.get("excel", {}).get("sheet_name") == "Sheet1"
    assert chunks[1].metadata.extra.get("excel", {}).get("sheet_name") == "Sheet2"
    assert updated is doc


def test_excel_chunker_single_sheet():
    """ExcelChunker with one sheet returns one chunk, empty boundaries."""
    doc = _make_excel_doc(["A\tB\n1\t2"])
    chunker = ExcelChunker()
    boundaries = chunker.detect_boundaries(doc)
    assert boundaries == []
    chunks, _ = chunker.chunk(doc, boundaries)
    assert len(chunks) == 1
    assert "A" in chunks[0].chunk


def test_excel_chunker_empty_pages():
    """ExcelChunker with no pages returns no chunks."""
    doc = _make_excel_doc([])
    chunker = ExcelChunker()
    boundaries = chunker.detect_boundaries(doc)
    assert boundaries == []
    chunks, _ = chunker.chunk(doc, boundaries)
    assert len(chunks) == 0


def test_excel_chunker_row_based(monkeypatch):
    """ExcelChunker with EXCEL_CHUNK_ROWS splits by rows."""
    monkeypatch.setattr("peter_parser.impl.chunker.excel.Config.EXCEL_CHUNK_ROWS", 2)
    doc = _make_excel_doc(
        ["H1\tH2\nr1\tv1\nr2\tv2\nr3\tv3\nr4\tv4"],
        sheet_names=["Data"],
    )
    chunker = ExcelChunker()
    boundaries = chunker.detect_boundaries(doc)
    # 5 rows -> 2 rows each -> 3 units: [H1,H2,r1,r2], [r3,v3,r4,v4] ... wait
    # lines = ["H1\tH2", "r1\tv1", "r2\tv2", "r3\tv3", "r4\tv4"] -> 5 lines
    # rows_per_chunk=2: units are lines[0:2], lines[2:4], lines[4:5] -> 3 units
    # boundaries = [1, 2]
    assert boundaries == [1, 2]
    chunks, _ = chunker.chunk(doc, boundaries)
    assert len(chunks) == 3
    assert "H1" in chunks[0].chunk
    assert "r3" in chunks[1].chunk
    assert "r4" in chunks[2].chunk
