"""Tests for document_render (PDF page sampling for VLM router)."""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

from peter_parser.common.document_render import document_to_page_images, _is_pdf, PDF_MAGIC


def test_is_pdf():
    assert _is_pdf(b"%PDF-1.4 something") is True
    assert _is_pdf(b"%PDF") is True
    assert _is_pdf(b"") is False
    assert _is_pdf(b"not a pdf") is False
    assert _is_pdf(None) is False


def test_document_to_page_images_empty():
    assert document_to_page_images(b"") == []
    assert document_to_page_images(b"not pdf") == []


def test_document_to_page_images_pdf_fixture():
    """If fixtures have a PDF, we should get up to max_pages images."""
    fixtures = project_root / "tests" / "fixtures"
    pdfs = list(fixtures.glob("*.pdf"))
    if not pdfs:
        return
    doc = pdfs[0].read_bytes()
    images = document_to_page_images(doc, max_pages=2, sample="uniform")
    assert isinstance(images, list)
    assert len(images) <= 2
    for img in images:
        assert isinstance(img, bytes)
        assert img[:8] == b"\x89PNG\r\n\x1a\n"  # PNG magic
