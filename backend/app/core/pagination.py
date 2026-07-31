"""Phân trang dùng chung cho MỌI endpoint danh sách.

Mọi endpoint danh sách BẮT BUỘC phân trang ngay từ đầu — thêm sau khi
frontend đã code là một thay đổi phá vỡ tương thích.
"""

from math import ceil
from typing import Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel, Field

T = TypeVar("T")

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


def page_params(
    page: int = Query(1, ge=1, description="Trang, bắt đầu từ 1"),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, alias="pageSize"),
) -> PageParams:
    return PageParams(page=page, page_size=page_size)


class PaginationMeta(BaseModel):
    page: int
    page_size: int = Field(serialization_alias="pageSize")
    total_items: int = Field(serialization_alias="totalItems")
    total_pages: int = Field(serialization_alias="totalPages")


class Page(BaseModel, Generic[T]):
    data: list[T]
    pagination: PaginationMeta

    @classmethod
    def create(cls, items: list[T], total: int, params: PageParams) -> "Page[T]":
        return cls(
            data=items,
            pagination=PaginationMeta(
                page=params.page,
                page_size=params.page_size,
                total_items=total,
                total_pages=ceil(total / params.page_size) if params.page_size else 0,
            ),
        )
