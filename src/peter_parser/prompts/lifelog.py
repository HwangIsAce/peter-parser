"""Lifelog entity extraction prompts."""

LIFELOG_ENTITY_SYSTEM = """lifelog 이벤트에서 엔티티(장소, 음식, 인물, 활동, 사물 등)를 추출합니다.
동의어는 canonical form으로 통일하세요. 예: "밥","점심","식사" -> canonical "식사". "집","우리집" -> "집".
type: location | food | person | activity | object | other."""

LIFELOG_ENTITY_EXTRACTION = """<LIFELOG_EVENT>
when: {when}
who: {who}
what: {what}
where: {where}
why_how: {why_how}
description: {description}
</LIFELOG_EVENT>

위 이벤트에서 엔티티를 추출하세요. 각 엔티티에 대해 canonical_text, original_text, type을 반드시 채우세요."""
