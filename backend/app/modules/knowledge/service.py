"""KbArticleService — soạn thảo, xuất bản, tìm kiếm tài liệu (US-28, 30, 31).

★ MẮT XÍCH CUỐI CỦA PIPELINE RAG (US-29)
Xuất bản một bài viết là lúc DUY NHẤT chatbot học được nội dung mới. Việc
index chạy NỀN qua Celery: sinh embedding cho một bài mất vài giây tới vài
chục giây tuỳ độ dài, chờ đồng bộ nghĩa là người soạn thảo bấm "Xuất bản" rồi
ngồi nhìn màn hình quay.

Đổi lại, bài vừa publish CHƯA trả lời được ngay. Đó là đánh đổi có chủ ý và
giao diện phải nói rõ ("đang cập nhật cho trợ lý ảo"), chứ không giấu.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.core.logging import get_logger
from app.core.pagination import PageParams
from app.modules.knowledge.constants import ArticleStatus
from app.modules.knowledge.models import KbArticle, KbCategory
from app.modules.knowledge.repository import KbArticleRepository, KbCategoryRepository
from app.modules.knowledge.schemas import (
    CreateArticleRequest,
    CreateCategoryRequest,
    UpdateArticleRequest,
)
from app.modules.knowledge.slug import slugify, unique_slug
from app.modules.users.constants import UserRole
from app.modules.users.models import User

logger = get_logger(__name__)

# Người ngoài đội IT chỉ thấy bài đã xuất bản (BR-11)
PUBLIC_STATUSES = [ArticleStatus.PUBLISHED]


class KbArticleService:
    def __init__(self, session: Session) -> None:
        self.db = session
        self.articles = KbArticleRepository(session)
        self.categories = KbCategoryRepository(session)

    # ── Đọc ───────────────────────────────────────────────────────────

    def list(
        self,
        user: User,
        params: PageParams,
        *,
        status: ArticleStatus | None = None,
        category_id: UUID | None = None,
        tag: str | None = None,
        q: str | None = None,
    ) -> tuple[list[KbArticle], int]:
        statuses = self._visible_statuses(user, status)
        return self.articles.list(
            params, statuses=statuses, category_id=category_id, tag=tag, q=q
        )

    def get_by_slug(self, user: User, slug: str, *, count_view: bool = True) -> KbArticle:
        article = self.articles.get_by_slug(slug)
        # 404 chứ không phải 403 với bản nháp: nhân viên không cần biết đội IT
        # đang soạn tài liệu gì.
        if article is None or article.status not in self._visible_statuses(user, None):
            raise NotFoundError("Không tìm thấy tài liệu")

        if count_view and article.status == ArticleStatus.PUBLISHED:
            self.articles.increment_view(article)
            self.db.commit()
            self.db.refresh(article)
        return article

    def suggest(self, q: str, limit: int = 5) -> list[KbArticle]:
        return self.articles.suggest(q, limit)

    def is_index_stale(self, article: KbArticle) -> bool:
        """Chatbot đang dùng bản cũ hay bản mới nhất?

        Người soạn thảo cần thấy điều này: sửa bài xong mà chatbot vẫn trả lời
        theo bản cũ là tình huống bối rối nhất khi vận hành.
        """
        if article.status != ArticleStatus.PUBLISHED:
            return False
        if article.indexed_at is None:
            return True
        return article.indexed_at < article.updated_at

    # ── Soạn thảo ─────────────────────────────────────────────────────

    def create(self, user: User, data: CreateArticleRequest) -> KbArticle:
        self._require_editor(user)

        slug = (
            data.slug
            if data.slug and not self.articles.slug_exists(data.slug)
            else unique_slug(data.slug or data.title, self.articles.slug_exists)
        )
        if data.kb_category_id and self.categories.get(data.kb_category_id) is None:
            raise ValidationError("Chủ đề không tồn tại")

        article = self.articles.add(
            KbArticle(
                slug=slug,
                title=data.title.strip(),
                summary=(data.summary or "").strip() or None,
                content_md=data.content_md.strip(),
                # Luôn tạo ở DRAFT. Xuất bản là hành động RIÊNG và có chủ ý —
                # tạo thẳng ở PUBLISHED nghĩa là một cú Ctrl+S nhầm sẽ đẩy bản
                # nháp dở dang vào miệng chatbot.
                status=ArticleStatus.DRAFT,
                kb_category_id=data.kb_category_id,
                ticket_category_id=data.ticket_category_id,
                tags=[t.strip() for t in data.tags if t.strip()],
                author_id=user.id,
            )
        )
        self.db.commit()
        logger.info("tạo bài viết", extra={"extra_fields": {"slug": slug}})
        return self.articles.get(article.id)

    def update(self, user: User, article_id: UUID, data: UpdateArticleRequest) -> KbArticle:
        self._require_editor(user)
        article = self._load(article_id)
        self._check_version(article, data.version)

        if data.title is not None:
            article.title = data.title.strip()
        if data.content_md is not None:
            article.content_md = data.content_md.strip()
        if data.summary is not None:
            article.summary = data.summary.strip() or None
        if data.kb_category_id is not None:
            if self.categories.get(data.kb_category_id) is None:
                raise ValidationError("Chủ đề không tồn tại")
            article.kb_category_id = data.kb_category_id
        if data.ticket_category_id is not None:
            article.ticket_category_id = data.ticket_category_id
        if data.tags is not None:
            article.tags = [t.strip() for t in data.tags if t.strip()]

        article.version += 1
        self.db.commit()

        # Sửa nội dung bài ĐANG xuất bản ⇒ chỉ mục cũ đi, phải index lại.
        # Không có bước này, chatbot tiếp tục trả lời theo bản cũ vô thời hạn.
        if article.status == ArticleStatus.PUBLISHED:
            self._schedule_index(article, reason="nội dung thay đổi")

        return self.articles.get(article.id)

    # ── Xuất bản ──────────────────────────────────────────────────────

    def publish(self, user: User, article_id: UUID) -> KbArticle:
        self._require_editor(user)
        article = self._load(article_id)

        if article.status == ArticleStatus.PUBLISHED:
            raise ConflictError("Tài liệu đã được xuất bản")
        if len(article.content_md.strip()) < 20:
            raise ValidationError("Nội dung quá ngắn để xuất bản")

        article.status = ArticleStatus.PUBLISHED
        # CHECK constraint yêu cầu published_at khác NULL khi PUBLISHED.
        # Giữ mốc lần xuất bản ĐẦU TIÊN — gỡ rồi đăng lại không phải bài mới.
        article.published_at = article.published_at or datetime.now(UTC)
        article.version += 1
        self.db.commit()

        self._schedule_index(article, reason="vừa xuất bản")
        logger.info("xuất bản tài liệu", extra={"extra_fields": {"slug": article.slug}})
        return self.articles.get(article.id)

    def unpublish(self, user: User, article_id: UUID) -> KbArticle:
        self._require_editor(user)
        article = self._load(article_id)

        if article.status != ArticleStatus.PUBLISHED:
            raise ConflictError("Tài liệu chưa được xuất bản")

        article.status = ArticleStatus.ARCHIVED
        article.version += 1
        self.db.commit()

        # Index lại để XOÁ chunk (IndexingService tự xoá khi bài không còn
        # PUBLISHED). Retriever đã lọc theo status nên đây là lớp phòng vệ
        # thứ hai — nhưng dữ liệu đã gỡ thì không nên còn nằm trong chỉ mục.
        self._schedule_index(article, reason="đã gỡ xuất bản")
        return self.articles.get(article.id)

    def request_reindex(self, user: User, article_id: UUID) -> KbArticle:
        self._require_editor(user)
        article = self._load(article_id)
        self._schedule_index(article, reason="yêu cầu thủ công")
        return article

    # ── Nội bộ ────────────────────────────────────────────────────────

    def _schedule_index(self, article: KbArticle, *, reason: str) -> None:
        """Đẩy việc index sang Celery.

        Lỗi hàng đợi KHÔNG được làm hỏng thao tác xuất bản: bài đã lưu rồi,
        chỉ là chatbot biết tới muộn hơn. Tác vụ `reconcile_stale_index` chạy
        định kỳ sẽ nhặt lại những bài bị bỏ sót.

        ★ `retry=False` là BẮT BUỘC. Mặc định Celery thử kết nối lại broker
        nhiều lần với backoff — khi Redis chết, một cú bấm "Xuất bản" treo
        request HTTP hàng phút rồi mới báo lỗi. Đo được: bộ test chạy 192 giây
        thay vì 20 giây chỉ vì chỗ này. Thất bại NHANH rồi để job đối soát
        nhặt lại là hành vi đúng.
        """
        try:
            from app.modules.knowledge.tasks import index_article

            index_article.apply_async(args=[str(article.id)], retry=False)
            logger.info("đã xếp hàng index", extra={"extra_fields": {
                "slug": article.slug, "reason": reason
            }})
        except Exception as exc:
            logger.warning(
                f"không xếp hàng index được ({reason}), sẽ do job đối soát nhặt lại: "
                f"{type(exc).__name__}: {exc}"
            )

    def _load(self, article_id: UUID) -> KbArticle:
        article = self.articles.get(article_id)
        if article is None:
            raise NotFoundError("Không tìm thấy tài liệu")
        return article

    @staticmethod
    def _check_version(article: KbArticle, version: int) -> None:
        if article.version != version:
            raise ConflictError(
                "Tài liệu đã được người khác cập nhật. Vui lòng tải lại.",
                details={"currentVersion": article.version},
            )

    @staticmethod
    def _require_editor(user: User) -> None:
        if user.role != UserRole.ADMIN:
            raise ForbiddenError("Chỉ Admin mới soạn thảo được tài liệu")

    @staticmethod
    def _visible_statuses(
        user: User, requested: ArticleStatus | None
    ) -> list[ArticleStatus]:
        if user.role != UserRole.ADMIN:
            # Nhân viên và Agent luôn chỉ thấy bài đã xuất bản, kể cả khi cố
            # tình truyền ?status=DRAFT.
            return PUBLIC_STATUSES
        return [requested] if requested else list(ArticleStatus)


class KbCategoryService:
    def __init__(self, session: Session) -> None:
        self.db = session
        self.categories = KbCategoryRepository(session)

    def list(self, user: User) -> list[tuple[KbCategory, int]]:
        return self.categories.list_with_counts(
            published_only=user.role != UserRole.ADMIN
        )

    def create(self, user: User, data: CreateCategoryRequest) -> KbCategory:
        if user.role != UserRole.ADMIN:
            raise ForbiddenError("Chỉ Admin mới quản lý chủ đề")

        slug = data.slug or slugify(data.name)
        if self.categories.slug_exists(slug):
            raise ConflictError("Chủ đề với đường dẫn này đã tồn tại")
        if data.parent_id and self.categories.get(data.parent_id) is None:
            raise ValidationError("Chủ đề cha không tồn tại")

        category = self.categories.add(
            KbCategory(
                slug=slug,
                name=data.name.strip(),
                parent_id=data.parent_id,
                sort_order=data.sort_order,
            )
        )
        self.db.commit()
        return category
