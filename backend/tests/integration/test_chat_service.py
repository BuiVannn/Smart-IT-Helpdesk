"""Integration test cho ChatService — pipeline RAG đầy đủ (US-23, US-24).

Cần PostgreSQL có pgvector và dữ liệu đã seed:
    docker compose up -d postgres
    alembic upgrade head
    python scripts/seed.py && python scripts/seed_kb.py
    python scripts/reindex_kb.py --all

Test tự bỏ qua nếu không kết nối được database, để CI không đỏ khi
fixture DB chưa sẵn sàng (task T10).
"""

from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.ai.embedding.fake_embedding import FakeEmbeddingClient
from app.ai.llm.fake_client import FakeLlmClient
from app.ai.retriever import Retriever
from app.core.exceptions import NotFoundError
from app.db import all_models  # noqa: F401  — nạp đủ mapper cho khoá ngoại
from app.db.session import SessionLocal
from app.modules.chatbot.models import ChatCitation, ChatMessage, ChatSession
from app.modules.chatbot.service import ChatService
from app.modules.knowledge.models import ArticleChunk
from app.modules.users.models import User

pytestmark = pytest.mark.asyncio


@pytest.fixture
def db():
    """Session dùng transaction và rollback ở cuối — test không để lại dữ liệu."""
    try:
        session = SessionLocal()
        session.execute(select(1))
    except Exception:
        pytest.skip("Không kết nối được database")

    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def seeded(db):
    """Bỏ qua test nếu chưa có dữ liệu — test này kiểm tra pipeline, không seed hộ."""
    chunks = db.execute(select(func.count()).select_from(ArticleChunk)).scalar_one()
    if chunks == 0:
        pytest.skip("Chưa có chunk nào — chạy scripts/reindex_kb.py --all trước")
    user = db.execute(select(User).limit(1)).scalar_one_or_none()
    if user is None:
        pytest.skip("Chưa có user — chạy scripts/seed.py trước")
    return user


@pytest.fixture
def chat_session(db, seeded) -> ChatSession:
    session = ChatSession(user_id=seeded.id, title="Test")
    db.add(session)
    db.flush()
    return session


@pytest.fixture
def llm() -> FakeLlmClient:
    return FakeLlmClient(responses={"mật khẩu": "Bạn vào portal.company.com để đổi."})


def make_service(db, llm, *, threshold: float) -> ChatService:
    return ChatService(db, Retriever(db, FakeEmbeddingClient(), threshold=threshold), llm)


async def collect(service, session_id, user_id, question):
    return [e async for e in service.answer(
        session_id=session_id, user_id=user_id, question=question
    )]


class TestCoNguCanh:
    async def test_thu_tu_su_kien_dung(self, db, chat_session, seeded, llm):
        events = await collect(
            make_service(db, llm, threshold=0.1),
            chat_session.id, seeded.id, "Làm sao đổi mật khẩu email?",
        )
        types = [e.type for e in events]
        assert types[0] == "citations", "trích dẫn phải gửi TRƯỚC nội dung"
        assert "token" in types
        assert types[-1] == "done"

    async def test_trich_dan_gui_truoc_noi_dung(self, db, chat_session, seeded, llm):
        """Người dùng thấy ngay nguồn tham chiếu trong khi câu trả lời đang sinh."""
        events = await collect(
            make_service(db, llm, threshold=0.1), chat_session.id, seeded.id, "wifi",
        )
        citations = events[0].data["citations"]
        assert citations
        for c in citations:
            assert {"articleId", "title", "slug", "score", "rank"} <= c.keys()

    async def test_luu_tin_nhan_va_trich_dan(self, db, chat_session, seeded, llm):
        await collect(
            make_service(db, llm, threshold=0.1), chat_session.id, seeded.id, "wifi",
        )
        db.flush()
        messages = db.execute(
            select(ChatMessage).where(ChatMessage.session_id == chat_session.id)
        ).scalars().all()
        assert len(messages) == 2  # câu hỏi + câu trả lời
        assert db.execute(select(func.count()).select_from(ChatCitation)).scalar_one() > 0


class TestKhongCoNguCanh:
    async def test_tu_choi_va_KHONG_goi_llm_sinh_cau_tra_loi(
        self, db, chat_session, seeded, llm
    ):
        """★ TEST QUAN TRỌNG NHẤT CỦA CẢ MODULE.

        Không có tài liệu liên quan ⇒ TUYỆT ĐỐI không gọi stream(). Model
        không được gọi thì không thể bịa ra các bước thao tác IT sai.
        Đây là lớp phòng vệ mạnh hơn mọi mẹo viết prompt.
        """
        before = llm.stream_count
        events = await collect(
            make_service(db, llm, threshold=0.99),   # ngưỡng cao ⇒ không chunk nào đạt
            chat_session.id, seeded.id, "Lương tháng này khi nào có?",
        )
        assert llm.stream_count == before, "ĐÃ GỌI stream() dù không có tài liệu!"
        assert events[-1].data["noContextFound"] is True
        assert events[-1].data["canCreateTicket"] is True

    async def test_cau_tra_loi_tu_choi_goi_y_tao_ticket(self, db, chat_session, seeded, llm):
        events = await collect(
            make_service(db, llm, threshold=0.99), chat_session.id, seeded.id, "câu hỏi lạ",
        )
        answer = next(e for e in events if e.type == "token").data["delta"]
        assert "chưa tìm thấy" in answer.lower()
        assert "yêu cầu hỗ trợ" in answer.lower()

    async def test_danh_dau_no_context_de_phan_tich_khoang_trong(
        self, db, chat_session, seeded, llm
    ):
        """Dữ liệu cho US-27 — tìm chủ đề còn thiếu trong kho tài liệu."""
        await collect(
            make_service(db, llm, threshold=0.99), chat_session.id, seeded.id, "câu hỏi lạ",
        )
        db.flush()
        messages = db.execute(
            select(ChatMessage).where(
                ChatMessage.session_id == chat_session.id,
                ChatMessage.no_context_found.is_(True),
            )
        ).scalars().all()
        assert len(messages) == 1


class TestXuLyLoi:
    async def test_llm_hong_tra_ve_loi_than_thien(self, db, chat_session, seeded):
        """Người dùng cần biết 'thử lại sau', không cần biết 'connection reset'."""
        events = await collect(
            make_service(db, FakeLlmClient(should_fail=True), threshold=0.1),
            chat_session.id, seeded.id, "wifi",
        )
        assert events[-1].type == "error"
        assert events[-1].data["canCreateTicket"] is True
        assert "Trợ lý ảo" in events[-1].data["message"]

    async def test_cau_hoi_rong_bi_tu_choi(self, db, chat_session, seeded, llm):
        events = await collect(
            make_service(db, llm, threshold=0.1), chat_session.id, seeded.id, "   ",
        )
        assert events[0].type == "error"
        assert events[0].data["code"] == "VALIDATION_ERROR"

    async def test_khong_truy_cap_duoc_phien_cua_nguoi_khac(
        self, db, chat_session, seeded, llm
    ):
        """Trả NotFound (404) thay vì Forbidden (403) — không tiết lộ sự tồn tại."""
        with pytest.raises(NotFoundError):
            await collect(
                make_service(db, llm, threshold=0.1), chat_session.id, uuid4(), "wifi",
            )


class TestRetriever:
    async def test_nguong_loc_dung(self, db, seeded):
        retriever_low = Retriever(db, FakeEmbeddingClient(), threshold=0.0)
        retriever_high = Retriever(db, FakeEmbeddingClient(), threshold=0.99)

        low = await retriever_low.retrieve("đổi mật khẩu")
        high = await retriever_high.retrieve("đổi mật khẩu")

        assert low.has_context is True
        assert high.has_context is False
        assert high.total_candidates > 0, "vẫn có ứng viên, chỉ là không đạt ngưỡng"

    async def test_gioi_han_so_chunk_dua_vao_prompt(self, db, seeded):
        retriever = Retriever(
            db, FakeEmbeddingClient(), threshold=0.0, top_k=8, max_context_chunks=3
        )
        result = await retriever.retrieve("mạng wifi")
        assert len(result.chunks) <= 3

    async def test_cau_hoi_rong_tra_ve_rong(self, db, seeded):
        result = await Retriever(db, FakeEmbeddingClient()).retrieve("   ")
        assert result.has_context is False
