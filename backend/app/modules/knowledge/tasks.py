"""Celery task cho module kho tri thức.

Task chỉ là VỎ MỎNG gọi service — toàn bộ logic nằm ở indexing.py. Nhờ vậy
cùng một logic chạy được cả trong API, trong worker lẫn trong script CLI,
và test được mà không cần Celery.
"""

import asyncio
from uuid import UUID

from app.ai.embedding.openai_embedding import build_embedding_client
from app.celery_app import celery_app
from app.core.logging import get_logger

# Nạp TOÀN BỘ model để SQLAlchemy phân giải được mọi quan hệ khoá ngoại.
# Thiếu dòng này, script chỉ import một vài model sẽ lỗi
# "could not find table 'users'" khi model đó có FK tới bảng khác.
from app.db import all_models  # noqa: F401
from app.db.session import session_scope
from app.modules.knowledge.indexing import IndexingService

logger = get_logger(__name__)


@celery_app.task(
    bind=True,
    name="app.modules.knowledge.tasks.index_article",
    max_retries=3,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_jitter=True,
)
def index_article(self, article_id: str) -> dict:
    """Index một bài viết. Được gọi khi Admin publish hoặc sửa bài."""
    with session_scope() as db:
        service = IndexingService(db, build_embedding_client())
        result = asyncio.run(service.index_article(UUID(article_id)))

    return {
        "article_id": str(result.article_id),
        "slug": result.slug,
        "chunks_created": result.chunks_created,
        "skipped_reason": result.skipped_reason,
    }


@celery_app.task(name="app.modules.knowledge.tasks.reconcile_stale_index")
def reconcile_stale_index() -> dict:
    """Job đối soát định kỳ (mỗi giờ) — bắt các bài chưa được index.

    Đây là lưới an toàn cho việc KHÔNG dùng transactional outbox (ADR-0007):
    nếu tác vụ index bị mất giữa lúc commit và lúc đẩy vào hàng đợi, job này
    sẽ phát hiện và xử lý trong vòng một giờ.
    """
    with session_scope() as db:
        service = IndexingService(db, build_embedding_client())
        results = asyncio.run(service.reindex_all(only_stale=True))

    indexed = [r for r in results if r.was_indexed]
    if indexed:
        logger.warning(
            f"đối soát: phát hiện và index lại {len(indexed)} bài bị bỏ sót",
            extra={"extra_fields": {"slugs": [r.slug for r in indexed]}},
        )
    return {"checked": len(results), "reindexed": len(indexed)}
