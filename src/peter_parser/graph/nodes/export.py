"""Export node implementation: serialize chunks to JSON."""
from __future__ import annotations

import json
import sys
from typing import Any, Callable, Dict, List

from peter_parser.common.config import Config
from peter_parser_core.common.types import Chunk
from peter_parser.graph.states import PipelineState


def create_export_node() -> Callable[[PipelineState], Dict[str, Any]]:
    """Create an export node that serializes chunks to JSON."""

    def export_node(state: PipelineState) -> Dict[str, Any]:
        """Serialize state["chunks"] to JSON and return export_json."""
        if Config.PIPELINE_PROGRESS:
            print("[Pipeline] Step: export (serialize to JSON)...", file=sys.stderr, flush=True)
        chunks: List[Chunk] = state.get("chunks") or []
        payload: List[Dict[str, Any]] = []
        for c in chunks:
            d = c.model_dump() if hasattr(c, "model_dump") else c.dict()
            payload.append(d)
        export_json = json.dumps(payload, ensure_ascii=False, indent=2)
        return {"export_json": export_json}

    return export_node
