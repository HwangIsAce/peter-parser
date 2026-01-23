"""API test for parser pipeline with actual PDF file."""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

from peter_parser.graph.flow import PipelineFlow


def _find_pdf_file(fixtures_dir: Path) -> Path | None:
    """Find first PDF file in fixtures directory."""
    pdf_files = list(fixtures_dir.glob("*.pdf"))
    if pdf_files:
        return pdf_files[0]
    return None


def test_with_pdf_file():
    """Test with actual PDF file (file path)."""
    print("=" * 60)
    print("Testing Parser Pipeline with PDF File")
    print("=" * 60)
    
    try:
        # 1. PipelineFlow 초기화
        print("\n[1] Initializing PipelineFlow...")
        flow = PipelineFlow()
        print("✓ PipelineFlow initialized successfully")
        
        # 2. PDF 파일 찾기
        print("\n[2] Loading PDF file...")
        fixtures_dir = project_root / "tests" / "fixtures"
        
        # fixtures 디렉터리에서 PDF 파일 자동 찾기
        pdf_path = _find_pdf_file(fixtures_dir)
        
        if not pdf_path:
            print(f"✗ No PDF file found in: {fixtures_dir}")
            print(f"  Please place a PDF file in: {fixtures_dir}")
            return
        
        print(f"✓ PDF file found: {pdf_path.name}")
        print(f"  Full path: {pdf_path}")
        print(f"  File size: {pdf_path.stat().st_size / 1024:.2f} KB")
        
        # 3. 파이프라인 실행 (파일 경로로)
        print("\n[3] Executing pipeline with file path...")
        result = flow.invoke(str(pdf_path))
        print("✓ Pipeline executed successfully")
        
        # 4. 결과 출력
        _print_results(result)
        
    except ValueError as e:
        print(f"\n✗ Configuration error: {e}")
        print("  Make sure .env file exists with UPSTAGE_API_KEY")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


def test_with_pdf_bytes():
    """Test with actual PDF file (bytes)."""
    print("=" * 60)
    print("Testing Parser Pipeline with PDF Bytes")
    print("=" * 60)
    
    try:
        # 1. PipelineFlow 초기화
        print("\n[1] Initializing PipelineFlow...")
        flow = PipelineFlow()
        print("✓ PipelineFlow initialized successfully")
        
        # 2. PDF 파일 찾기 및 읽기
        print("\n[2] Reading PDF file...")
        fixtures_dir = project_root / "tests" / "fixtures"
        pdf_path = _find_pdf_file(fixtures_dir)
        
        if not pdf_path:
            print(f"✗ No PDF file found in: {fixtures_dir}")
            return
        
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        
        print(f"✓ PDF file read: {pdf_path.name}")
        print(f"  Size: {len(pdf_bytes) / 1024:.2f} KB")
        
        # 3. 파이프라인 실행 (bytes로)
        print("\n[3] Executing pipeline with bytes...")
        result = flow.invoke(pdf_bytes)
        print("✓ Pipeline executed successfully")
        
        # 4. 결과 출력
        _print_results(result)
        
    except ValueError as e:
        print(f"\n✗ Configuration error: {e}")
        print("  Make sure .env file exists with UPSTAGE_API_KEY")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


def _print_results(result):
    """Print parsing results."""
    print("\n" + "=" * 60)
    print("[4] Parsing Results")
    print("=" * 60)
    
    if not result.get('parsed_document'):
        print("✗ No parsed document in result")
        return
    
    parsed_doc = result['parsed_document']
    
    print(f"\n✓ Parsed Document:")
    print(f"  - Pages: {len(parsed_doc.pages)}")
    print(f"  - Total content length: {len(parsed_doc.content)} characters")
    print(f"  - Tables: {len(parsed_doc.tables)}")
    print(f"  - Images: {len(parsed_doc.images)}")
    
    # 각 페이지 정보
    if parsed_doc.pages:
        print(f"\n  Page Details:")
        for i, page in enumerate(parsed_doc.pages[:3]):  # 처음 3페이지만
            print(f"    Page {page.page_number}:")
            print(f"      - Text length: {len(page.text)} chars")
            print(f"      - Tables: {len(page.tables)}")
            print(f"      - Images: {len(page.images)}")
            if page.text:
                preview = page.text[:100].replace('\n', ' ')
                print(f"      - Preview: {preview}...")
        
        if len(parsed_doc.pages) > 3:
            print(f"    ... and {len(parsed_doc.pages) - 3} more pages")
    
    # 테이블 정보
    if parsed_doc.tables:
        print(f"\n  Table Details:")
        for i, table in enumerate(parsed_doc.tables[:2]):  # 처음 2개만
            print(f"    Table {table.table_index}:")
            print(f"      - Page: {table.page_number}")
            print(f"      - Size: {table.rows}x{table.columns}")
            print(f"      - Cells: {len(table.cells)}")
    
    # 전체 텍스트 미리보기
    if parsed_doc.content:
        print(f"\n  Content Preview (first 500 chars):")
        print(f"  {'-' * 58}")
        print(f"  {parsed_doc.content[:500]}...")
        print(f"  {'-' * 58}")
    
    print("\n" + "=" * 60)
    print("✓ Test completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    # 파일 경로로 테스트
    test_with_pdf_file()
    
    print("\n\n")
    
    # bytes로 테스트 (선택)
    # test_with_pdf_bytes()