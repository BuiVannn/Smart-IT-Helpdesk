"""Chỉ mục hoá bài viết cho chatbot RAG (US-29).

NGUYÊN TẮC IDEMPOTENT: index lại một bài luôn là *xoá hết chunk cũ → tạo mới*,
không cập nhật từng phần. Đơn giản, và không bao giờ để lại chunk mồ côi.

`article_chunks` là DỮ LIỆU DẪN XUẤT — luôn tái tạo được từ `kb_articles`
bằng `python scripts/reindex_kb.py --all`. Nó không bao giờ là nguồn sự thật.
"""

import time
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.ai.embedding.base import EmbeddingClient
from app.core.logging import get_logger
from app.modules.knowledge.chunker import TextChunker
from app.modules.knowledge.constants import ArticleStatus
from app.modules.knowledge.models import ArticleChunk, KbArticle

logger = get_logger(__name__)


@dataclass
class IndexResult:
    article_id: UUID
    slug: str
    chunks_created: int
    chunks_removed: int
    skipped_reason: str | None = None
    latency_ms: int = 0

    @property
    def was_indexed(self) -> bool:
        return self.skipped_reason is None


class IndexingService:
    def __init__(
        self,
        session: Session,
        embedding_client: EmbeddingClient,
        chunker: TextChunker | None = None,
    ) -> None:
        self.session = session
        self.embedding = embedding_client
        self.chunker = chunker or TextChunker()

    async def index_article(self, article_id: UUID) -> IndexResult:
        """Chia chunk và tạo embedding cho một bài viết.

        Bài KHÔNG ở trạng thái PUBLISHED sẽ bị xoá hết chunk (BR-11, BR-12) —
        không được để chatbot trích dẫn tài liệu đã gỡ.
        """
        started = time.perf_counter()

        article = self.session.get(KbArticle, article_id)
        if article is None:
            return IndexResult(article_id, "", 0, 0, skipped_reason="Bài viết không tồn tại")

        removed = self._delete_chunks(article_id)

        if not article.is_indexable:
            # Bài DRAFT hoặc ARCHIVED: xoá chunk và dừng lại
            article.indexed_at = None
            self.session.flush()
            logger.info(
                "gỡ chunk của bài không PUBLISHED",
                extra={"extra_fields": {"slug": article.slug, "removed": removed}},
            )
            return IndexResult(
                article_id,
                article.slug,
                0,
                removed,
                skipped_reason=f"Trạng thái {article.status}, không index",
            )

        chunks = self.chunker.chunk(title=article.title, content_md=article.content_md)
        if not chunks:
            return IndexResult(
                article_id, article.slug, 0, removed, skipped_reason="Không tách được chunk nào"
            )

        vectors = await self.embedding.embed([c.content for c in chunks])
        if len(vectors) != len(chunks):
            raise RuntimeError(f"Số vector ({len(vectors)}) không khớp số chunk ({len(chunks)})")

        self.session.add_all(
            [
                ArticleChunk(
                    article_id=article_id,
                    chunk_index=chunk.index,
                    content=chunk.content,
                    token_count=chunk.token_count,
                    embedding=vector,
                    embedding_model=self.embedding.model_name,
                )
                for chunk, vector in zip(chunks, vectors, strict=True)
            ]
        )

        # `updated_at` có onupdate=func.now(), nên lệnh UPDATE này cũng đẩy nó
        # lên. Ở đây vô hại: cả hai cột đều nhận `now()` của CÙNG một câu lệnh
        # nên bằng nhau, và điều kiện "cũ" là `indexed_at < updated_at`.
        #
        # ⚠️ Nhưng mọi lệnh UPDATE KHÁC lên hàng này thì KHÔNG vô hại — xem
        # `KbArticleRepository.increment_view`.
        article.indexed_at = func.now()
        self.session.flush()

        latency = round((time.perf_counter() - started) * 1000)
        logger.info(
            "index bài viết xong",
            extra={
                "extra_fields": {
                    "slug": article.slug,
                    "chunks": len(chunks),
                    "removed": removed,
                    "latency_ms": latency,
                }
            },
        )
        return IndexResult(article_id, article.slug, len(chunks), removed, latency_ms=latency)

    async def reindex_all(self, *, only_stale: bool = False) -> list[IndexResult]:
        """Dựng lại chỉ mục cho toàn bộ bài PUBLISHED.

        ★ ĐƯỜNG PHỤC HỒI BẮT BUỘC. Một đường phục hồi chưa từng được chạy thì
        không tồn tại — hãy chạy thử ít nhất một lần trước khi demo.
        """
        stmt = select(KbArticle).where(KbArticle.status == ArticleStatus.PUBLISHED)
        if only_stale:
            stmt = stmt.where(
                (KbArticle.indexed_at.is_(None)) | (KbArticle.indexed_at < KbArticle.updated_at)
            )

        articles = list(self.session.execute(stmt.order_by(KbArticle.slug)).scalars().all())
        logger.info(f"bắt đầu index {len(articles)} bài viết")

        results: list[IndexResult] = []
        for article in articles:
            try:
                results.append(await self.index_article(article.id))
            except Exception as exc:
                # Một bài lỗi không được làm hỏng cả lượt chạy
                logger.exception(f"lỗi khi index {article.slug}", exc_info=exc)
                results.append(
                    IndexResult(
                        article.id,
                        article.slug,
                        0,
                        0,
                        skipped_reason=f"Lỗi: {type(exc).__name__}: {exc}",
                    )
                )
        return results

    def _delete_chunks(self, article_id: UUID) -> int:
        result = self.session.execute(
            delete(ArticleChunk).where(ArticleChunk.article_id == article_id)
        )
        return result.rowcount or 0

    def count_chunks(self) -> int:
        return self.session.execute(select(func.count()).select_from(ArticleChunk)).scalar_one()
