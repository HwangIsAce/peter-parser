#!/usr/bin/env python3
"""
현재 프로세스에서 로드되는 .env 기준으로 OPENAI_BASE_URL과 GPU 서버 연결을 확인합니다.
Chunking 작업은 RQ worker 프로세스에서 실행되므로, .env 수정 후에는 반드시 worker를 재시작해야 합니다.

사용: cd peter-parser && uv run python scripts/check_gpu_env.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from peter_parser.common.config import Config


def main() -> int:
    base = (Config.OPENAI_BASE_URL or "").strip()
    vision = (Config.OPENAI_VISION_BASE_URL or "").strip()

    print("=== 1. 현재 이 프로세스가 읽은 설정 ===")
    print(f"   .env 경로(추정): {ROOT / '.env'}")
    print(f"   OPENAI_BASE_URL       = {base or '(비어 있음 → OpenAI 기본 URL 사용)'}")
    print(f"   OPENAI_VISION_BASE_URL = {vision or '(비어 있음 → LLM과 동일)'}")
    print(f"   OPENAI_MODEL           = {Config.OPENAI_MODEL}")
    print(f"   OPENAI_VISION_MODEL   = {Config.OPENAI_VISION_MODEL}")
    print()

    if not base or base.startswith("("):
        print("   ⚠ OPENAI_BASE_URL이 비어 있으면 GPU 서버가 아닌 OpenAI 기본 URL로 요청이 나갑니다.")
        print("   → .env에 OPENAI_BASE_URL=http://69.30.85.154:22089/v1 형태로 설정 후, worker 재시작")
        return 1

    # 연결 테스트 (비밀값 노출 없이). OpenAI 호환: /v1/models 또는 /models
    print("=== 2. GPU 서버 연결 테스트 ===")
    base_clean = base.rstrip("/")
    test_url = base_clean + "/models"  # e.g. http://69.30.85.154:22089/v1/models
    print(f"   GET {test_url}")

    try:
        import httpx
        r = httpx.get(test_url, timeout=10.0)
        print(f"   → HTTP {r.status_code}")
        if r.status_code == 200:
            print("   → 이 머신에서 GPU 서버로 연결됩니다.")
        else:
            print(f"   → 응답 내용(일부): {r.text[:150]}")
    except httpx.ConnectError as e:
        print(f"   → 연결 실패: {e}")
        print("   → 방화벽/VPN/네트워크 확인. worker도 같은 환경에서 실행되므로 동일해야 합니다.")
        return 1
    except httpx.TimeoutException as e:
        print(f"   → 타임아웃: {e}")
        return 1
    except Exception as e:
        print(f"   → 오류: {e}")
        return 1

    print()
    print("=== 3. RQ worker 안내 ===")
    print("   Chunking 작업은 RQ worker 프로세스에서 실행됩니다.")
    print("   .env를 수정했다면 worker를 반드시 재시작하세요:")
    print("     peter-parser 디렉터리에서: uv run python -m peter_parser.worker")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
