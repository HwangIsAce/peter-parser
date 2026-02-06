"""Lifelog chunker: 5W1H event-unit chunking + entity extraction + JanusGraph."""
from __future__ import annotations

import asyncio
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from peter_parser.common.config import Config
from peter_parser_core import ParsedDocument
from peter_parser_core.common.types import Chunk, ChunkMetadata, ContentModel

from peter_parser.impl.extractor.structured import StructuredLLM
from peter_parser.impl.db.lifelog_store import LifelogStore
from peter_parser.prompts.lifelog import LIFELOG_ENTITY_EXTRACTION, LIFELOG_ENTITY_SYSTEM


class LifelogEvent(BaseModel):
    when: str = ""
    who: str = ""
    what: str = ""
    where: str = ""
    why_how: str = ""
    description: str = ""


class _EntityExtraction(BaseModel):
    canonical_text: str = ""
    original_text: str = ""
    type: str = "other"


class _LifelogEntitiesOut(BaseModel):
    entities: List[_EntityExtraction] = Field(default_factory=list)


def _parse_lifelog_events(text: str) -> List[LifelogEvent]:
    events: List[LifelogEvent] = []
    blocks = re.split(r"\n\s*---\s*\n|\n{2,}", (text or "").strip())
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        lines = [ln.strip() for ln in block.split("\n")][:6]
        while len(lines) < 6:
            lines.append("")
        events.append(
            LifelogEvent(
                when=lines[0],
                who=lines[1],
                what=lines[2],
                where=lines[3],
                why_how=lines[4],
                description=lines[5],
            )
        )
    return events


def _ev_to_day(ev: LifelogEvent) -> str:
    s = (ev.when or "").strip()
    if not s:
        return "unknown"
    m = re.match(r"(\d{1,2})[/\-.](\d{1,2})", s)
    if m:
        return f"2025-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    return "unknown"


class LifelogChunker:
    def __init__(
        self,
        llm: Optional[StructuredLLM] = None,
        lifelog_store: Optional[LifelogStore] = None,
    ) -> None:
        self.llm = llm or StructuredLLM(datamodel=_LifelogEntitiesOut)
        self.lifelog_store = lifelog_store

    def detect_boundaries(self, parsed_document: ParsedDocument) -> List[int]:
        text = getattr(parsed_document.content, "text", None) or ""
        evs = _parse_lifelog_events(text)
        if len(evs) <= 1:
            return []
        return list(range(1, len(evs)))

    async def _extract_entities_one(
        self, semaphore: asyncio.Semaphore, ev: LifelogEvent, idx: int
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """Extract entities for one event; returns (idx, entities)."""
        async with semaphore:
            instruction = LIFELOG_ENTITY_EXTRACTION.format(
                when=ev.when,
                who=ev.who,
                what=ev.what,
                where=ev.where,
                why_how=ev.why_how,
                description=ev.description,
            )
            try:
                out = await self.llm.astructure_output(
                    instruction=instruction,
                    user_system_prompt=LIFELOG_ENTITY_SYSTEM,
                    datamodel=_LifelogEntitiesOut,
                    key_attr="name",
                    value_attr="description",
                )
            except Exception:
                out = _LifelogEntitiesOut(entities=[])
            entities: List[Dict[str, Any]] = []
            for e in out.entities or []:
                c = (e.canonical_text or "").strip()
                if not c:
                    continue
                entities.append({
                    "canonical": c,
                    "original": (e.original_text or c).strip(),
                    "type": (e.type or "other").strip(),
                })
            return (idx, entities)

    def chunk(
        self,
        parsed_document: ParsedDocument,
        chunk_boundaries: List[int],
        doc_title: Optional[str] = None,
    ) -> Tuple[List[Chunk], ParsedDocument]:
        text = getattr(parsed_document.content, "text", None) or ""
        events = _parse_lifelog_events(text)
        doc_title = doc_title or getattr(parsed_document, "title", None) or ""
        chunks: List[Chunk] = []

        # Parallel entity extraction (gather inside _run_async to avoid event loop binding issues)
        max_concurrency = max(1, getattr(Config, "CHUNKER_LLM_MAX_CONCURRENCY", 5))
        semaphore = asyncio.Semaphore(max_concurrency)
        tasks = [self._extract_entities_one(semaphore, ev, i) for i, ev in enumerate(events)]

        async def _gather_all() -> List[Tuple[int, List[Dict[str, Any]]]]:
            return await asyncio.gather(*tasks)

        results_list: List[Tuple[int, List[Dict[str, Any]]]] = self.llm._run_async(_gather_all())
        entities_by_idx = {idx: ents for idx, ents in results_list}

        for i, ev in enumerate(events):
            entities = entities_by_idx.get(i, [])

            day = _ev_to_day(ev)
            event_uuid = str(uuid.uuid4())

            if self.lifelog_store:
                try:
                    self.lifelog_store.save_event(
                        day=day,
                        event_uuid=event_uuid,
                        event_data={
                            "when": ev.when,
                            "who": ev.who,
                            "what": ev.what,
                            "where": ev.where,
                            "why_how": ev.why_how,
                            "description": ev.description,
                        },
                        entities=entities,
                    )
                except Exception:
                    pass

            desc = ev.description or f"{ev.when} {ev.who} {ev.what} {ev.where} {ev.why_how}"
            meta = ChunkMetadata(
                chunk_size=len(desc),
                start_index=i,
                end_index=i,
                extra={
                    "lifelog": {
                        "when": ev.when,
                        "who": ev.who,
                        "what": ev.what,
                        "where": ev.where,
                        "why_how": ev.why_how,
                        "description": ev.description,
                        "entities": [
                            {"text": x["original"], "canonical": x["canonical"], "type": x["type"]}
                            for x in entities
                        ],
                    },
                    "graph": {
                        "day": day,
                        "entity_ids": [x["canonical"] for x in entities],
                    },
                },
            )
            ch = Chunk(
                uuid=event_uuid,
                doc_title=doc_title,
                chunk=desc,
                chunk_order=i,
                metadata=meta,
            )
            chunks.append(ch)

        return chunks, parsed_document