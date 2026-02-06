#!/usr/bin/env python3
"""
현재 설정된 LLM/VLM 엔드포인트를 출력하고, Qwen LLM(텍스트)과 VLM(이미지) 호출이
정상 동작하는지 한 번씩 요청을 보내서 확인합니다.

사용: uv run python scripts/check_llm_vlm_endpoints.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from peter_parser.common.config import Config
from peter_parser.impl.router.llm_router import LLMRouter
from peter_parser.impl.router.vlm_router import VLMRouter
from peter_parser.common.document_render import document_to_page_images


def main() -> None:
    base = Config.OPENAI_BASE_URL or "(비어있음 → OpenAI 기본 URL)"
    vision = Config.OPENAI_VISION_BASE_URL or "(비어있음 → OPENAI_BASE_URL와 동일 클라이언트)"
    llm_model = Config.OPENAI_MODEL
    vlm_model = Config.OPENAI_VISION_MODEL
    api_key = Config.OPENAI_API_KEY or ""

    is_qwen = "qwen" in (base + vision + llm_model + vlm_model).lower()

    print("=== 현재 LLM/VLM 설정 ===")
    print(f"  OPENAI_BASE_URL:       {base}")
    print(f"  OPENAI_VISION_BASE_URL: {vision}")
    print(f"  OPENAI_API_KEY:        {'설정됨 (길이 %d)' % len(api_key) if api_key else "비어있음 (요청 시 'dummy' 사용)"}")
    print(f"  OPENAI_MODEL:          {llm_model}")
    print(f"  OPENAI_VISION_MODEL:   {vlm_model}")
    print(f"  추정: {'Qwen 호환 엔드포인트' if is_qwen else 'OpenAI 또는 기타 호환 엔드포인트'}")
    if base and not base.startswith("("):
        print(f"  실제 요청: POST {base.rstrip('/')}/chat/completions (model로 LLM/VLM 구분)")
    print()

    # ----- 서버 도달 확인: GET /v1/models -----
    if base and not base.startswith("("):
        print("=== 0. 서버 도달 확인 (GET /models) ===")
        try:
            import httpx
            url = base.rstrip("/") + "/models"
            r = httpx.get(url, timeout=10.0)
            print(f"    GET {url}  →  HTTP {r.status_code}")
            if r.status_code != 200:
                print(f"    응답 본문(일부): {r.text[:200]}")
        except Exception as e:
            print(f"    실패: {e}")
        print()

    # ----- LLM (텍스트만) 호출 테스트 (예외 시 실패로 표시, router는 예외 시 'plain' 반환해서 실패 숨김) -----
    print("=== 1. LLM 호출 (텍스트만, Route 분류) ===")
    print(f"    요청: POST {base.rstrip('/') if base and not base.startswith('(') else base}/chat/completions  model={llm_model}")
    try:
        router = LLMRouter()
        # 실제로 요청이 나가는지 확인하려면 예외를 받아서 출력 (router.route는 실패 시 'plain' 반환함)
        from peter_parser.impl.router.schema import RouterSchema
        from peter_parser.prompts.route import ROUTER_SYSTEM, build_router_instruction
        snippet = "이 문서는 건축 일반공통사항에 대한 기술지침서입니다. 제1장 총칙..."
        instruction = build_router_instruction(content=snippet, file_extension="pdf", title="일반공통사항")
        out = router.llm.structure_output(
            instruction=instruction,
            user_system_prompt=ROUTER_SYSTEM,
            datamodel=RouterSchema,
        )
        doc_type = getattr(out, "document_type", None) or "plain"
        print(f"    결과: document_type = {doc_type!r}  → LLM 호출 성공 (서버 응답 수신)")
    except Exception as e:
        print(f"    실패 (서버 미도달 또는 API 오류): {e}")
    print()

    # ----- VLM (이미지) 호출 테스트 -----
    print("=== 2. VLM 호출 (이미지, Route 분류) ===")
    pdf_dir = ROOT / "docs" / "input"
    if not pdf_dir.is_dir():
        pdf_dir = ROOT / "tests" / "fixtures"
    pdfs = list(pdf_dir.glob("*.pdf")) if pdf_dir.is_dir() else []
    if not pdfs:
        print("    건너뜀: PDF 없음 (docs/input 또는 tests/fixtures)")
    else:
        sample_pdf = pdfs[0]
        doc_bytes = sample_pdf.read_bytes()
        images = document_to_page_images(doc_bytes, max_pages=2, sample="uniform")
        if not images:
            print("    건너뜀: 페이지 이미지 추출 실패")
        else:
            print(f"    요청: POST (동일 URL)  model={vlm_model}")
            print(f"    샘플 PDF: {sample_pdf.name}, 이미지 {len(images)}장")
            try:
                vlm_router = VLMRouter()
                from peter_parser.prompts.route import ROUTER_VLM_SYSTEM, build_router_vlm_instruction
                from peter_parser.impl.router.fewshot_loader import get_router_fewshot_images, TYPES
                instruction = build_router_vlm_instruction(num_doc_images=len(images), has_fewshot=False)
                extra = []
                for t in TYPES:
                    extra.extend(get_router_fewshot_images().get(t, []))
                all_images = images + extra
                out = vlm_router.llm.structure_output(
                    instruction=instruction,
                    user_system_prompt=ROUTER_VLM_SYSTEM,
                    datamodel=RouterSchema,
                    images=all_images,
                )
                doc_type = getattr(out, "document_type", None) or "plain"
                print(f"    결과: document_type = {doc_type!r}  → VLM 호출 성공 (서버 응답 수신)")
            except Exception as e:
                print(f"    실패 (서버 미도달 또는 API 오류): {e}")
    print()
    print("=== 완료 ===")


if __name__ == "__main__":
    main()
