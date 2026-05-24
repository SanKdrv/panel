"""Application configuration loaded from environment variables."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Backend network ---
    backend_host: str = Field(default="0.0.0.0", alias="BACKEND_HOST")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    http_access_log: bool = Field(default=True, alias="HTTP_ACCESS_LOG")
    cors_origins_raw: str = Field(
        default="http://localhost:5173", alias="CORS_ORIGINS"
    )

    # --- Auth (admin panel local login) ---
    admin_username: str = Field(default="admin", alias="ADMIN_USERNAME")
    admin_password: str = Field(default="admin", alias="ADMIN_PASSWORD")
    session_secret: str = Field(
        default="dev-secret-change-me", alias="SESSION_SECRET"
    )
    session_ttl_hours: int = Field(default=12, alias="SESSION_TTL_HOURS")

    # --- RAG API client ---
    rag_backend_url: str = Field(default="http://rag-api:8000", alias="RAG_BACKEND_URL")
    rag_api_secret: str = Field(default="", alias="RAG_API_SECRET")
    rag_timeout_seconds: float = Field(default=30.0, alias="RAG_TIMEOUT_SECONDS")

    # --- Quality evaluation ---
    quality_gold_dataset_path: str = Field(
        default="app/data/gold_dataset.json",
        alias="QUALITY_GOLD_DATASET_PATH",
    )
    quality_embedding_url: str = Field(
        default="http://embedding-server:11434", alias="QUALITY_EMBEDDING_URL"
    )
    quality_embedding_model: str = Field(
        default="bge-m3", alias="QUALITY_EMBEDDING_MODEL"
    )
    quality_judge_url: str = Field(
        default="http://llm-server:11434", alias="QUALITY_JUDGE_URL"
    )
    quality_judge_model: str = Field(
        default="command-r7b-arabic", alias="QUALITY_JUDGE_MODEL"
    )

    # --- Grafana embed ---
    grafana_embed_url: str = Field(default="", alias="GRAFANA_EMBED_URL")
    grafana_dashboard_url: str = Field(default="", alias="GRAFANA_DASHBOARD_URL")

    @computed_field
    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_origins_raw.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
