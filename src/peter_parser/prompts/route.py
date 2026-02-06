"""Prompts for LLM-based document-type routing (4-case)."""

ROUTER_SYSTEM = """문서 타입을 다음 네 가지 중 정확히 하나로 분류합니다. 구분 기준을 우선 적용하세요.

- heading: 계층 구조가 분명한 문서. 절·조·항, 챕터·섹션·소제목이 반복되고, 각 항목 아래에 설명·정의·규정 같은 본문이 이어짐. 참조·규정·시방 성격의 정형 문서.
- plain: 위와 같은 계층·레이아웃·이벤트 나열이 뚜렷하지 않은 연속 텍스트. 일기, 메모, 에세이, 블로그 본문 등.
- slide: 한 페이지(한 화면) 단위로 구성된 발표/제안형. 한 장 안에 불릿·키워드·짧은 문장이 많고, 시각적 구획이 뚜렷함. 한 장이 하나의 메시지 단위인 레이아웃.
- lifelog: 이벤트·기록 단위로 나열된 문서. 시간·장소·행동·대상(언제/어디서/누가/무엇)이 반복되고, 일지·로그·일일 기록 형식. 항목 나열이 주를 이루고 연속 산문이 아님.

document_type 필드에 위 네 값 중 하나만 반환하세요."""

ROUTER_INSTRUCTION = """다음 문서 내용을 보고 document_type을 한 가지만 선택하세요.

<DOCUMENT>
{content}
</DOCUMENT>
"""


ROUTER_VLM_SYSTEM = """문서 타입을 다음 네 가지 중 정확히 하나로 분류합니다. 구분 기준을 우선 적용하세요.

- heading: 계층 구조가 분명한 문서. 절·조·항, 챕터·섹션·소제목이 반복되고, 각 항목 아래에 설명·정의·규정 같은 본문이 이어짐. 참조·규정·시방 성격의 정형 문서.
- plain: 위와 같은 계층·레이아웃·이벤트 나열이 뚜렷하지 않은 연속 텍스트. 일기, 메모, 에세이, 블로그 본문 등.
- slide: 한 페이지(한 화면) 단위로 구성된 발표/제안형. 한 장 안에 불릿·키워드·짧은 문장이 많고, 시각적 구획이 뚜렷함. 한 장이 하나의 메시지 단위인 레이아웃.
- lifelog: 이벤트·기록 단위로 나열된 문서. 시간·장소·행동·대상(언제/어디서/누가/무엇)이 반복되고, 일지·로그·일일 기록 형식. 항목 나열이 주를 이루고 연속 산문이 아님.

이미지는 문서에서 골라 낸 페이지들입니다. 레이아웃과 구조를 보고 document_type을 한 가지만 반환하세요. 레이아웃이 비슷해 보여도, 절·조·항 번호와 본문이 있으면 heading, 시간·이벤트 나열이면 lifelog, 한 장 단위 발표용 구성이면 slide로 구분하세요."""

ROUTER_VLM_INSTRUCTION = """아래 이미지들은 분류할 문서에서 골라 낸 {num_doc}페이지입니다.
{fewshot_note}

document_type을 heading / plain / slide / lifelog 중 하나로 선택하세요."""


def build_router_vlm_instruction(num_doc_images: int, has_fewshot: bool) -> str:
    """Build user instruction for VLM router (image-based classification)."""
    fewshot_note = (
        "이후 이미지들은 예시입니다(순서: heading, slide, lifelog). 참고하여 분류하세요."
        if has_fewshot
        else ""
    )
    return ROUTER_VLM_INSTRUCTION.format(
        num_doc=num_doc_images,
        fewshot_note=fewshot_note,
    ).strip()


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
