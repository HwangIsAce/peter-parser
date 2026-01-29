"""Router output schema definitions."""

from typing import Literal

from pydantic import BaseModel, Field


DocumentTypeLiteral = Literal["heading", "plain", "slide", "lifelog"]


class RouterSchema(BaseModel):
    """Structured output for document-type routing. Used by LLMRouter."""

    document_type: DocumentTypeLiteral = Field(
        ...,
        description="One of: heading (structured with headings), plain (unstructured text), slide (presentation), lifelog (5W1H lifelog entries).",
    )
