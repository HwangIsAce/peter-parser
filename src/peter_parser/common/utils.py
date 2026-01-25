"""Text processing utilities: sentence splitting, segment mapping."""
import re
from typing import List

from peter_parser_core.common.types import Element


def split_sentences(text: str, language: str) -> List[str]:
    """Split text into sentences"""
    if not text or not text.strip():
        return []
    text = text.strip()
    segs = re.split(r'[.!?。！？]\s*|\n+', text)
    return [s.strip() for s in segs if s.strip()]


def segment_to_element_boundaries(
    section_elements: List[Element],
    segments: List[str],
    segment_boundaries: List[int],
    language: str,
) -> List[int]:
    """Convert segment boundaries to element boundaries"""
    if not segment_boundaries:
        return []
    
    segment_to_element: List[int] = []
    for el_idx, el in enumerate(section_elements):
        el_segments = split_sentences(el.text or "", language)
        for _ in el_segments:
            segment_to_element.append(el_idx)
    
    out: List[int] = []
    for sb in segment_boundaries:
        if 0 <= sb < len(segment_to_element):
            out.append(segment_to_element[sb])
    
    return sorted(list(set(out)))