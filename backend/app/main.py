"""Điểm khởi động ứng dụng FastAPI."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.error_handlers import register_error_handlers
from app.core.logging import get_logger, setup_logging
from app.core.middleware import RequestContextMiddleware

# ★ BẮT BUỘC — nạp TOÀN BỘ model trước khi SQLAlchemy dựng mapper.
# Quan hệ khai báo bằng chuỗi (ví dụ ChatCitation.article -> "KbArticle") chỉ
# phân giải được khi lớp đích đã được nạp. Thiếu dòng này, ứng dụng khởi động
# bình thường rồi vỡ ở REQUEST ĐẦU TIÊN với lỗi "failed to locate a name".
# Test không bắt được vì conftest.py đã tự nạp all_models từ trước.
from app.db import all_models  # noqa: E402,F401  (đặt sau import trên là cố ý)

setup_logging(settings.LOG_LEVEL)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info(f"Khởi động {settings.APP_NAME} — môi trường {settings.ENVIRONMENT}")
    yield
    logger.info("Dừng ứng dụng")


app = FastAPI(
    title=settings.APP_NAME,
    description="Hệ thống hỗ trợ IT nội bộ thông minh, tích hợp AI",
    version="0.1.0",
    docs_url="/docs",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

register_error_handlers(app)

app.include_router(health_router)
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {"app": settings.APP_NAME, "docs": "/docs", "health": "/health/live"}
