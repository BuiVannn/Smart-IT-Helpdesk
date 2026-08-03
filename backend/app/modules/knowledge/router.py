"""Endpoint kho tài liệu (US-28, US-29, US-30, US-31, US-32)."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_db
from app.modules.knowledge.constants import ArticleStatus
from app.modules.knowledge.models import KbArticle
from app.modules.knowledge.schemas import (
    ArticleListItem,
    ArticleResponse,
    CategoryResponse,
    CreateArticleRequest,
    CreateCategoryRequest,
    SuggestionItem,
    UpdateArticleRequest,
)
from app.modules.knowledge.service import KbArticleService, KbCategoryService
from app.modules.users.models import User

router = APIRouter()


def get_article_service(db: Session = Depends(get_db)) -> KbArticleService:
    return KbArticleService(db)


def get_category_service(db: Session = Depends(get_db)) -> KbCategoryService:
    return KbCategoryService(db)


def _detail(service: KbArticleService, article: KbArticle) -> ArticleResponse:
    response = ArticleResponse.model_validate(article)
    response.is_index_stale = service.is_index_stale(article)
    return response


# ── Chủ đề (US-31) ────────────────────────────────────────────────────
# Đặt TRƯỚC "/articles/{slug}" là không cần thiết (khác tiền tố), nhưng đặt
# trước cho dễ đọc: chủ đề là khung phân loại, bài viết nằm trong đó.


@router.get(
    "/categories",
    response_model=list[CategoryResponse],
    summary="Danh sách chủ đề kèm số bài (US-31)",
)
def list_categories(
    current_user: User = Depends(get_current_user),
    service: KbCategoryService = Depends(get_category_service),
) -> list[CategoryResponse]:
    return [
        CategoryResponse(
            id=c.id,
            slug=c.slug,
            name=c.name,
            parent_id=c.parent_id,
            sort_order=c.sort_order,
            article_count=count,
        )
        for c, count in service.list(current_user)
    ]


@router.post(
    "/categories",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo chủ đề (Admin)",
)
def create_category(
    data: CreateCategoryRequest,
    current_user: User = Depends(get_current_user),
    service: KbCategoryService = Depends(get_category_service),
) -> CategoryResponse:
    c = service.create(current_user, data)
    return CategoryResponse(
        id=c.id,
        slug=c.slug,
        name=c.name,
        parent_id=c.parent_id,
        sort_order=c.sort_order,
        article_count=0,
    )


# ── Bài viết ──────────────────────────────────────────────────────────


@router.get(
    "/articles",
    response_model=Page[ArticleListItem],
    summary="Danh sách và tìm kiếm tài liệu (US-30)",
)
def list_articles(
    params: PageParams = Depends(page_params),
    q: str | None = Query(default=None, max_length=200, description="Tìm toàn văn"),
    category_id: UUID | None = Query(default=None, alias="categoryId"),
    tag: str | None = Query(default=None, max_length=50),
    article_status: ArticleStatus | None = Query(
        default=None,
        alias="status",
        description="Chỉ Admin dùng được; vai trò khác luôn chỉ thấy PUBLISHED",
    ),
    current_user: User = Depends(get_current_user),
    service: KbArticleService = Depends(get_article_service),
) -> Page[ArticleListItem]:
    rows, total = service.list(
        current_user, params, status=article_status, category_id=category_id, tag=tag, q=q
    )
    return Page.create([ArticleListItem.model_validate(a) for a in rows], total, params)


@router.get(
    "/articles/suggest",
    response_model=list[SuggestionItem],
    summary="Gợi ý bài viết khi đang mô tả sự cố (US-32)",
)
def suggest_articles(
    q: str = Query(min_length=3, max_length=200),
    limit: int = Query(default=5, ge=1, le=10),
    _: User = Depends(get_current_user),
    service: KbArticleService = Depends(get_article_service),
) -> list[SuggestionItem]:
    # Phải khai báo TRƯỚC "/articles/{slug}", nếu không FastAPI khớp "suggest"
    # như một slug và luôn trả 404.
    return [SuggestionItem.model_validate(a) for a in service.suggest(q, limit)]


@router.get(
    "/articles/{slug}",
    response_model=ArticleResponse,
    summary="Chi tiết tài liệu theo đường dẫn",
)
def get_article(
    slug: str,
    current_user: User = Depends(get_current_user),
    service: KbArticleService = Depends(get_article_service),
) -> ArticleResponse:
    return _detail(service, service.get_by_slug(current_user, slug))


@router.post(
    "/articles",
    response_model=ArticleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Soạn tài liệu mới — luôn tạo ở trạng thái nháp (US-28)",
)
def create_article(
    data: CreateArticleRequest,
    current_user: User = Depends(get_current_user),
    service: KbArticleService = Depends(get_article_service),
) -> ArticleResponse:
    return _detail(service, service.create(current_user, data))


@router.patch(
    "/articles/{article_id}",
    response_model=ArticleResponse,
    summary="Sửa tài liệu (US-28)",
)
def update_article(
    article_id: UUID,
    data: UpdateArticleRequest,
    current_user: User = Depends(get_current_user),
    service: KbArticleService = Depends(get_article_service),
) -> ArticleResponse:
    return _detail(service, service.update(current_user, article_id, data))


@router.post(
    "/articles/{article_id}/publish",
    response_model=ArticleResponse,
    summary="Xuất bản và đưa vào chỉ mục chatbot (US-28, US-29)",
)
def publish_article(
    article_id: UUID,
    current_user: User = Depends(get_current_user),
    service: KbArticleService = Depends(get_article_service),
) -> ArticleResponse:
    # ★ Đây là mắt xích cuối của pipeline RAG: xuất bản là lúc DUY NHẤT
    # chatbot học được nội dung mới. Việc index chạy nền qua Celery.
    return _detail(service, service.publish(current_user, article_id))


@router.post(
    "/articles/{article_id}/unpublish",
    response_model=ArticleResponse,
    summary="Gỡ xuất bản và xoá khỏi chỉ mục chatbot",
)
def unpublish_article(
    article_id: UUID,
    current_user: User = Depends(get_current_user),
    service: KbArticleService = Depends(get_article_service),
) -> ArticleResponse:
    return _detail(service, service.unpublish(current_user, article_id))


@router.post(
    "/articles/{article_id}/reindex",
    response_model=ArticleResponse,
    summary="Ép index lại một bài",
)
def reindex_article(
    article_id: UUID,
    current_user: User = Depends(get_current_user),
    service: KbArticleService = Depends(get_article_service),
) -> ArticleResponse:
    return _detail(service, service.request_reindex(current_user, article_id))
