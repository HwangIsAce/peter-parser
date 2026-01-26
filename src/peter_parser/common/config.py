"""Configuration management."""
import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent.parent.parent / ".env"
load_dotenv(env_path)

class Config:
    """Application configuration."""
    
    # Upstage API
    UPSTAGE_API_KEY: str = os.getenv("UPSTAGE_API_KEY", "")
    UPSTAGE_API_URL: str = os.getenv(
        "UPSTAGE_API_URL", 
        "https://api.upstage.ai/v1/document-digitization"
    )
    
    UPSTAGE_DEFAULT_OCR: str = os.getenv("UPSTAGE_DEFAULT_OCR", "force")
    UPSTAGE_DEFAULT_BASE64_ENCODING: str = os.getenv(
        "UPSTAGE_DEFAULT_BASE64_ENCODING", 
        "['table']"
    )
    UPSTAGE_DEFAULT_MODEL: str = os.getenv(
        "UPSTAGE_DEFAULT_MODEL", 
        "document-parse"
    )
    
    # OpenAI API
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_VISION_MODEL: str = os.getenv("OPENAI_VISION_MODEL", "gpt-4o")  # Vision용
    
    # VLM-basedChunking Configuration
    DEFAULT_CHUNK_UNIT: str = os.getenv("DEFAULT_CHUNK_UNIT", "element")  # "page" or "element"
    CHUNK_MAX_CONTENT_LENGTH: int = int(os.getenv("CHUNK_MAX_CONTENT_LENGTH", "10000"))  # For document summary
    
    # Lumber-based Chunking Configuration
    LUMBER_LANGUAGE_DEFAULT: str = os.getenv("LUMBER_LANGUAGE_DEFAULT", "ko")
    
    # Lifelog Chunking Configuration
    JANUSGRAPH_HOST: str = os.getenv("JANUSGRAPH_HOST", "localhost")
    JANUSGRAPH_PORT: int = int(os.getenv("JANUSGRAPH_PORT", "8182"))
    
    # Schema Descriptions for LLM structured output
    SCHEMA_DESCRIPTIONS = {
        "document_summary": "Document summary",
        "page_title": "Page title",
        "page_script": "Presentation script",
        "chunk_boundaries": "List of indices where new chunks should start (0-based, excluding 0)",
        "chunk_summary": "Chunk summary",
        "chunk_keywords": "Key terms in chunk",
    }
    
    @classmethod
    def validate(cls) -> None:
        """Validate required configuration."""
        if not cls.UPSTAGE_API_KEY:
            raise ValueError("UPSTAGE_API_KEY is required")