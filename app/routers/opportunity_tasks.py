"""Opportunity Tasks Router with RBAC and Data Scope Filtering."""
import math
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import (
    DataScope,
    check_scope_access,
    get_current_user,
    resolve_scope,
)
from app.schemas.opportunity_task import (
    OpportunityTaskCreate,
    OpportunityTaskListResponse,
    OpportunityTaskResponse,
    OpportunityTaskUpdate,
)
from app.services.opportunity_task_service import (
    create_task_record,
    delete_task_record,
    get_raw_task_by_id,
    get_tasks_by_scope,
    update_task_record,
)

router = APIRouter(
    tags=["Opportunity Tasks"],
)


@router.get("/opportunity-tasks", response_model=OpportunityTaskListResponse)
def list_opportunity_tasks(
    scope: Optional[str] = Query(None, description="Data scope: MY, MY_TEAM, TEAM, ALL"),
    opportunity_id: Optional[str] = Query(None, description="Lọc theo cơ hội"),
    assigned_to_id: Optional[int] = Query(None, description="Lọc theo người phụ trách"),
    status: Optional[str] = Query(None, description="Lọc theo trạng thái công việc"),
    search: Optional[str] = Query(None, description="Tìm kiếm theo tiêu đề/mô tả"),
    page: Optional[int] = Query(1, ge=1, description="Trang hiện tại"),
    limit: Optional[int] = Query(20, ge=1, le=100, description="Số lượng mỗi trang"),
    current_user: dict = Depends(get_current_user),
):
    effective_scope = resolve_scope(current_user, scope)
    tasks = get_tasks_by_scope(
        current_user=current_user,
        scope=effective_scope,
        opportunity_id=opportunity_id,
        assigned_to_id=assigned_to_id,
        status=status,
        search=search,
    )
    total = len(tasks)
    eff_page = page or 1
    eff_limit = limit or 20
    start = (eff_page - 1) * eff_limit
    end = start + eff_limit
    paged_items = tasks[start:end]
    total_pages = max(1, math.ceil(total / eff_limit)) if total > 0 else 1

    return {
        "items": paged_items,
        "total": total,
        "page": eff_page,
        "limit": eff_limit,
        "total_pages": total_pages,
    }


@router.get("/opportunities/{opportunity_id}/tasks", response_model=OpportunityTaskListResponse)
def list_tasks_for_opportunity(
    opportunity_id: str,
    scope: Optional[str] = Query(None, description="Data scope: MY, MY_TEAM, TEAM, ALL"),
    assigned_to_id: Optional[int] = Query(None, description="Lọc theo người phụ trách"),
    status: Optional[str] = Query(None, description="Lọc theo trạng thái"),
    search: Optional[str] = Query(None, description="Tìm kiếm"),
    page: Optional[int] = Query(1, ge=1),
    limit: Optional[int] = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    return list_opportunity_tasks(
        scope=scope,
        opportunity_id=opportunity_id,
        assigned_to_id=assigned_to_id,
        status=status,
        search=search,
        page=page,
        limit=limit,
        current_user=current_user,
    )


@router.get("/opportunity-tasks/{task_id}", response_model=OpportunityTaskResponse)
def get_opportunity_task(
    task_id: str,
    current_user: dict = Depends(get_current_user),
):
    task = get_raw_task_by_id(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy công việc với ID: {task_id}",
        )

    # Kiểm tra phân quyền truy cập bản ghi
    if not check_scope_access(current_user, owner_id=task.get("owner_id", 1), team_id=task.get("team_id")):
        # Nếu được gán cho chính user này thì vẫn cho phép xem
        if task.get("assigned_to_id") != current_user.get("id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền truy cập công việc này",
            )

    return task


@router.post("/opportunity-tasks", response_model=OpportunityTaskResponse, status_code=status.HTTP_201_CREATED)
def create_opportunity_task(
    payload: OpportunityTaskCreate,
    current_user: dict = Depends(get_current_user),
):
    created = create_task_record(payload.model_dump(), current_user)
    return created


@router.post("/opportunities/{opportunity_id}/tasks", response_model=OpportunityTaskResponse, status_code=status.HTTP_201_CREATED)
def create_opportunity_task_for_opp(
    opportunity_id: str,
    payload: OpportunityTaskCreate,
    current_user: dict = Depends(get_current_user),
):
    data = payload.model_dump()
    data["opportunity_id"] = opportunity_id
    created = create_task_record(data, current_user)
    return created


@router.put("/opportunity-tasks/{task_id}", response_model=OpportunityTaskResponse)
def update_opportunity_task(
    task_id: str,
    payload: OpportunityTaskUpdate,
    current_user: dict = Depends(get_current_user),
):
    task = get_raw_task_by_id(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy công việc với ID: {task_id}",
        )

    if not check_scope_access(current_user, owner_id=task.get("owner_id", 1), team_id=task.get("team_id")):
        if task.get("assigned_to_id") != current_user.get("id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền chỉnh sửa công việc này",
            )

    updated = update_task_record(task_id, payload.model_dump(exclude_unset=True), current_user)
    return updated


@router.delete("/opportunity-tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_opportunity_task(
    task_id: str,
    current_user: dict = Depends(get_current_user),
):
    task = get_raw_task_by_id(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy công việc với ID: {task_id}",
        )

    if not check_scope_access(current_user, owner_id=task.get("owner_id", 1), team_id=task.get("team_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền xóa công việc này",
        )

    delete_task_record(task_id)
    return None
