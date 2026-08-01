"""Job định kỳ của module xác thực.

★ `celery_app.beat_schedule` trỏ tới `cleanup_expired_tokens` từ trước khi
file này tồn tại, nên beat đẩy một task không ai đăng ký và worker ném
`NotRegistered` mỗi ngày. File này khép lại cái vòng đó.
"""

from __future__ import annotations

from app.celery_app import celery_app
from app.core.logging import get_logger
from app.db import all_models  # noqa: F401
from app.db.session import session_scope
from app.modules.auth.repository import RefreshTokenRepository

logger = get_logger(__name__)


@celery_app.task(name="app.modules.auth.tasks.cleanup_expired_tokens")
def cleanup_expired_tokens() -> dict:
    """Xoá refresh token đã hết hạn (chạy 02:30 hằng ngày).

    Không xoá token còn hạn nhưng đã bị thu hồi: chúng là bằng chứng để phát
    hiện token bị đánh cắp (US-03 — dùng lại token đã thu hồi phải làm sập
    toàn bộ phiên của người đó). Xoá sớm là tự bịt mắt mình.
    """
    with session_scope() as db:
        deleted = RefreshTokenRepository(db).delete_expired()

    if deleted:
        logger.info(f"dọn {deleted} refresh token đã hết hạn")
    return {"deleted": deleted}
