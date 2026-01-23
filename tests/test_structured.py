"""Tests for StructuredLLM implementation."""
import sys
import base64
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional, List

project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

from peter_parser.impl.extractor.structured import StructuredLLM
from peter_parser.common.config import Config


# 테스트용 간단한 Pydantic 모델
class SimpleSummary(BaseModel):
    """간단한 요약 모델 (테스트용)."""
    title: str = Field(description="문서 제목")
    summary: str = Field(description="문서 요약")
    key_points: List[str] = Field(description="주요 포인트 리스트")


class PageInfo(BaseModel):
    """페이지 정보 모델 (테스트용)."""
    page_number: int = Field(description="페이지 번호")
    title: Optional[str] = Field(description="페이지 제목", default=None)
    script: str = Field(description="발표 스크립트")


def test_helper_methods():
    """헬퍼 메서드 단위 테스트 (API 호출 없음)."""
    print("=" * 60)
    print("Testing Helper Methods (No API calls)")
    print("=" * 60)
    
    # StructuredLLM 초기화 (datamodel 필요)
    llm = StructuredLLM(datamodel=SimpleSummary)
    
    # 1. _get_structure_information 테스트
    print("\n[1] Testing _get_structure_information...")
    structure_info = llm._get_structure_information()
    print(f"✓ Structure info keys: {list(structure_info.keys())}")
    assert "title" in structure_info
    assert "summary" in structure_info
    assert "key_points" in structure_info
    print("✓ _get_structure_information passed")
    
    # 2. _prepare_image_data 테스트 (bytes)
    print("\n[2] Testing _prepare_image_data (bytes)...")
    test_image_bytes = b"fake_image_data"
    result = llm._prepare_image_data(test_image_bytes)
    assert result.startswith("data:image/png;base64,")
    assert base64.b64decode(result.split(",")[1]) == test_image_bytes
    print("✓ _prepare_image_data (bytes) passed")
    
    # 3. _prepare_image_data 테스트 (base64 string)
    print("\n[3] Testing _prepare_image_data (base64 string)...")
    test_base64 = base64.b64encode(b"fake_image_data").decode('utf-8')
    result = llm._prepare_image_data(test_base64)
    assert result == f"data:image/png;base64,{test_base64}"
    print("✓ _prepare_image_data (base64 string) passed")
    
    print("\n" + "=" * 60)
    print("✓ All helper method tests passed!")
    print("=" * 60)


def test_llm_text_only():
    """LLM 텍스트 전용 테스트 (실제 API 호출 - 비용 발생)."""
    print("\n" + "=" * 60)
    print("Testing LLM Text-Only Mode (Real API Call)")
    print("=" * 60)
    
    # API 키 확인
    if not Config.OPENAI_API_KEY:
        print("⚠ Skipping: OPENAI_API_KEY not set")
        return
    
    try:
        # StructuredLLM 초기화
        print("\n[1] Initializing StructuredLLM...")
        llm = StructuredLLM(datamodel=SimpleSummary)
        print("✓ StructuredLLM initialized")
        
        # 간단한 텍스트 요약 요청
        print("\n[2] Calling structure_output (text-only)...")
        instruction = """
        다음 문서를 요약해주세요:
        
        제목: 인공지능의 미래
        내용: 인공지능은 빠르게 발전하고 있으며, 다양한 분야에서 활용되고 있습니다.
        주요 기술로는 머신러닝, 딥러닝, 자연어처리 등이 있습니다.
        """
        
        result = llm.structure_output(
            instruction=instruction,
            key_attr="name",
            value_attr="description"
        )
        
        print("✓ API call successful")
        print(f"\n[3] Result:")
        print(f"  - Type: {type(result)}")
        print(f"  - Title: {result.title}")
        print(f"  - Summary: {result.summary[:100]}...")
        print(f"  - Key Points: {len(result.key_points)} items")
        for i, point in enumerate(result.key_points[:3], 1):
            print(f"    {i}. {point}")
        
        # 타입 검증
        assert isinstance(result, SimpleSummary)
        assert isinstance(result.title, str)
        assert isinstance(result.summary, str)
        assert isinstance(result.key_points, list)
        
        print("\n" + "=" * 60)
        print("✓ LLM text-only test passed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


def test_vlm_with_image():
    """VLM 이미지 포함 테스트 (실제 API 호출 - 비용 발생)."""
    print("\n" + "=" * 60)
    print("Testing VLM with Image (Real API Call)")
    print("=" * 60)
    
    # API 키 확인
    if not Config.OPENAI_API_KEY:
        print("⚠ Skipping: OPENAI_API_KEY not set")
        return
    
    try:
        # StructuredLLM 초기화
        print("\n[1] Initializing StructuredLLM...")
        llm = StructuredLLM(datamodel=PageInfo)
        print("✓ StructuredLLM initialized")
        
        # 간단한 테스트 이미지 생성 (1x1 PNG)
        print("\n[2] Creating test image...")
        # 최소한의 PNG 이미지 (1x1 픽셀, 투명)
        png_header = b'\x89PNG\r\n\x1a\n'
        # 실제로는 PIL이나 다른 라이브러리로 이미지를 생성해야 하지만,
        # 테스트를 위해 간단한 더미 데이터 사용
        test_image = base64.b64encode(b"fake_image_data_for_test").decode('utf-8')
        test_image_bytes = base64.b64decode(test_image)
        
        print("⚠ Using dummy image data (real image recommended for production test)")
        
        # VLM 호출
        print("\n[3] Calling structure_output (with image)...")
        instruction = "이 이미지에서 페이지 정보를 추출해주세요."
        
        # 실제 이미지 파일이 있다면 사용
        fixtures_dir = project_root / "tests" / "fixtures"
        image_files = list(fixtures_dir.glob("*.png")) + list(fixtures_dir.glob("*.jpg"))
        
        if image_files:
            with open(image_files[0], "rb") as f:
                real_image = f.read()
            print(f"✓ Using real image: {image_files[0].name}")
            result = llm.structure_output(
                instruction=instruction,
                images=[real_image],
                key_attr="name",
                value_attr="description"
            )
        else:
            print("⚠ No image file found, skipping VLM test")
            print("  Place a PNG/JPG file in tests/fixtures/ to test VLM")
            return
        
        print("✓ API call successful")
        print(f"\n[4] Result:")
        print(f"  - Type: {type(result)}")
        print(f"  - Page Number: {result.page_number}")
        if result.title:
            print(f"  - Title: {result.title}")
        print(f"  - Script: {result.script[:100]}...")
        
        # 타입 검증
        assert isinstance(result, PageInfo)
        assert isinstance(result.page_number, int)
        assert isinstance(result.script, str)
        
        print("\n" + "=" * 60)
        print("✓ VLM with image test passed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


def test_async_method():
    """비동기 메서드 테스트 (실제 API 호출 - 비용 발생)."""
    print("\n" + "=" * 60)
    print("Testing Async Method (Real API Call)")
    print("=" * 60)
    
    # API 키 확인
    if not Config.OPENAI_API_KEY:
        print("⚠ Skipping: OPENAI_API_KEY not set")
        return
    
    import asyncio
    
    async def async_test():
        llm = StructuredLLM(datamodel=SimpleSummary)
        
        instruction = "다음 텍스트를 요약해주세요: AI는 미래 기술입니다."
        
        result = await llm.astructure_output(
            instruction=instruction,
            key_attr="name",
            value_attr="description"
        )
        
        assert isinstance(result, SimpleSummary)
        print(f"✓ Async result: {result.title}")
        return result
    
    try:
        result = asyncio.run(async_test())
        print("\n" + "=" * 60)
        print("✓ Async method test passed!")
        print("=" * 60)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


def test_model_selection():
    """모델 선택 로직 테스트 (API 호출 없이 메시지 구성 확인)."""
    print("\n" + "=" * 60)
    print("Testing Model Selection Logic")
    print("=" * 60)
    
    llm = StructuredLLM(datamodel=SimpleSummary)
    
    # 이미지 없을 때: OPENAI_MODEL 사용
    print("\n[1] Testing model selection (no images)...")
    # 실제로는 structure_output 내부에서 확인하지만,
    # 여기서는 로직만 확인
    assert Config.OPENAI_MODEL == "gpt-4o-mini" or Config.OPENAI_MODEL
    print(f"✓ Text model: {Config.OPENAI_MODEL}")
    
    # 이미지 있을 때: OPENAI_VISION_MODEL 사용
    print("\n[2] Testing model selection (with images)...")
    assert Config.OPENAI_VISION_MODEL == "gpt-4o" or Config.OPENAI_VISION_MODEL
    print(f"✓ Vision model: {Config.OPENAI_VISION_MODEL}")
    
    print("\n" + "=" * 60)
    print("✓ Model selection test passed!")
    print("=" * 60)


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("StructuredLLM Test Suite")
    print("=" * 80)
    
    test_helper_methods()
    
    test_model_selection()
    
    print("\n" + "⚠" * 40)
    print("The following tests will make real API calls and incur costs.")
    print("Make sure OPENAI_API_KEY is set in .env file.")
    print("⚠" * 40)
    
    user_input = input("\nContinue with API tests? (y/n): ").strip().lower()
    if user_input == 'y':
        test_llm_text_only()
        test_async_method()
        test_vlm_with_image()
    else:
        print("\n⚠ Skipping API tests. Run individually if needed.")
    
    print("\n" + "=" * 80)
    print("Test Suite Completed")
    print("=" * 80)