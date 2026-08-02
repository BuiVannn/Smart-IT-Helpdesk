"""Lưới an toàn: không so sánh vector của hai model khác nhau.

★ VÌ SAO ĐÂY LÀ TÍNH CHẤT SỐNG CÒN. Khoảng cách cosine giữa vector của model
A và vector của model B không phải là "kém chính xác" — nó là số ngẫu nhiên.
Nhưng hệ thống không có cách nào tự biết điều đó: nó vẫn nhận được điểm số,
vẫn vượt ngưỡng, vẫn trả lời tự tin kèm trích dẫn. Đây là kiểu hỏng tệ nhất
vì nó im lặng và trông giống như đang hoạt động.

Ba tình huống rất đời thường dẫn tới lệch model:
  1. Đổi `EMBEDDING_MODEL` mà quên chạy lại `reindex_kb.py`
  2. Nhà cung cấp chính hỏng ⇒ hệ thống tự chuyển sang dự phòng
  3. Chạy demo `LLM_PROVIDER=fake` trên kho đã index bằng model thật
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, text

from app.ai.retriever import Retriever
from app.modules.knowledge.constants import ArticleStatus
from app.modules.knowledge.models import ArticleChunk, KbArticle


class EmbeddingGia:
    """Trả vector cố định, khai báo tên model tuỳ ý."""

    def __init__(self, ten_model: str, gia_tri: float = 0.5) -> None:
        self._ten = ten_model
        self._gia_tri = gia_tri

    @property
    def model_name(self) -> str:
        return self._ten

    @property
    def dimensions(self) -> int:
        return 1536

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[self._gia_tri] * 1536 for _ in texts]


@pytest.fixture
def bai_viet_da_index(db, make_user):
    """Một bài PUBLISHED với chunk index bằng `model-A`."""
    article = KbArticle(
        slug=f"bai-kiem-thu-{uuid4().hex[:8]}",
        title="Bài kiểm thử lệch model embedding",
        content_md="Nội dung hướng dẫn đủ dài để làm một đoạn tài liệu hợp lệ.",
        summary="Tóm tắt ngắn",
        status=ArticleStatus.PUBLISHED,
        # Ràng buộc `ck_kb_articles_published` bắt PUBLISHED phải có mốc đăng —
        # database không cho dựng dữ liệu trái quy tắc, kể cả trong test.
        published_at=datetime.now(UTC),
        author_id=make_user().id,
    )
    db.add(article)
    db.flush()

    db.add(
        ArticleChunk(
            article_id=article.id,
            chunk_index=0,
            content="Đoạn tài liệu dùng để kiểm chứng việc lọc theo model embedding.",
            token_count=20,
            embedding=[0.5] * 1536,
            embedding_model="model-A",
        )
    )
    db.flush()

    yield article

    db.execute(delete(ArticleChunk).where(ArticleChunk.article_id == article.id))
    db.execute(delete(KbArticle).where(KbArticle.id == article.id))
    db.flush()


class TestLocTheoModel:
    async def test_cung_model_thi_lay_duoc(self, db, bai_viet_da_index):
        retriever = Retriever(db, EmbeddingGia("model-A"), threshold=0.1)

        ket_qua = await retriever.retrieve("câu hỏi bất kỳ")

        assert ket_qua.has_context
        assert any(c.slug == bai_viet_da_index.slug for c in ket_qua.chunks)

    async def test_LECH_model_thi_KHONG_lay_gi_ca(self, db, bai_viet_da_index):
        """★ Vector giống hệt nhau (cùng [0.5]*1536) nên nếu không lọc theo
        model, điểm tương đồng sẽ là 1.0 và chunk chắc chắn lọt. Test này chỉ
        đỏ khi và chỉ khi bộ lọc bị gỡ."""
        retriever = Retriever(db, EmbeddingGia("model-B"), threshold=0.1)

        ket_qua = await retriever.retrieve("câu hỏi bất kỳ")

        assert not ket_qua.has_context, "vector của model khác KHÔNG được đem ra so sánh"
        assert ket_qua.chunks == []

    async def test_lech_model_dan_toi_TU_CHOI_chu_khong_bia(self, db, bai_viet_da_index):
        """`has_context = False` là tín hiệu để `ChatService` trả câu từ chối
        mà KHÔNG gọi LLM. Nói không biết còn hơn trả lời dựa trên tài liệu
        được chọn ngẫu nhiên."""
        retriever = Retriever(db, EmbeddingGia("model-B"), threshold=0.1)

        ket_qua = await retriever.retrieve("câu hỏi bất kỳ")

        assert ket_qua.has_context is False
        assert ket_qua.top_score == 0.0


class TestChanDoanNguyenNhan:
    async def test_bao_ro_LECH_MODEL_chu_khong_bao_kho_rong(self, db, bai_viet_da_index, caplog):
        """Hai nguyên nhân cần hai hành động khác hẳn nhau — kho rỗng thì chạy
        `seed_kb.py`, lệch model thì chạy `reindex_kb.py` — mà triệu chứng lại
        giống hệt. Thông báo phải chỉ đúng việc cần làm."""
        retriever = Retriever(db, EmbeddingGia("model-B"), threshold=0.1)

        await retriever.retrieve("câu hỏi bất kỳ")

        thong_bao = " ".join(b.message for b in caplog.records)
        assert "LỆCH MODEL" in thong_bao
        assert "reindex_kb.py" in thong_bao

    async def test_kho_rong_that_thi_bao_dung_nhu_vay(self, db, caplog):
        db.execute(text("DELETE FROM article_chunks"))
        db.flush()
        retriever = Retriever(db, EmbeddingGia("model-A"), threshold=0.1)

        await retriever.retrieve("câu hỏi bất kỳ")

        thong_bao = " ".join(b.message for b in caplog.records)
        assert "rỗng" in thong_bao
        assert "seed_kb.py" in thong_bao


class TestKhoThatVanHoatDong:
    async def test_kho_hien_tai_dung_dung_model_dang_cau_hinh(self, db):
        """Bảo vệ khỏi tình huống ai đó đổi `FakeEmbeddingClient.model_name`
        mà quên index lại — kho dev sẽ ngừng khớp và mọi test chat sẽ skip
        hàng loạt mà không rõ lý do."""
        from app.ai.embedding.openai_embedding import build_embedding_client

        dang_dung = build_embedding_client().model_name
        trong_kho = {
            r[0] for r in db.execute(select(ArticleChunk.embedding_model).distinct().limit(5)).all()
        }

        if not trong_kho:
            pytest.skip("kho chưa index — chạy scripts/reindex_kb.py --all")
        assert dang_dung in trong_kho, (
            f"model đang dùng {dang_dung!r} không khớp kho {trong_kho} — "
            "chạy `python scripts/reindex_kb.py --all`"
        )
