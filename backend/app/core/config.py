from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    APP_NAME: str = "AIDA - AI Document Assistant"
    APP_VERSION: str = "0.1.0"
    OPENROUTER_API_KEY: str
    PINECONE_API_KEY: str
    PINECONE_INDEX_NAME: str
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost"]

    # Langfuse observability — all three must be set to enable tracing.
    # Leave unset (or empty) to disable Langfuse silently; the app runs normally.
    # Get keys from https://cloud.langfuse.com or your self-hosted instance.
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"


settings = Settings()
