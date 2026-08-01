"""Schema cho module kho tài liệu (knowledge base).

Quy tắc (theo file mẫu app/modules/auth/schemas.py):
- extra="forbid": field lạ bị TỪ CHỐI, không âm thầm bỏ qua
- Tách Input (client gửi) và Response (server trả) — không dùng chung một class
- Response dùng alias camelCase để khớp hợp đồng API (docs/design/06)
- ArticleListItem KHÔNG có contentMd — bài dài, không cần trong danh sách
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.knowledge.constants import ArticleStatus


class StrictModel(BaseModel):
    """Base cho mọi schema đầu vào — từ chối field lạ."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ResponseModel(BaseModel):
    """Base cho mọi schema đầu ra — đọc được từ ORM, trả về camelCase."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ─────────────── Input ───────────────


class ArticleCreate(StrictModel):
    title: str = Field(min_length=5, max_length=200)
    summary: str | None = Field(default=None, max_length=500)
    content_md: str = Field(min_length=20, alias="contentMd")
    kb_category_id: UUID | None = Field(default=None, alias="kbCategoryId")
    tags: list[str] = Field(default_factory=list)


class ArticleUpdate(StrictModel):
    """Sửa bài viết — tất cả optional, chỉ gửi field cần đổi."""

    title: str | None = Field(default=None, min_length=5, max_length=200)
    summary: str | None = Field(default=None, max_length=500)
    content_md: str | None = Field(default=None, min_length=20, alias="contentMd")
    kb_category_id: UUID | None = Field(default=None, alias="kbCategoryId")
    tags: list[str] | None = None
    status: ArticleStatus | None = None


# ─────────────── Output ───────────────


class ArticleResponse(ResponseModel):
    """Chi tiết đầy đủ một bài viết — dùng cho trang xem bài."""

    id: UUID
    slug: str
    title: str
    summary: str | None = None
    content_md: str = Field(serialization_alias="contentMd")
    status: ArticleStatus
    tags: list[str]
    view_count: int = Field(serialization_alias="viewCount")
    published_at: datetime | None = Field(default=None, serialization_alias="publishedAt")
    created_at: datetime = Field(serialization_alias="createdAt")


class ArticleListItem(ResponseModel):
    """Bản rút gọn cho danh sách — KHÔNG có contentMd (lãng phí băng thông)."""

    id: UUID
    slug: str
    title: str
    summary: str | None = None
    status: ArticleStatus
    tags: list[str]
    view_count: int = Field(serialization_alias="viewCount")
    published_at: datetime | None = Field(default=None, serialization_alias="publishedAt")
    created_at: datetime = Field(serialization_alias="createdAt")