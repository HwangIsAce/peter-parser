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
    
    @classmethod
    def validate(cls) -> None:
        """Validate required configuration."""
        if not cls.UPSTAGE_API_KEY:
            raise ValueError("UPSTAGE_API_KEY is required")