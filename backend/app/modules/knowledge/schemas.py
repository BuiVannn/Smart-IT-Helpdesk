"""Schema kho tài liệu (US-28, US-30, US-31).

Giới hạn phải khớp CHECK constraint trong models.py — nội dung tối thiểu 20
ký tự, tiêu đề tối đa 200. Lệch nhau thì người soạn thảo nhận 500 từ database
thay vì thông báo rõ ràng.
"""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.core.schemas import ResponseModel, StrictModel
from app.modules.knowledge.constants import ArticleStatus
from app.modules.users.schemas import UserBrief


class CategoryBrief(ResponseModel):
    id: UUID
    slug: str
    name: str


# ─────────────── Input ───────────────


class CreateArticleRequest(StrictModel):
    title: str = Field(min_length=5, max_length=200)
    content_md: str = Field(alias="contentMd", min_length=20)
    summary: str | None = Field(default=None, max_length=500)
    kb_category_id: UUID | None = Field(default=None, alias="kbCategoryId")
    ticket_category_id: UUID | None = Field(default=None, alias="ticketCategoryId")
    tags: list[str] = Field(default_factory=list, max_length=10)
    # Slug tự sinh từ tiêu đề nếu không truyền. Cho phép truyền tay để giữ
    # nguyên đường dẫn cũ khi di chuyển tài liệu từ hệ thống khác sang.
    slug: str | None = Field(default=None, max_length=200, pattern=r"^[a-z0-9-]+$")


class UpdateArticleRequest(StrictModel):
    title: str | None = Field(default=None, min_length=5, max_length=200)
    content_md: str | None = Field(default=None, alias="contentMd", min_length=20)
    summary: str | None = Field(default=None, max_length=500)
    kb_category_id: UUID | None = Field(default=None, alias="kbCategoryId")
    ticket_category_id: UUID | None = Field(default=None, alias="ticketCategoryId")
    tags: list[str] | None = Field(default=None, max_length=10)
    version: int = Field(ge=1)


class CreateCategoryRequest(StrictModel):
    name: str = Field(min_length=2, max_length=100)
    slug: str | None = Field(default=None, max_length=50, pattern=r"^[a-z0-9-]+$")
    parent_id: UUID | None = Field(default=None, alias="parentId")
    sort_order: int = Field(default=0, alias="sortOrder", ge=0, le=999)


# ─────────────── Output ───────────────


class ArticleListItem(ResponseModel):
    """Bản rút gọn cho danh sách — KHÔNG có `contentMd`.

    Một bài hướng dẫn dài vài nghìn ký tự; trả kèm 20 bài trong danh sách là
    hàng trăm KB mỗi lần tải trang mà không ai đọc tới.
    """

    id: UUID
    slug: str
    title: str
    summary: str | None
    status: ArticleStatus
    category: CategoryBrief | None = None
    tags: list[str]
    view_count: int = Field(serialization_alias="viewCount")
    published_at: datetime | None = Field(default=None, serialization_alias="publishedAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")
    version: int


class ArticleResponse(ArticleListItem):
    content_md: str = Field(serialization_alias="contentMd")
    author: UserBrief | None = None
    ticket_category_id: UUID | None = Field(default=None, serialization_alias="ticketCategoryId")
    created_at: datetime = Field(serialization_alias="createdAt")
    # NULL hoặc cũ hơn updated_at ⇒ chatbot đang dùng bản chưa cập nhật
    indexed_at: datetime | None = Field(default=None, serialization_alias="indexedAt")
    # Không đọc được từ ORM (là suy luận, không phải cột) nên phải có mặc định;
    # router tính rồi gán đè. Thiếu default thì `model_validate` vỡ ngay.
    is_index_stale: bool = Field(default=False, serialization_alias="isIndexStale")


class CategoryResponse(CategoryBrief):
    parent_id: UUID | None = Field(default=None, serialization_alias="parentId")
    sort_order: int = Field(serialization_alias="sortOrder")
    article_count: int = Field(default=0, serialization_alias="articleCount")


class SuggestionItem(ResponseModel):
    """Gợi ý hiển thị khi người dùng đang gõ mô tả ticket (US-32)."""

    id: UUID
    slug: str
    title: str
    summary: str | None


class IndexResultResponse(ResponseModel):
    slug: str
    chunks_created: int = Field(serialization_alias="chunksCreated")
    chunks_removed: int = Field(serialization_alias="chunksRemoved")
    skipped_reason: str | None = Field(default=None, serialization_alias="skippedReason")
