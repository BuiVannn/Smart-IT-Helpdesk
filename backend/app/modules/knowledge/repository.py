"""Repository cho module kho tài liệu (knowledge base).

Quy tắc (theo file mẫu app/modules/users/repository.py):
- Nhận Session qua constructor, KHÔNG tự tạo session
- CHỈ truy vấn và ánh xạ — không chứa logic nghiệp vụ
- Trả về model/entity, KHÔNG trả về Pydantic schema
- KHÔNG commit — việc mở/đóng transaction là của service
"""

from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.pagination import PageParams
from app.modules.knowledge.constants import ArticleStatus
from app.modules.knowledge.models import KbArticle


class ArticleRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, article: KbArticle) -> KbArticle:
        self.session.add(article)
        self.session.flush()  # để lấy id, nhưng KHÔNG commit
        return article

    def get_by_slug(self, slug: str, published_only: bool = True) -> KbArticle | None:
        """Tra một bài theo slug.

        published_only=True mặc định — nhân viên không được đọc bài DRAFT.
        Chỉ Admin mới truyền published_only=False.
        """
        stmt = select(KbArticle).where(KbArticle.slug == slug)
        if published_only:
            stmt = stmt.where(KbArticle.status == ArticleStatus.PUBLISHED)
        return self.session.execute(stmt).scalar_one_or_none()

    def list(
        self,
        params: PageParams,
        *,
        category_id: UUID | None = None,
        status: ArticleStatus | None = None,
        q: str | None = None,
    ) -> tuple[list[KbArticle], int]:
        """Trả về (danh sách, tổng số) — tổng số cần cho phân trang."""
        stmt: Select = select(KbArticle)

        if category_id is not None:
            stmt = stmt.where(KbArticle.kb_category_id == category_id)
        if status is not None:
            stmt = stmt.where(KbArticle.status == status)
        if q:
            # unaccent cho phép gõ "mat khau" tìm ra "mật khẩu"
            stmt = stmt.where(
                KbArticle.search_vector.op("@@")(
                    func.plainto_tsquery("simple", func.unaccent(q))
                )
            )

        total = self.session.execute(
            select(func.count()).select_from(stmt.subquery())
        ).scalar_one()

        rows = (
            self.session.execute(
                stmt.order_by(KbArticle.created_at.desc())
                .offset(params.offset)
                .limit(params.limit)
            )
            .scalars()
            .all()
        )

        return list(rows), total

    def list_stale_for_index(self) -> list[KbArticle]:
        """Bài PUBLISHED cần index lại — phục vụ chatbot RAG.

        indexed_at rỗng (chưa từng index) hoặc cũ hơn lần sửa gần nhất.
        """
        stmt = select(KbArticle).where(
            KbArticle.status == ArticleStatus.PUBLISHED,
            (KbArticle.indexed_at.is_(None))
            | (KbArticle.indexed_at < KbArticle.updated_at),
        )
        return list(self.session.execute(stmt).scalars().all())