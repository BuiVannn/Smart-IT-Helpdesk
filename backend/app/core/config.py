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

    # ── AI: nhà cung cấp chính ────────────────────────────────────────
    #
    # `openai` không có nghĩa là "phải dùng OpenAI" — nó có nghĩa là "dùng
    # HTTP API theo chuẩn OpenAI". Ollama Cloud, OpenRouter, Groq, Together,
    # Azure và Ollama chạy máy đều nói chuẩn này, chỉ khác `LLM_BASE_URL`.
    LLM_PROVIDER: Literal["fake", "openai"] = "fake"
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o-mini"

    # ── AI: nhà cung cấp DỰ PHÒNG ─────────────────────────────────────
    #
    # Bật bằng cách điền `LLM_FALLBACK_API_KEY`. Khi nhà cung cấp chính lỗi
    # mạng, quá tải (429) hoặc lỗi 5xx, lời gọi tự chuyển sang đây.
    #
    # ★ Vì sao cần: hạn mức miễn phí của Ollama Cloud tính theo thời gian
    # GPU và reset theo phiên 5 giờ, còn danh sách model `:free` của
    # OpenRouter thay đổi liên tục (20 xuống 15 trong chín ngày, tháng
    # 7/2026 gỡ hết tầng Llama và Qwen). Một nhà cung cấp duy nhất nghĩa là
    # có ngày demo không chạy.
    LLM_FALLBACK_BASE_URL: str = ""
    LLM_FALLBACK_API_KEY: str = ""
    LLM_FALLBACK_MODEL: str = ""

    # Cách ràng buộc đầu ra JSON. Không phải nhà cung cấp nào cũng nhận
    # `json_schema` (đặc sản của OpenAI); `json_object` phổ dụng hơn nhiều.
    # `none` dành cho model chỉ biết làm theo lời dặn trong prompt —
    # `TicketClassifier._validate()` vẫn kiểm chặt đầu ra nên vẫn an toàn.
    LLM_JSON_MODE: Literal["json_schema", "json_object", "none"] = "json_object"

    # ── AI: embedding ─────────────────────────────────────────────────
    #
    # ★ TÁCH RIÊNG KHỎI LLM VÌ MỘT LÝ DO CỤ THỂ: Ollama Cloud KHÔNG có
    # model embedding nào (lọc cloud+embedding trên ollama.com trả về rỗng).
    # Nên khi dùng Ollama Cloud cho chat, embedding phải trỏ sang chỗ khác —
    # OpenRouter có `/v1/embeddings`, hoặc Ollama chạy máy.
    #
    # Để trống ⇒ dùng lại cấu hình LLM chính.
    EMBEDDING_BASE_URL: str = ""
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    # ★ PHẢI khớp số chiều thật của model. Cột `article_chunks.embedding` là
    # `vector(EMBEDDING_DIMENSIONS)`; đổi model sang loại 768 chiều mà quên
    # sửa đây thì mọi lệnh index sẽ lỗi ngay ở dòng đầu tiên.
    EMBEDDING_DIMENSIONS: int = 1536
    AI_MONTHLY_BUDGET_USD: float = 20.0
    AI_CONFIDENCE_THRESHOLD: float = Field(default=0.6, ge=0, le=1)
    RAG_SIMILARITY_THRESHOLD: float = Field(default=0.35, ge=0, le=1)
    RAG_TOP_K: int = 8
    RAG_MAX_CONTEXT_CHUNKS: int = 5
    LLM_TIMEOUT_CLASSIFY: int = 20
    LLM_TIMEOUT_CHAT: int = 30
    LLM_TIMEOUT_EMBED: int = 5

    # F3 — Gợi ý người xử lý (US-20). Trọng số nằm ở đây chứ không nằm trong
    # code: hiệu chỉnh phân bổ công việc là việc của vận hành, không phải của
    # một lần deploy. Tổng ba trọng số nên bằng 1 để điểm nằm trong [0, 1].
    SUGGEST_WEIGHT_SKILL: float = Field(default=0.5, ge=0, le=1)
    SUGGEST_WEIGHT_LOAD: float = Field(default=0.35, ge=0, le=1)
    SUGGEST_WEIGHT_DUTY: float = Field(default=0.15, ge=0, le=1)
    # Tải quy đổi (URGENT=4, HIGH=3, MEDIUM=2, LOW=1) bị coi là đầy ở mức này.
    SUGGEST_MAX_LOAD: int = Field(default=20, gt=0)
    SUGGEST_TOP_N: int = Field(default=3, gt=0, le=10)
    SUGGEST_DUTY_HOURS: int = Field(default=12, gt=0)

    # Ticket ở PENDING quá lâu nghĩa là việc phân loại đã rơi mất trên đường
    # ra hàng đợi — job đối soát sẽ nhặt lại (xem tickets/tasks.py).
    AI_CLASSIFY_STALE_MINUTES: int = Field(default=10, gt=0)

    # SLA — giờ hành chính
    #
    # ★ `BUSINESS_TIMEZONE` là múi giờ của HAI mốc trên. Dấu thời gian trong
    # database là UTC; thiếu tham số này thì 8:30–17:30 bị hiểu là giờ UTC,
    # tức 15:30–00:30 giờ Việt Nam, và mọi hạn SLA lệch 7 tiếng.
    BUSINESS_HOUR_START: float = 8.5
    BUSINESS_HOUR_END: float = 17.5
    BUSINESS_TIMEZONE: str = "Asia/Ho_Chi_Minh"

    # F6 — Thông báo (US-33 → US-36)
    # Cửa sổ chống lặp: cùng người nhận + cùng loại + cùng đối tượng trong
    # khoảng này thì chỉ sinh MỘT thông báo. Xem notifications/service.py để
    # biết vì sao là "chống lặp" chứ không phải "gộp".
    NOTIFY_DEDUP_MINUTES: int = Field(default=5, gt=0)
    # Job quét SLA xử lý tối đa bao nhiêu ticket mỗi lần chạy. Có trần để một
    # lần chạy không bao giờ vượt `task_time_limit`; phần dư chờ lượt sau,
    # muộn nhất 5 phút.
    SLA_MONITOR_BATCH_SIZE: int = Field(default=200, gt=0)

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
