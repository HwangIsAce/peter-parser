"""Unit tests for LLMRouter and RouterSchema."""
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock

project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

from peter_parser.impl.router.schema import RouterSchema, DocumentTypeLiteral
from peter_parser.common.config import Config
from peter_parser.impl.router.llm_router import LLMRouter
from peter_parser.impl.router.vlm_router import VLMRouter
from peter_parser.prompts.route import (
    ROUTER_SYSTEM,
    build_router_instruction,
    build_router_vlm_instruction,
)


# ============================================================================
# RouterSchema
# ============================================================================

def test_router_schema_valid_types():
    """RouterSchema accepts all four document types."""
    for dt in ("heading", "plain", "slide", "lifelog"):
        out = RouterSchema(document_type=dt)
        assert out.document_type == dt


def test_router_schema_required():
    """RouterSchema requires document_type."""
    try:
        RouterSchema()
    except Exception as e:
        assert "document_type" in str(e).lower() or "required" in str(e).lower()


# ============================================================================
# build_router_instruction
# ============================================================================

def test_build_router_instruction_content_only():
    """Instruction contains only content when no file_extension/title."""
    s = build_router_instruction("Hello world")
    assert "Hello world" in s
    assert "DOCUMENT" in s


def test_build_router_instruction_with_hints():
    """Instruction includes file_extension and title when provided."""
    s = build_router_instruction("Body", file_extension="pdf", title="Report")
    assert "pdf" in s
    assert "Report" in s
    assert "Body" in s


def test_build_router_instruction_empty_content():
    """Empty content is replaced with placeholder."""
    s = build_router_instruction("")
    assert "(내용 없음)" in s


# ============================================================================
# LLMRouter with mocked LLM
# ============================================================================

def test_llm_router_returns_heading():
    """LLMRouter.route returns 'heading' when LLM returns heading."""
    mock_llm = Mock()
    mock_llm.structure_output.return_value = RouterSchema(document_type="heading")
    router = LLMRouter(llm=mock_llm)
    result = router.route("1. Introduction\n2. Methods\n3. Results")
    assert result == "heading"
    mock_llm.structure_output.assert_called_once()


def test_llm_router_returns_plain():
    """LLMRouter.route returns 'plain' when LLM returns plain."""
    mock_llm = Mock()
    mock_llm.structure_output.return_value = RouterSchema(document_type="plain")
    router = LLMRouter(llm=mock_llm)
    result = router.route("오늘 날씨가 좋았다. 산책을 했다.")
    assert result == "plain"


def test_llm_router_returns_slide():
    """LLMRouter.route returns 'slide' when LLM returns slide."""
    mock_llm = Mock()
    mock_llm.structure_output.return_value = RouterSchema(document_type="slide")
    router = LLMRouter(llm=mock_llm)
    result = router.route("• Item 1\n• Item 2\n• Item 3")
    assert result == "slide"


def test_llm_router_returns_lifelog():
    """LLMRouter.route returns 'lifelog' when LLM returns lifelog."""
    mock_llm = Mock()
    mock_llm.structure_output.return_value = RouterSchema(document_type="lifelog")
    router = LLMRouter(llm=mock_llm)
    text = "1/25 10:00\n나\n밥을\n집에서\n-\n먹었다."
    result = router.route(text)
    assert result == "lifelog"


def test_llm_router_passes_instruction_and_prompt():
    """LLMRouter passes correct instruction and ROUTER_SYSTEM to structure_output."""
    mock_llm = Mock()
    mock_llm.structure_output.return_value = RouterSchema(document_type="plain")
    router = LLMRouter(llm=mock_llm)
    router.route("Some content", file_extension="pdf", title="Doc")
    call_kw = mock_llm.structure_output.call_args[1]
    assert "Some content" in call_kw["instruction"]
    assert "pdf" in call_kw["instruction"]
    assert "Doc" in call_kw["instruction"]
    assert call_kw["user_system_prompt"] == ROUTER_SYSTEM
    assert call_kw["datamodel"] == RouterSchema


def test_llm_router_truncates_long_content():
    """LLMRouter truncates content to Config.ROUTER_CONTENT_MAX_CHARS."""
    mock_llm = Mock()
    mock_llm.structure_output.return_value = RouterSchema(document_type="plain")
    router = LLMRouter(llm=mock_llm)
    max_chars = Config.ROUTER_CONTENT_MAX_CHARS
    long_content = "x" * (max_chars + 1000)
    router.route(long_content)
    instruction = mock_llm.structure_output.call_args[1]["instruction"]
    assert len(instruction) <= max_chars + 200  # plus XML/prompt wrapper


def test_llm_router_fallback_on_exception():
    """LLMRouter returns 'plain' when structure_output raises."""
    mock_llm = Mock()
    mock_llm.structure_output.side_effect = Exception("API error")
    router = LLMRouter(llm=mock_llm)
    result = router.route("Anything")
    assert result == "plain"


def test_llm_router_fallback_on_invalid_type():
    """LLMRouter returns 'plain' when LLM returns invalid document_type."""
    mock_llm = Mock()
    out = Mock()
    out.document_type = "unknown_type"
    mock_llm.structure_output.return_value = out
    router = LLMRouter(llm=mock_llm)
    result = router.route("Anything")
    assert result == "plain"


def test_llm_router_fallback_on_none_type():
    """LLMRouter returns 'plain' when document_type is None."""
    mock_llm = Mock()
    out = Mock()
    out.document_type = None
    mock_llm.structure_output.return_value = out
    router = LLMRouter(llm=mock_llm)
    result = router.route("Anything")
    assert result == "plain"


# ============================================================================
# VLM Router
# ============================================================================


def test_build_router_vlm_instruction():
    s = build_router_vlm_instruction(3, has_fewshot=True)
    assert "3" in s or "페이지" in s
    assert "예시" in s or "heading" in s
    s2 = build_router_vlm_instruction(2, has_fewshot=False)
    assert "2" in s2 or "페이지" in s2


def test_vlm_router_empty_images_returns_none():
    router = VLMRouter()
    assert router.route([]) is None
    assert router.route(page_images=[]) is None


def test_vlm_router_returns_type_with_mock():
    mock_llm = Mock()
    mock_llm.structure_output.return_value = RouterSchema(document_type="slide")
    router = VLMRouter(llm=mock_llm)
    result = router.route([b"\x89PNG\r\n\x1a\n" + b"\x00" * 100])  # minimal PNG-like
    assert result == "slide"
    mock_llm.structure_output.assert_called_once()
    call_kw = mock_llm.structure_output.call_args[1]
    assert call_kw["images"]
    assert call_kw["datamodel"] == RouterSchema


def test_vlm_router_fallback_on_exception():
    mock_llm = Mock()
    mock_llm.structure_output.side_effect = Exception("VLM error")
    router = VLMRouter(llm=mock_llm)
    result = router.route([b"fake image bytes"])
    assert result == "plain"
