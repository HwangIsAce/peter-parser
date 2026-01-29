"""Prompts for LLM-based document-type routing (4-case)."""

ROUTER_SYSTEM = """문서 내용을 보고 문서 타입을 다음 네 가지 중 하나로 분류합니다.

- heading: 제목/헤딩 구조가 있는 정형 문서 (논문, 보고서, 계약서 등). 섹션·챕터가 명확함.
- plain: 헤딩 구조 없이 흐름 있는 비정형 텍스트 (일기, 메모, 블로그 본문 등).
- slide: 슬라이드/발표 자료 형식. 불릿, 짧은 문장, 페이지 단위 구성.
- lifelog: 5W1H(언제/누가/무엇을/어디서/왜·어떻게) 형식의 일일 기록. 시간·장소·행동이 이벤트 단위로 나열됨.

반드시 document_type 필드에 위 네 값 중 하나만 반환하세요."""

ROUTER_INSTRUCTION = """다음 문서 내용을 보고 document_type을 한 가지만 선택하세요.

<DOCUMENT>
{content}
</DOCUMENT>
"""


def build_router_instruction(
    content: str,
    file_extension: str | None = None,
    title: str | None = None,
) -> str:
    """Build user instruction for the router, optionally including file_extension and title."""
    parts = []
    if file_extension:
        parts.append(f"파일 확장자: {file_extension}")
    if title:
        parts.append(f"제목: {title}")
    if parts:
        prefix = "\n".join(parts) + "\n\n"
    else:
        prefix = ""
    return ROUTER_INSTRUCTION.format(content=prefix + (content or "(내용 없음)"))
