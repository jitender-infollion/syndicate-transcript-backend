from typing import Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel
from sqlalchemy.orm import Query as SAQuery

T = TypeVar("T")


class PaginationParams:
    def __init__(self, page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100)):
        self.page = page
        self.limit = limit

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit


class PageMeta(BaseModel):
    page: int
    limit: int
    total: int
    totalPages: int


class Page(BaseModel, Generic[T]):
    items: list[T]
    meta: PageMeta


def paginate(query: SAQuery, params: PaginationParams) -> tuple[list, int]:
    total = query.order_by(None).count()
    items = query.offset(params.offset).limit(params.limit).all()
    return items, total


def build_page(items: list[T], total: int, params: PaginationParams) -> Page:
    # params.limit is always >= 1 (enforced by Query/Field), so no zero-division guard needed.
    total_pages = (total + params.limit - 1) // params.limit
    return Page(items=items, meta=PageMeta(page=params.page, limit=params.limit, total=total, totalPages=total_pages))
