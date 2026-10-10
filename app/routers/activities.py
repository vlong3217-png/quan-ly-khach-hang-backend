"""
Activity API router with role-based access control and data scope filtering.
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
from app.schemas.activity import (
    ActivityCreate,
    ActivityListResponse,
    ActivityResponse,
    ActivityUpdate,
)
from app.services.activity_service import (
    create_activity_record,
    delete_activity_record,
    get_activities_by_scope,
    get_raw_activity_by_id,
    update_activity_record,
)

router = APIRouter(
    prefix="/activities",
    tags=["Activities"],
)


@router.get("", response_model=ActivityListResponse)
def list_activities(
    scope: Optional[str] = Query(
        None,
        description="Data scope filter: MY, MY_TEAM, TEAM, or ALL. Defaults based on role.",
    ),
    search: Optional[str] = Query(None, description="Search query"),
    q: Optional[str] = Query(None, description="Search query alias"),
    page: Optional[int] = Query(None, ge=1, description="Trang hiện tại (bắt đầu từ 1)"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Số lượng hoạt động mỗi trang (mặc định 20)"),
    skip: Optional[int] = Query(None, ge=0, description="Vị trí bắt đầu (offset)"),
    current_user: dict = Depends(get_current_user),
):
    import math

    effective_scope = resolve_scope(current_user, scope)
    search_query = search or q
    all_activities = get_activities_by_scope(current_user, effective_scope, search=search_query)
    total = len(all_activities)

    effective_limit = limit if limit is not None else 20
    if page is not None:
        effective_skip = (page - 1) * effective_limit
        effective_page = page
    elif skip is not None:
        effective_skip = skip
        effective_page = (effective_skip // effective_limit) + 1
    else:
        effective_skip = 0
        effective_page = 1

    paged_items = all_activities[effective_skip : effective_skip + effective_limit]
    total_pages = max(1, math.ceil(total / effective_limit)) if total > 0 else 1

    return {
        "scope": effective_scope.value,
        "total": total,
        "activities": paged_items,
        "page": effective_page,
        "limit": effective_limit,
        "skip": effective_skip,
        "total_pages": total_pages,
    }


@router.get("/{activity_id}", response_model=ActivityResponse)
def get_activity(
    activity_id: int,
    current_user: dict = Depends(get_current_user),
):
    act = get_raw_activity_by_id(activity_id)
    if act is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy hoạt động",
        )

    if not check_scope_access(current_user, act["owner_id"], act.get("team_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền truy cập dữ liệu hoạt động này",
        )

    return act


@router.post("", response_model=ActivityResponse, status_code=status.HTTP_201_CREATED)
def create_activity(
    payload: ActivityCreate,
    current_user: dict = Depends(require_roles(["ADMIN", "MANAGER"])),
):
    new_act = create_activity_record(payload.model_dump(), current_user)
    return new_act


@router.put("/{activity_id}", response_model=ActivityResponse)
def update_activity(
    activity_id: int,
    payload: ActivityUpdate,
    current_user: dict = Depends(get_current_user),
):
    act = get_raw_activity_by_id(activity_id)
    if act is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy hoạt động",
        )

    if not check_scope_access(current_user, act["owner_id"], act.get("team_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền chỉnh sửa dữ liệu hoạt động này",
        )

    updated = update_activity_record(activity_id, payload.model_dump(exclude_unset=True))
    return updated


@router.delete(
    "/{activity_id}",
    dependencies=[Depends(require_roles(["ADMIN"]))],
)
def delete_activity(activity_id: int):
    success = delete_activity_record(activity_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy hoạt động để xóa",
        )
    return {"message": f"Đã xóa hoạt động ID {activity_id}"}
