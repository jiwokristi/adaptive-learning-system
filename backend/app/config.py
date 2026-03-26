from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/adaptive_learning"
    ANTHROPIC_API_KEY: str = ""
    UPLOAD_DIR: str = "./uploads"
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"
    CLAUDE_DISTILL_MODEL: str = "claude-sonnet-4-20250514"
    MAX_FILE_SIZE_MB: int = 50
    CHUNK_SIZE_TOKENS: int = 1500
    CHUNK_OVERLAP_TOKENS: int = 200

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
