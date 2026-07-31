"""Cấu hình ứng dụng — đọc toàn bộ từ biến môi trường.

Ứng dụng TỪ CHỐI KHỞI ĐỘNG nếu thiếu biến bắt buộc hoặc nếu JWT_SECRET
còn là giá trị mặc định ở môi trường production. Thà không chạy còn hơn
chạy với cấu hình không an toàn.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SECRET_MARKER = "CHANGE_ME"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # Môi trường
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    APP_NAME: str = "Smart IT Helpdesk"
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_ECHO: bool = False

    # Redis / Celery
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/2"

    # Bảo mật
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    BCRYPT_ROUNDS: int = 12
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15

    CORS_ORIGINS: str = "http://localhost:5173"

    # Object storage
    S3_ENDPOINT_URL: str = "http://minio:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET: str = "helpdesk-attachments"
    S3_REGION: str = "us-east-1"
    MAX_UPLOAD_SIZE_BYTES: int = 10 * 1024 * 1024
    MAX_ATTACHMENTS_PER_TICKET: int = 5

    # AI
    LLM_PROVIDER: Literal["fake", "openai"] = "fake"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o-mini"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 1536
    AI_MONTHLY_BUDGET_USD: float = 20.0
    AI_CONFIDENCE_THRESHOLD: float = Field(default=0.6, ge=0, le=1)
    RAG_SIMILARITY_THRESHOLD: float = Field(default=0.35, ge=0, le=1)
    RAG_TOP_K: int = 8
    RAG_MAX_CONTEXT_CHUNKS: int = 5
    LLM_TIMEOUT_CLASSIFY: int = 20
    LLM_TIMEOUT_CHAT: int = 30
    LLM_TIMEOUT_EMBED: int = 5

    # SLA — giờ hành chính
    BUSINESS_HOUR_START: float = 8.5
    BUSINESS_HOUR_END: float = 17.5

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @field_validator("JWT_SECRET")
    @classmethod
    def _validate_secret(cls, v: str, info) -> str:
        if len(v) < 32:
            raise ValueError("JWT_SECRET phải dài ít nhất 32 ký tự")
        env = info.data.get("ENVIRONMENT", "local")
        if env == "production" and DEFAULT_SECRET_MARKER in v:
            raise ValueError(
                "JWT_SECRET đang là giá trị mặc định. Sinh chuỗi thật: openssl rand -hex 32"
            )
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
