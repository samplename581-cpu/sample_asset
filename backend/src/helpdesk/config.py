from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: str = "development"
    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    API_PREFIX: str = "/api/v1"
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    LLM_PROVIDER: str = "mock"
    LLM_MODEL_ID: str = "mock-helpdesk-v1"
    LLM_TIMEOUT_SECONDS: int = Field(default=30, ge=1, le=120)
    LLM_MAX_OUTPUT_TOKENS: int = 500
    LLM_TEMPERATURE: float = Field(default=0.1, ge=0.0, le=2.0)

    WATSONX_URL: str | None = "https://jp-tok.ml.cloud.ibm.com"
    WATSONX_PROJECT_ID: str | None = None
    WATSONX_API_KEY: str | None = None
    WATSONX_MODEL_ID: str | None = None

    OPENAI_COMPATIBLE_BASE_URL: str | None = "http://127.0.0.1:11434/v1"
    OPENAI_COMPATIBLE_API_KEY: str | None = None
    OPENAI_COMPATIBLE_MODEL_ID: str | None = None

    EMBEDDING_PROVIDER: str = "mock"
    EMBEDDING_MODEL_ID: str = "mock-embedding-v1"
    EMBEDDING_DIMENSION: int = 64
    WATSONX_EMBEDDING_MODEL_ID: str | None = None

    VECTOR_STORE_PROVIDER: str = "chroma"
    VECTOR_TOP_K: int = Field(default=5, ge=1, le=20)
    VECTOR_MIN_SCORE: float = 0.45

    CHROMA_COLLECTION: str = "helpdesk_knowledge"

    SEED_DATA_DIR: str = "./data/seed"
    # 画面とAPIで使用する初期Ticket
    TICKET_SEED_FILE: str = "tickets_app.json"
    RUNTIME_DATA_DIR: str = "./data/runtime"
    INDEX_DIR: str = "./data/index"

    SHEET_TEMPLATE_PATH: str = "assets/source/business_tools/inquiry_management.xlsx"
    SHEET_OUTPUT_PATH: str = "data/runtime/inquiry_management.xlsx"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_ticket_seed_file(self) -> Settings:
        """TICKET_SEED_FILE は SEED_DATA_DIR 直下のファイル名だけを許可する。"""
        if Path(self.TICKET_SEED_FILE).name != self.TICKET_SEED_FILE:
            raise ValueError("TICKET_SEED_FILE must be a file name without directories")
        return self

    @model_validator(mode="after")
    def validate_cors_wildcard(self) -> Settings:
        """Reject CORS_ORIGINS=* in non-development environments (design rule 5.2)."""
        if "*" in self.cors_origin_list and self.APP_ENV not in ("development", "test"):
            raise ValueError(
                "CORS_ORIGINS=* is not allowed in non-development environments. "
                "Set explicit origins or APP_ENV=development."
            )
        return self

    @model_validator(mode="after")
    def validate_watsonx_credentials(self) -> Settings:
        if self.LLM_PROVIDER == "watsonx" or self.EMBEDDING_PROVIDER == "watsonx":
            missing: list[str] = []
            if not self.WATSONX_URL:
                missing.append("WATSONX_URL")
            if not self.WATSONX_PROJECT_ID:
                missing.append("WATSONX_PROJECT_ID")
            if not self.WATSONX_API_KEY:
                missing.append("WATSONX_API_KEY")
            if not self.WATSONX_MODEL_ID:
                if self.LLM_PROVIDER == "watsonx":
                    missing.append("WATSONX_MODEL_ID")
            if self.EMBEDDING_PROVIDER == "watsonx" and not self.WATSONX_EMBEDDING_MODEL_ID:
                missing.append("WATSONX_EMBEDDING_MODEL_ID")
            if missing:
                raise ValueError("watsonx provider settings are incomplete: " + ", ".join(missing))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
