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
#
# ★★ ĐIỀU KIỆN `c.embedding_model = :embedding_model` LÀ LƯỚI AN TOÀN, ĐỪNG BỎ.
#
# Vector của hai model khác nhau KHÔNG so sánh được — khoảng cách cosine giữa
# chúng là một con số vô nghĩa, không phải một con số kém chính xác. Không có
# điều kiện này thì ba tình huống rất đời thường đều cho ra câu trả lời tự tin
# dựa trên tài liệu ngẫu nhiên:
#
#   1. Đổi `EMBEDDING_MODEL` mà quên chạy lại `reindex_kb.py`
#   2. Nhà cung cấp embedding chính hỏng, hệ thống chuyển sang dự phòng
#   3. Chạy demo bằng `LLM_PROVIDER=fake` trên kho đã index bằng model thật
#
# Lọc theo model biến cả ba thành "không tìm thấy tài liệu" ⇒ chatbot từ chối
# trả lời. Thà nói không biết còn hơn bịa — đúng nguyên tắc của tầng RAG.
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
      AND c.embedding_model = :embedding_model
    ORDER BY c.embedding <=> CAST(:query_vector AS vector)
    LIMIT :top_k
""")

# Đếm chunk theo từng model — chỉ chạy khi truy vấn không ra gì, để thông báo
# lỗi nói được nguyên nhân thật thay vì "kho tài liệu rỗng".
DIAGNOSTIC_SQL = text("""
    SELECT c.embedding_model AS model, count(*) AS so_luong
    FROM article_chunks c
    JOIN kb_articles a ON a.id = c.article_id
    WHERE a.status = 'PUBLISHED'
    GROUP BY c.embedding_model
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
        # Lấy tên model SAU khi gọi embed: với chuỗi có dự phòng, tên chỉ đúng
        # khi đã biết chỗ nào thật sự phục vụ lần gọi này.
        model = self.embedding.model_name

        rows = (
            self.session.execute(
                RETRIEVAL_SQL,
                {
                    "query_vector": str(vector),
                    "top_k": self.top_k,
                    "embedding_model": model,
                },
            )
            .mappings()
            .all()
        )

        if not rows:
            self._canh_bao_khong_co_chunk(model)
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

    def _canh_bao_khong_co_chunk(self, model: str) -> None:
        """Nói rõ VÌ SAO không có chunk nào — rỗng thật hay lệch model.

        Hai nguyên nhân này cần hai hành động hoàn toàn khác nhau, mà triệu
        chứng lại giống hệt: chatbot trả lời "không tìm thấy tài liệu". Không
        phân biệt được thì người sửa sẽ đi chạy `seed_kb.py` trong khi vấn đề
        thật là quên `reindex_kb.py`.
        """
        theo_model = {
            row["model"]: row["so_luong"]
            for row in self.session.execute(DIAGNOSTIC_SQL).mappings().all()
        }

        if not theo_model:
            logger.warning(
                "kho tài liệu rỗng — chạy scripts/seed_kb.py rồi scripts/reindex_kb.py --all"
            )
            return

        logger.error(
            "LỆCH MODEL EMBEDDING: kho đã index bằng model khác nên không so sánh được. "
            "Chạy `python scripts/reindex_kb.py --all` để index lại bằng model hiện tại.",
            extra={
                "extra_fields": {
                    "model_dang_dung": model,
                    "model_trong_kho": theo_model,
                }
            },
        )
