"""Truy xuất đoạn tài liệu liên quan cho RAG (F4).

★ ĐIỂM QUAN TRỌNG NHẤT: nếu điểm tương đồng cao nhất dưới ngưỡng, trả về
`has_context = False`. Tầng gọi PHẢI trả câu từ chối mà KHÔNG gọi LLM.

Đây là lớp phòng vệ mạnh nhất chống việc chatbot bịa đặt — mạnh hơn mọi mẹo
viết prompt, vì model không hề được gọi thì không thể bịa.
"""

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai.embedding.base import EmbeddingClient
from app.core.config import settings
from app.core.logging import get_logger
from app.modules.chatbot.prompts import RetrievedChunk

logger = get_logger(__name__)

# Chỉ truy xuất bài đã PUBLISHED — bài DRAFT không bao giờ lọt vào ngữ cảnh (BR-11).
RETRIEVAL_SQL = text("""
    SELECT
        c.id            AS chunk_id,
        c.content       AS content,
        a.id            AS article_id,
        a.title         AS title,
        a.slug          AS slug,
        1 - (c.embedding <=> CAST(:query_vector AS vector)) AS score
    FROM article_chunks c
    JOIN kb_articles a ON a.id = c.article_id
    WHERE a.status = 'PUBLISHED'
    ORDER BY c.embedding <=> CAST(:query_vector AS vector)
    LIMIT :top_k
""")


@dataclass
class RetrievalResult:
    chunks: list[RetrievedChunk]
    top_score: float
    total_candidates: int

    @property
    def has_context(self) -> bool:
        """False ⇒ KHÔNG gọi LLM, trả NO_CONTEXT_ANSWER."""
        return bool(self.chunks)


class Retriever:
    def __init__(
        self,
        session: Session,
        embedding_client: EmbeddingClient,
        *,
        threshold: float | None = None,
        top_k: int | None = None,
        max_context_chunks: int | None = None,
    ) -> None:
        self.session = session
        self.embedding = embedding_client
        # Ngưỡng CẦN HIỆU CHỈNH bằng tập đánh giá ở tests/fixtures/rag_eval.jsonl,
        # không phải con số thần thánh. Xem docs/design/07 §3.2.
        self.threshold = threshold if threshold is not None else settings.RAG_SIMILARITY_THRESHOLD
        self.top_k = top_k or settings.RAG_TOP_K
        self.max_context_chunks = max_context_chunks or settings.RAG_MAX_CONTEXT_CHUNKS

    async def retrieve(self, query: str) -> RetrievalResult:
        """Tìm các đoạn tài liệu liên quan nhất tới câu hỏi.

        Lấy dư (top_k = 8) rồi lọc theo ngưỡng và cắt còn tối đa 5 — tốt hơn
        lấy thiếu, vì chi phí lấy thêm gần bằng không còn lấy thiếu thì mất
        thông tin không lấy lại được.
        """
        query = query.strip()
        if not query:
            return RetrievalResult(chunks=[], top_score=0.0, total_candidates=0)

        vector = (await self.embedding.embed([query]))[0]

        rows = (
            self.session.execute(
                RETRIEVAL_SQL,
                {"query_vector": str(vector), "top_k": self.top_k},
            )
            .mappings()
            .all()
        )

        if not rows:
            logger.warning("kho tài liệu rỗng — chưa có chunk nào được index")
            return RetrievalResult(chunks=[], top_score=0.0, total_candidates=0)

        top_score = float(rows[0]["score"])

        # Lọc theo ngưỡng, giữ tối đa max_context_chunks
        kept = [r for r in rows if float(r["score"]) >= self.threshold][: self.max_context_chunks]

        chunks = [
            RetrievedChunk(
                rank=i + 1,
                title=row["title"],
                slug=row["slug"],
                content=row["content"],
                score=float(row["score"]),
                article_id=str(row["article_id"]),
            )
            for i, row in enumerate(kept)
        ]

        logger.info(
            "truy xuất tài liệu",
            extra={
                "extra_fields": {
                    "candidates": len(rows),
                    "kept": len(chunks),
                    "top_score": round(top_score, 4),
                    "threshold": self.threshold,
                    "has_context": bool(chunks),
                }
            },
        )

        return RetrievalResult(chunks=chunks, top_score=top_score, total_candidates=len(rows))

    def chunk_ids_of(self, result: RetrievalResult) -> list[str]:
        """Tiện ích cho tầng gọi khi cần lưu trích dẫn."""
        return [c.article_id for c in result.chunks]
