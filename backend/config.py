from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o"
    LLM_TIMEOUT_SECONDS: int = 30
    LLM_MAX_RETRIES: int = 2

    POLICY_FILE_PATH: str = "data/policy_terms.json"

    # Explicit extra origin (e.g. your Vercel deployment URL)
    FRONTEND_URL: Optional[str] = None

    LOG_LEVEL: str = "INFO"

    @property
    def CORS_ORIGINS(self) -> List[str]:
        origins = ["http://localhost:3000"]
        if self.FRONTEND_URL:
            origins.append(self.FRONTEND_URL)
        return origins


settings = Settings()
