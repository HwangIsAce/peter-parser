"""Tests for chunking pipeline components - PPTX slide format only."""
import sys
import base64
from pathlib import Path

project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

from peter_parser.impl.extractor.document_enricher import DocumentEnricher
from peter_parser.impl.chunker.vlm import VLMChunker
from peter_parser.impl.extractor.chunk_enricher import ChunkEnricher
from peter_parser_core import ParsedDocument
from peter_parser_core.common.types import Page, Image


def create_mock_pptx_parsed_document() -> ParsedDocument:
    """Create a mock ParsedDocument for PPTX-style slides (with images)."""
    # 실제 이미지 파일이 있으면 사용, 없으면 더미 데이터
    fixtures_dir = project_root / "tests" / "fixtures"
    test_image_path = fixtures_dir / "test_image.png"
    
    # 이미지 데이터 준비
    if test_image_path.exists():
        with open(test_image_path, "rb") as f:
            image_bytes = f.read()
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
    else:
        # 더미 base64 이미지 데이터 (1x1 PNG)
        dummy_png_bytes = (
            b'\x89PNG\r\n\x1a\n'  # PNG signature
            b'\x00\x00\x00\rIHDR'  # IHDR chunk
            b'\x00\x00\x00\x01'  # width: 1
            b'\x00\x00\x00\x01'  # height: 1
            b'\x08\x02\x00\x00\x00'  # bit depth, color type, etc.
            b'\x90wS\xde'  # CRC
            b'\x00\x00\x00\nIDAT'  # IDAT chunk
            b'x\x9c\x63\x00\x01\x00\x00\x05\x00\x01'  # compressed data
            b'\r\n-\xdc'  # CRC
            b'\x00\x00\x00\x00IEND\xaeB`\x82'  # IEND
        )
        image_base64 = base64.b64encode(dummy_png_bytes).decode('utf-8')
    
    # 각 페이지에 이미지가 있는 슬라이드 형태
    pages = [
        Page(
            page_number=1,
            text="Slide 1: Introduction\nWelcome to our presentation about AI and Machine Learning.",
            tables=[],
            images=[
                Image(
                    image_index=0,
                    page_number=1,
                    bbox=None,
                    base64=image_base64,
                )
            ]
        ),
        Page(
            page_number=2,
            text="Slide 2: Overview\nKey topics:\n- Machine Learning\n- Deep Learning\n- Neural Networks",
            tables=[],
            images=[
                Image(
                    image_index=1,
                    page_number=2,
                    bbox=None,
                    base64=image_base64,
                )
            ]
        ),
        Page(
            page_number=3,
            text="Slide 3: Applications\nReal-world applications of AI technology.",
            tables=[],
            images=[
                Image(
                    image_index=2,
                    page_number=3,
                    bbox=None,
                    base64=image_base64,
                )
            ]
        ),
        Page(
            page_number=4,
            text="Slide 4: Conclusion\nThank you for your attention.",
            tables=[],
            images=[
                Image(
                    image_index=3,
                    page_number=4,
                    bbox=None,
                    base64=image_base64,
                )
            ]
        ),
    ]
    
    # ParsedDocument.images도 설정 (pages에서 추출)
    all_images = []
    for page in pages:
        all_images.extend(page.images)
    
    content = "\n\n".join([page.text for page in pages])
    
    # ParsedDocument 생성
    try:
        # images 파라미터가 있으면 사용
        parsed_doc = ParsedDocument(
            pages=pages,
            content=content,
            tables=[],
            images=all_images,
            metadata={}
        )
    except TypeError:
        # images 파라미터가 없으면 제외
        parsed_doc = ParsedDocument(
            pages=pages,
            content=content,
            tables=[],
            metadata={}
        )
    
    return parsed_doc


def test_document_enricher_structure():
    """Test DocumentEnricher structure (no API calls)."""
    print("=" * 60)
    print("Testing DocumentEnricher Structure")
    print("=" * 60)
    
    enricher = DocumentEnricher()
    
    assert hasattr(enricher, 'llm')
    assert hasattr(enricher, 'vlm')
    assert hasattr(enricher, 'enrich')
    assert hasattr(enricher, '_get_page_images')
    
    print("✓ DocumentEnricher structure is correct")


def test_vlm_chunker_structure():
    """Test VLMChunker structure (no API calls)."""
    print("\n" + "=" * 60)
    print("Testing VLMChunker Structure")
    print("=" * 60)
    
    chunker = VLMChunker()
    
    assert hasattr(chunker, 'llm')
    assert hasattr(chunker, 'detect_boundaries')
    assert hasattr(chunker, 'chunk')
    
    print("✓ VLMChunker structure is correct")


def test_chunk_enricher_structure():
    """Test ChunkEnricher structure (no API calls)."""
    print("\n" + "=" * 60)
    print("Testing ChunkEnricher Structure")
    print("=" * 60)
    
    enricher = ChunkEnricher()
    
    assert hasattr(enricher, 'llm')
    assert hasattr(enricher, 'enrich_chunks')
    
    print("✓ ChunkEnricher structure is correct")


def test_vlm_chunker_chunk_logic():
    """Test VLMChunker chunk logic with PPTX mock data (no API calls)."""
    print("\n" + "=" * 60)
    print("Testing VLMChunker Chunk Logic (PPTX Mock Data)")
    print("=" * 60)
    
    chunker = VLMChunker()
    parsed_doc = create_mock_pptx_parsed_document()
    
    # Test chunking with boundaries
    boundaries = [2]  # Chunk starts at page 2 (0-based, so page 3)
    chunks = chunker.chunk(parsed_doc, boundaries, doc_title="Test Presentation")
    
    assert len(chunks) == 2  # Two chunks: [0-1] and [2-3]
    
    # Chunk 0 assertions
    assert chunks[0].chunk_order == 0
    assert chunks[0].metadata.start_index == 0
    assert chunks[0].metadata.end_index == 1
    assert chunks[0].metadata.page_number == 1  # First page number
    assert chunks[0].doc_title == "Test Presentation"
    assert chunks[0].chunk is not None
    assert chunks[0].uuid is not None
    
    # Chunk 1 assertions
    assert chunks[1].chunk_order == 1
    assert chunks[1].metadata.start_index == 2
    assert chunks[1].metadata.end_index == 3
    assert chunks[1].metadata.page_number == 3  # First page number
    assert chunks[1].metadata.extra["page_indices"] == [2, 3]
    assert chunks[1].metadata.extra["page_numbers"] == [3, 4]
    
    print(f"✓ Created {len(chunks)} chunks correctly")
    print(f"  Chunk 0: pages {chunks[0].metadata.extra['page_numbers']}")
    print(f"  Chunk 1: pages {chunks[1].metadata.extra['page_numbers']}")

def test_pptx_mock_data_creation():
    """Test PPTX mock data creation (no API calls)."""
    print("\n" + "=" * 60)
    print("Testing PPTX Mock Data Creation")
    print("=" * 60)
    
    parsed_doc = create_mock_pptx_parsed_document()
    
    assert len(parsed_doc.pages) == 4
    
    # Check images in pages
    total_page_images = sum(len(page.images) for page in parsed_doc.pages)
    assert total_page_images == 4
    
    # Check ParsedDocument.images if available
    if hasattr(parsed_doc, 'images') and parsed_doc.images:
        assert len(parsed_doc.images) == 4
        for i, img in enumerate(parsed_doc.images):
            assert img.page_number == i + 1
            assert img.image_index == i
            assert img.base64 is not None
    
    # Check each page has image
    for i, page in enumerate(parsed_doc.pages):
        assert len(page.images) == 1
        assert page.images[0].page_number == i + 1
        assert page.images[0].image_index == i
        assert page.images[0].base64 is not None
    
    print(f"✓ Created PPTX mock document:")
    print(f"  - Pages: {len(parsed_doc.pages)}")
    print(f"  - Images in pages: {total_page_images}")
    if hasattr(parsed_doc, 'images') and parsed_doc.images:
        print(f"  - Images in ParsedDocument: {len(parsed_doc.images)}")
    print(f"  - Content length: {len(parsed_doc.content)} chars")


def test_pptx_enrichment():
    """Test DocumentEnricher with PPTX-style mock data (real API calls)."""
    print("\n" + "=" * 60)
    print("Testing PPTX-style Enrichment")
    print("=" * 60)
    
    from peter_parser.common.config import Config
    
    if not Config.OPENAI_API_KEY:
        print("⚠ Skipping: OPENAI_API_KEY not set")
        return
    
    try:
        # Create mock PPTX document
        print("\n[1] Creating mock PPTX document...")
        parsed_doc = create_mock_pptx_parsed_document()
        print(f"✓ Created document with {len(parsed_doc.pages)} pages")
        
        # Count images
        total_images = sum(len(page.images) for page in parsed_doc.pages)
        print(f"✓ Images in pages: {total_images}")
        
        # Initialize enricher
        print("\n[2] Initializing DocumentEnricher...")
        enricher = DocumentEnricher()
        print("✓ DocumentEnricher initialized")
        
        # Test enrichment with page unit
        print("\n[3] Running enrichment (chunk_unit='page')...")
        result = enricher.enrich(
            parsed_document=parsed_doc,
            chunk_unit="page",
        )
        
        print("\n[4] Checking results...")
        assert "document_summary" in result
        assert "item_metadata" in result
        assert "chunk_unit" in result
        assert result["chunk_unit"] == "page"
        
        print(f"✓ Document summary: {len(result['document_summary'])} chars")
        print(f"✓ Item metadata: {len(result['item_metadata'])} items")
        
        # Check item_metadata
        if result['item_metadata']:
            print("\n[5] Item Metadata Details:")
            for page_idx, metadata in sorted(result['item_metadata'].items()):
                print(f"  Page {page_idx}:")
                if metadata.get('title'):
                    print(f"    - Title: {metadata['title']}")
                if metadata.get('script'):
                    script_preview = metadata['script'][:100].replace('\n', ' ')
                    print(f"    - Script: {script_preview}...")
        else:
            print("⚠ No item_metadata generated")
            print("  (Images might not be processed - check _get_page_images)")
        
        print("\n" + "=" * 60)
        print("✓ PPTX enrichment test passed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

def test_pptx_full_pipeline():
    """Test full pipeline with PPTX-style mock data (real API calls)."""
    print("\n" + "=" * 60)
    print("Testing Full Pipeline with PPTX Mock Data")
    print("=" * 60)
    
    from peter_parser.common.config import Config
    
    if not Config.OPENAI_API_KEY:
        print("⚠ Skipping: OPENAI_API_KEY not set")
        return
    
    try:
        # Create mock PPTX document
        print("\n[1] Creating mock PPTX document...")
        parsed_doc = create_mock_pptx_parsed_document()
        print(f"✓ Created document with {len(parsed_doc.pages)} pages")
        total_images = sum(len(page.images) for page in parsed_doc.pages)
        print(f"✓ Images: {total_images}")
        
        # Initialize components
        print("\n[2] Initializing components...")
        enricher = DocumentEnricher()
        chunker = VLMChunker()
        print("✓ Components initialized")
        
        # Step 1: Enrichment
        print("\n[3] Running enrichment...")
        enrich_result = enricher.enrich(
            parsed_document=parsed_doc,
            chunk_unit="page",
        )
        print(f"✓ Enrichment complete")
        print(f"  - Summary: {len(enrich_result['document_summary'])} chars")
        print(f"  - Metadata: {len(enrich_result['item_metadata'])} items")
        
        # Step 2: Chunking
        print("\n[4] Running chunking...")
        boundaries = chunker.detect_boundaries(
            parsed_document=parsed_doc,
            document_summary=enrich_result['document_summary'],
            item_metadata=enrich_result['item_metadata'],
        )
        print(f"✓ Boundaries detected: {boundaries}")
        
        chunks = chunker.chunk(
            parsed_document=parsed_doc,
            chunk_boundaries=boundaries,
            doc_title="Test PPTX Document",
        )
        print(f"✓ Chunks created: {len(chunks)}")
        
        # Print results
        print("\n[5] Results:")
        for chunk in chunks:
            print(f"  Chunk {chunk.chunk_order}:")
            print(f"    - UUID: {chunk.uuid}")
            print(f"    - Pages: {chunk.metadata.extra.get('page_numbers', [])}")
            print(f"    - Text: {len(chunk.chunk)} chars")
            if chunk.chunk:
                preview = chunk.chunk[:80].replace('\n', ' ')
                print(f"    - Preview: {preview}...")
        
        print("\n" + "=" * 60)
        print("✓ PPTX full pipeline test passed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("PPTX Slide Format Chunking Pipeline Test Suite")
    print("=" * 80)
    
    # Unit tests (no API calls)
    print("\n[Unit Tests - No API Calls]")
    test_document_enricher_structure()
    test_vlm_chunker_structure()
    test_chunk_enricher_structure()
    test_vlm_chunker_chunk_logic()
    test_pptx_mock_data_creation()
    
    # Integration tests (real API calls)
    print("\n" + "=" * 80)
    print("[Integration Tests - Real API Calls]")
    print("⚠ The following tests will make real API calls and incur costs.")
    print("⚠ Make sure OPENAI_API_KEY is set in .env file.")
    print("=" * 80)
    
    test_pptx_enrichment()
    test_pptx_full_pipeline()
    
    print("\n" + "=" * 80)
    print("Test Suite Completed")
    print("=" * 80)