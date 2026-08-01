"""Integration test cho IndexingService — trọng tâm là dấu thời gian chỉ mục.

Cần PostgreSQL có pgvector. Test tự bỏ qua nếu không kết nối được.
"""

import pytest
from sqlalchemy import select

from app.ai.embedding.fake_embedding import FakeEmbeddingClient
from app.db import all_models  # noqa: F401  — nạp đủ mapper cho khoá ngoại
from app.modules.knowledge.constants import ArticleStatus
from app.modules.knowledge.indexing import IndexingService
from app.modules.knowledge.models import ArticleChunk, KbArticle
from app.modules.users.constants import UserRole

pytestmark = pytest.mark.asyncio

CONTENT = (
    "## Bước 1\nMở ứng dụng Lịch công ty và chọn mục Phòng họp.\n\n"
    "## Bước 2\nChọn toà nhà, tầng và khung giờ, rồi bấm Đặt phòng.\n\n"
    "## Bước 3\nHệ thống gửi email xác nhận kèm mã mở cửa."
)


@pytest.fixture
def article(db, make_user):
    from datetime import UTC, datetime

    author = make_user(role=UserRole.ADMIN)
    row = KbArticle(
        slug=f"bai-test-{author.id.hex[:10]}",
        title="Đặt phòng họp qua hệ thống nội bộ",
        content_md=CONTENT,
        status=ArticleStatus.PUBLISHED,
        published_at=datetime.now(UTC),
        author_id=author.id,
    )
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def service(db) -> IndexingService:
    return IndexingService(db, FakeEmbeddingClient())


async def test_tao_chunk_va_dong_dau_thoi_gian(db, service, article):
    result = await service.index_article(article.id)

    assert result.was_indexed
    assert result.chunks_created > 0
    assert article.indexed_at is not None

    chunks = (
        db.execute(select(ArticleChunk).where(ArticleChunk.article_id == article.id))
        .scalars()
        .all()
    )
    assert len(chunks) == result.chunks_created


async def test_index_xong_thi_khong_con_bi_coi_la_cu(db, service, article):
    await service.index_article(article.id)
    db.refresh(article)

    assert article.indexed_at >= article.updated_at


async def test_DOC_bai_viet_KHONG_duoc_lam_chi_muc_thanh_cu(db, service, article):
    """★ LỖI ĐÃ XẢY RA THẬT VÀ TỐN TIỀN NẾU LỌT.

    `updated_at` có `onupdate=func.now()`, nên MỌI lệnh UPDATE lên hàng đều
    đẩy nó lên — kể cả lệnh chỉ tăng bộ đếm lượt xem. Hệ quả: cứ có người ĐỌC
    bài là bài đó bị coi là "nội dung mới hơn chỉ mục", dù không ai sửa chữ nào.

    Job `reconcile_stale_index` chạy mỗi giờ sẽ index lại mọi bài có người
    đọc — càng đông người dùng, hoá đơn embedding càng lớn, mà không sinh thêm
    giá trị nào.

    Phát hiện được là nhờ chạy thật với Celery worker rồi soi thẳng vào
    database: indexed_at 21:03:25, updated_at 21:03:42 — lệch đúng 17 giây,
    bằng khoảng thời gian vòng lặp kiểm tra gọi API đọc bài.
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import update

    from app.modules.knowledge.repository import KbArticleRepository

    await service.index_article(article.id)

    # Ép hai mốc về QUÁ KHỨ. Không có bước này thì không thử được: trong cùng
    # một transaction, `now()` của PostgreSQL luôn trả về thời điểm BẮT ĐẦU
    # transaction, nên mốc do onupdate ghi ra trùng khít mốc cũ và lỗi bị che.
    past = datetime.now(UTC) - timedelta(hours=1)
    db.execute(
        update(KbArticle).where(KbArticle.id == article.id).values(updated_at=past, indexed_at=past)
    )
    db.flush()
    db.refresh(article)
    assert article.updated_at == past

    KbArticleRepository(db).increment_view(article)
    db.flush()
    db.refresh(article)

    assert article.view_count == 1
    assert article.updated_at == past, (
        "đọc bài làm updated_at nhảy lên hiện tại ⇒ chỉ mục bị coi là cũ. "
        "Job đối soát sẽ index lại mọi bài có người đọc, mỗi giờ, và mỗi vòng "
        "là một hoá đơn embedding."
    )
    assert article.indexed_at >= article.updated_at


async def test_chi_con_lai_bai_can_index_sau_khi_da_index(db, service, article):
    """Hệ quả trực tiếp: chạy `only_stale` lần hai phải không còn bài này."""
    await service.index_article(article.id)
    db.flush()

    results = await service.reindex_all(only_stale=True)
    assert article.slug not in [
        r.slug for r in results
    ], "bài vừa index xong lại lọt vào danh sách cần index"


async def test_bai_khong_PUBLISHED_bi_xoa_khoi_chi_muc(db, service, article):
    """BR-11 — gỡ bài thì chatbot không được trích dẫn nữa."""
    await service.index_article(article.id)

    article.status = ArticleStatus.ARCHIVED
    db.flush()
    result = await service.index_article(article.id)

    assert not result.was_indexed
    assert result.chunks_removed > 0
    remaining = (
        db.execute(select(ArticleChunk).where(ArticleChunk.article_id == article.id))
        .scalars()
        .all()
    )
    assert remaining == []


async def test_index_lai_khong_nhan_doi_chunk(db, service, article):
    """Idempotent: chạy hai lần cho cùng số chunk, không cộng dồn."""
    first = await service.index_article(article.id)
    second = await service.index_article(article.id)

    assert first.chunks_created == second.chunks_created
    total = (
        db.execute(select(ArticleChunk).where(ArticleChunk.article_id == article.id))
        .scalars()
        .all()
    )
    assert len(total) == second.chunks_created
