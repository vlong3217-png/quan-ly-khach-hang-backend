"""
Quote API router with role-based access control and data scope filtering.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import (
    DataScope,
    check_scope_access,
    get_current_user,
    require_roles,
    resolve_scope,
)
from app.schemas.quote import (
    QuoteCreate,
    QuoteListResponse,
    QuoteResponse,
    QuoteUpdate,
)
from app.services.quote_service import (
    create_quote_record,
    delete_quote_record,
    get_quotes_by_scope,
    get_raw_quote_by_id,
    update_quote_record,
)

router = APIRouter(
    prefix="/quotes",
    tags=["Quotes"],
)


@router.get("", response_model=QuoteListResponse)
def list_quotes(
    scope: Optional[str] = Query(
        None,
        description="Data scope filter: MY, MY_TEAM, TEAM, or ALL. Defaults based on role.",
    ),
    search: Optional[str] = Query(None, description="Search query"),
    q: Optional[str] = Query(None, description="Search query alias"),
    current_user: dict = Depends(get_current_user),
):
    effective_scope = resolve_scope(current_user, scope)
    search_query = search or q
    quotes = get_quotes_by_scope(current_user, effective_scope, search=search_query)
    return {
        "scope": effective_scope.value,
        "total": len(quotes),
        "quotes": quotes,
    }


@router.get("/{quote_id}", response_model=QuoteResponse)
def get_quote(
    quote_id: int,
    current_user: dict = Depends(get_current_user),
):
    q_item = get_raw_quote_by_id(quote_id)
    if q_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy báo giá",
        )

    if not check_scope_access(current_user, q_item["owner_id"], q_item.get("team_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền truy cập dữ liệu báo giá này",
        )

    return q_item


@router.post("", response_model=QuoteResponse, status_code=status.HTTP_201_CREATED)
def create_quote(
    payload: QuoteCreate,
    current_user: dict = Depends(require_roles(["ADMIN", "MANAGER"])),
):
    new_q = create_quote_record(payload.model_dump(), current_user)
    return new_q


@router.put("/{quote_id}", response_model=QuoteResponse)
def update_quote(
    quote_id: int,
    payload: QuoteUpdate,
    current_user: dict = Depends(get_current_user),
):
    q_item = get_raw_quote_by_id(quote_id)
    if q_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy báo giá",
        )

    if not check_scope_access(current_user, q_item["owner_id"], q_item.get("team_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền chỉnh sửa dữ liệu báo giá này",
        )

    updated = update_quote_record(quote_id, payload.model_dump(exclude_unset=True))
    return updated


@router.delete(
    "/{quote_id}",
    dependencies=[Depends(require_roles(["ADMIN"]))],
)
def delete_quote(quote_id: int):
    success = delete_quote_record(quote_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy báo giá để xóa",
        )
    return {"message": f"Đã xóa báo giá ID {quote_id}"}
