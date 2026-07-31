"""Health check.

TÁCH RIÊNG live và ready là bắt buộc: nếu /health/live phụ thuộc database,
một sự cố DB ngắn sẽ khiến orchestrator khởi động lại TOÀN BỘ instance
cùng lúc — biến sự cố suy giảm thành sự cố sập hoàn toàn.
"""

from fastapi import APIRouter, Response
from sqlalchemy import text

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import engine

router = APIRouter(tags=["health"])
logger = get_logger(__name__)


@router.get("/health/live")
def liveness() -> dict:
    """Tiến trình còn sống. KHÔNG kiểm tra phụ thuộc."""
    return {"status": "alive", "app": settings.APP_NAME, "environment": settings.ENVIRONMENT}


@router.get("/health/ready")
def readiness(response: Response) -> dict:
    """Sẵn sàng nhận traffic — có kiểm tra phụ thuộc."""
    checks: dict[str, str] = {}
    healthy = True

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {type(exc).__name__}"
        healthy = False

    try:
        import redis
        redis.from_url(settings.REDIS_URL, socket_connect_timeout=2).ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {type(exc).__name__}"
        healthy = False

    if not healthy:
        response.status_code = 503
    return {"status": "ready" if healthy else "not_ready", "checks": checks}
