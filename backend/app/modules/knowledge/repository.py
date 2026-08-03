"""Truy vấn kho tài liệu.

★ Tìm kiếm dùng `search_vector` do trigger ở migration 0004 sinh, cấu hình
`simple` + unaccent: người Việt gõ "mat khau" phải ra "mật khẩu". Dùng ILIKE
thay thế sẽ không xử lý được dấu và bỏ luôn xếp hạng theo độ liên quan.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, func, select, text
from sqlalchemy.orm import Session, selectinload

from app.core.pagination import PageParams
from app.modules.knowledge.constants import ArticleStatus
from app.modules.knowledge.models import ArticleChunk, KbArticle, KbCategory

SEARCH_CONDITION = text(
    "kb_articles.search_vector @@ plainto_tsquery('simple', immutable_unaccent(:q))"
)
# Xếp hạng theo độ liên quan; tiêu đề nặng hơn nội dung nhờ setweight ở trigger.
# Viết thẳng DESC vào chuỗi vì `text()` không có `.desc()` — nó là mẩu SQL thô,
# không phải cột.
SEARCH_RANK_DESC = text(
    "ts_rank(kb_articles.search_vector, " "plainto_tsquery('simple', immutable_unaccent(:q))) DESC"
)


class KbArticleRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, article: KbArticle) -> KbArticle:
        self.session.add(article)
        self.session.flush()
        return article

    def slug_exists(self, slug: str) -> bool:
        return (
            self.session.execute(
                select(func.count()).select_from(KbArticle).where(KbArticle.slug == slug)
            ).scalar_one()
            > 0
        )

    def get(self, article_id: UUID) -> KbArticle | None:
        return self.session.execute(
            select(KbArticle)
            .options(selectinload(KbArticle.category))
            .where(KbArticle.id == article_id)
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()

    def get_by_slug(self, slug: str) -> KbArticle | None:
        return self.session.execute(
            select(KbArticle)
            .options(selectinload(KbArticle.category))
            .where(KbArticle.slug == slug)
        ).scalar_one_or_none()

    def list(
        self,
        params: PageParams,
        *,
        statuses: list[ArticleStatus],
        category_id: UUID | None = None,
        tag: str | None = None,
        q: str | None = None,
    ) -> tuple[list[KbArticle], int]:
        stmt: Select = select(KbArticle).where(KbArticle.status.in_(statuses))

        if category_id is not None:
            stmt = stmt.where(KbArticle.kb_category_id == category_id)
        if tag:
            # ARRAY(Text): `any` sinh ra `:tag = ANY(tags)`
            stmt = stmt.where(KbArticle.tags.any(tag))

        keyword = (q or "").strip()
        if keyword:
            stmt = stmt.where(SEARCH_CONDITION).params(q=keyword)

        total = self.session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

        ordering = (
            [SEARCH_RANK_DESC, KbArticle.view_count.desc()]
            if keyword
            # Không có từ khoá thì không có "độ liên quan" để xếp; dùng lượt
            # xem để bài hữu ích nhất nổi lên đầu.
            else [KbArticle.view_count.desc(), KbArticle.updated_at.desc()]
        )

        rows = (
            self.session.execute(
                stmt.options(selectinload(KbArticle.category))
                .order_by(*ordering, KbArticle.id.desc())
                .offset(params.offset)
                .limit(params.limit)
                .params(q=keyword)
            )
            .scalars()
            .all()
        )

        return list(rows), total

    def suggest(self, q: str, limit: int = 5) -> list[KbArticle]:
        """Gợi ý bài viết khi người dùng đang gõ mô tả ticket (US-32).

        CHỈ bài đã publish: gợi ý bản nháp cho nhân viên là làm lộ tài liệu
        chưa được duyệt.
        """
        keyword = q.strip()
        if len(keyword) < 3:
            return []
        return list(
            self.session.execute(
                select(KbArticle)
                .where(
                    KbArticle.status == ArticleStatus.PUBLISHED,
                    SEARCH_CONDITION,
                )
                .order_by(SEARCH_RANK_DESC)
                .limit(limit)
                .params(q=keyword)
            )
            .scalars()
            .all()
        )

    def increment_view(self, article: KbArticle) -> None:
        """Tăng lượt xem bằng UPDATE nguyên tử, GIỮ NGUYÊN `updated_at`.

        Hai điểm, cả hai đều là lỗi đã xảy ra thật:

        1. `article.view_count += 1` ở Python làm mất lượt xem khi hai người
           mở cùng lúc: cả hai đọc 10, cả hai ghi 11.

        2. ★ Phải gán lại `updated_at` bằng chính giá trị cũ. Cột này có
           `onupdate=func.now()`, nên MỌI lệnh UPDATE lên hàng đều đẩy nó lên
           — kể cả lệnh chỉ đếm lượt xem. Hệ quả: cứ có người ĐỌC bài là bài
           đó bị coi là "nội dung mới hơn chỉ mục", dù không ai sửa chữ nào.

           Điều đó khiến `reconcile_stale_index` (chạy mỗi giờ) index lại mọi
           bài có người đọc — càng nhiều người dùng thì hoá đơn embedding càng
           lớn, mà không sinh thêm giá trị nào.

           Phải để cột trong `.values()`; SQLAlchemy chỉ áp `onupdate` cho cột
           KHÔNG được chỉ định tường minh.
        """
        self.session.execute(
            KbArticle.__table__.update()
            .where(KbArticle.id == article.id)
            .values(
                view_count=KbArticle.view_count + 1,
                updated_at=article.updated_at,
            )
        )

    def count_chunks(self, article_id: UUID) -> int:
        return self.session.execute(
            select(func.count())
            .select_from(ArticleChunk)
            .where(ArticleChunk.article_id == article_id)
        ).scalar_one()


class KbCategoryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, category: KbCategory) -> KbCategory:
        self.session.add(category)
        self.session.flush()
        return category

    def get(self, category_id: UUID) -> KbCategory | None:
        return self.session.get(KbCategory, category_id)

    def slug_exists(self, slug: str) -> bool:
        return (
            self.session.execute(
                select(func.count()).select_from(KbCategory).where(KbCategory.slug == slug)
            ).scalar_one()
            > 0
        )

    def list_with_counts(self, *, published_only: bool) -> list[tuple[KbCategory, int]]:
        """Chủ đề kèm SỐ BÀI (US-31).

        Đếm bằng LEFT JOIN trong một truy vấn. Lặp qua từng chủ đề rồi đếm
        riêng là N+1 — với 5 chủ đề thì không sao, nhưng đây là mẫu code mà
        người khác sẽ chép lại.
        """
        condition = KbArticle.kb_category_id == KbCategory.id
        if published_only:
            condition = condition & (KbArticle.status == ArticleStatus.PUBLISHED)

        rows = self.session.execute(
            select(KbCategory, func.count(KbArticle.id))
            .outerjoin(KbArticle, condition)
            .group_by(KbCategory.id)
            .order_by(KbCategory.sort_order, KbCategory.name)
        ).all()
        return [(row[0], row[1]) for row in rows]
