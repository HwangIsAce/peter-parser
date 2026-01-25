# ------------------------------------------------------------
# VLM-based Chunking Prompts
# ------------------------------------------------------------

"""Prompts for chunk boundary detection."""

BOUNDARY_DETECTION_SYSTEM_PROMPT = """You are an expert in document analysis. Your task is to identify optimal chunk boundaries based on semantic coherence.

Return ONLY the indices where new chunks should start. Do NOT generate any text content."""

BOUNDARY_DETECTION_USER_PROMPT = """Analyze the following document and determine optimal chunk boundaries.

<DOCUMENT_SUMMARY>
{document_summary}
</DOCUMENT_SUMMARY>

<ITEM_METADATA>
{item_metadata}
</ITEM_METADATA>

<CHUNK_UNIT>
Chunking unit: {chunk_unit}
- "page": page numbers (0-based)
- "element": element indices (0-based)
</CHUNK_UNIT>

<TOTAL_ITEMS>
Total number of {chunk_unit}s: {total_items}
</TOTAL_ITEMS>

The first chunk always starts at index 0, so do not include 0 in the list.
Consider semantic coherence and topic changes when determining boundaries.
Return only the boundary indices as a list of integers."""

# -----------------------------------------------------------------------------
# LumberChunker
# -----------------------------------------------------------------------------

LUMBER_SYSTEM_PROMPT = """You are an expert in document structure. You receive a document section between two heading1 boundaries.

Task: Identify optimal chunk boundaries for hierarchical chunking within the section. Consider sub-topics, paragraph breaks, and semantic coherence.

Output: Return a list of segment indices (0-based) where new chunks start. Do not include 0."""

LUMBER_SECTION_PROMPT = """<SECTION_HEADING>
{section_heading}
</SECTION_HEADING>

<SECTION_CONTENT>
{document}
</SECTION_CONTENT>

This is a section between two heading1 boundaries. Analyze it and identify optimal chunk boundaries for hierarchical chunking. Return a list of segment indices where new chunks start. Do not include 0."""