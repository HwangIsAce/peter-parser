"""Load few-shot images for VLM router (heading / slide / lifelog)."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from peter_parser.common.config import Config

TYPES = ("heading", "slide", "lifelog")
SUFFIXES = (".png", ".jpg", ".jpeg")


def _project_root() -> Path:
    # From src/peter_parser/impl/router/ -> project root is 4 parents
    return Path(__file__).resolve().parent.parent.parent.parent


def get_router_fewshot_dir() -> Path:
    """Return path to router few-shot assets directory."""
    d = Config.ROUTER_FEWSHOT_DIR.strip()
    if d:
        return Path(d)
    return _project_root() / "assets" / "router_fewshot"


def get_router_fewshot_images() -> Dict[str, List[bytes]]:
    """Load few-shot images from assets/router_fewshot/{heading,slide,lifelog}/.

    Returns:
        Dict mapping document_type to list of image bytes (PNG/JPEG).
        Missing or empty dirs yield empty list for that type.
    """
    base = get_router_fewshot_dir()
    out: Dict[str, List[bytes]] = {t: [] for t in TYPES}
    for t in TYPES:
        folder = base / t
        if not folder.is_dir():
            continue
        for path in sorted(folder.iterdir()):
            if path.suffix.lower() in SUFFIXES:
                try:
                    out[t].append(path.read_bytes())
                except Exception:
                    continue
    return out
