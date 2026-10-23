from math import ceil
from typing import Generic, List, TypeVar

from pydantic import BaseModel

ItemT = TypeVar("ItemT")


class PaginatedResponse(BaseModel, Generic[ItemT]):
    items: List[ItemT]
    total: int
    page: int
    limit: int
    total_pages: int


def make_paginated_response(items: List[ItemT], page: int, limit: int, total: int) -> dict:
    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": max(1, ceil(total / limit)) if total else 1,
    }