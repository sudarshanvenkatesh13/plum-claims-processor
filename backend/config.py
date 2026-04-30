from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o"
    LLM_TIMEOUT_SECONDS: int = 30
    LLM_MAX_RETRIES: int = 2

    POLICY_FILE_PATH: str = "data/policy_terms.json"

    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    LOG_LEVEL: str = "INFO"


settings = Settings()
