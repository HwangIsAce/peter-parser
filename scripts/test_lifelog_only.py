#!/usr/bin/env python3
"""Test lifelog with raw text input (extract from PDF or use text file)."""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))


def _extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text from PDF using pymupdf (for lifelog: parse bypass)."""
    import fitz
    doc = fitz.open(pdf_path)
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return text


def main() -> None:
    import os
    os.environ.setdefault("PIPELINE_PROGRESS", "1")
    from peter_parser.graph.flow import PipelineFlow
    from peter_parser_core import BaseParser
    from peter_parser_core.common.types import ContentModel
    from peter_parser_core import ParsedDocument

    path = project_root / "docs" / "input" / "lifelog_sample.pdf"
    if not path.exists():
        print(f"ERROR: {path} not found")
        sys.exit(1)

    print(f"Testing: {path.name} (lifelog: text extracted from PDF)")
    print(f"Expected document_type: lifelog")
    print("-" * 50)

    document = _extract_text_from_pdf(path)
    # MockParser: lifelog path skips parse, so parser is never used
    class MockParser(BaseParser):
        def parse(self, doc):
            return ParsedDocument(content=ContentModel(text=""), elements=[], pages=[], metadata={})
    flow = PipelineFlow(parser=MockParser())
    result = flow.invoke(document, document_type="lifelog")

    dt = result.get("document_type", "?")
    chunks = result.get("chunks") or []
    export_json = result.get("export_json", "")

    print(f"document_type: {dt}")
    print(f"chunks: {len(chunks)}")
    print(f"export_json length: {len(export_json) if export_json else 0} bytes")
    print()
    status = "OK" if dt == "lifelog" else f"MISMATCH (expected lifelog, got {dt})"
    print(f"Status: {status}")
    if chunks:
        print(f"First chunk keys: {list(chunks[0].keys())}")
    print("Done.")

if __name__ == "__main__":
    main()
