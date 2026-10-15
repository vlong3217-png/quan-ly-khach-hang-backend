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


@router.post("", response_model=ActivityResponse, status_code=status.HTTP_201_CREATED)
def create_activity(
    payload: ActivityCreate,
    current_user: dict = Depends(get_current_user),
):
    """
    S6-05: Ghi nhận hoạt động với khách hàng:
    - 4 loại hoạt động: CALL, MEETING, EMAIL, NOTE.
    - Hỗ trợ gắn khách hàng, contact, cơ hội.
    - Cho phép ghi nhận hoạt động trong quá khứ.
    - Nhân viên đã đăng nhập đều có thể ghi nhận hoạt động theo quyền của mình.
    """
    new_act = create_activity_record(payload.model_dump(), current_user)
    return new_act


# ============================================================================
# SPRINT 6: S6-06 TASKS, S6-07 CALENDAR, S6-08 TIMELINE, S6-09 REMINDERS, S6-10 QUICK CALL
# ============================================================================

from app.schemas.activity import (
    TaskCreate,
    TaskUpdate,
    TaskResponse,
    TaskListResponse,
    TaskPostponeRequest,
    TaskCompleteRequest,
    CalendarResponse,
    TimelineResponse,
    NotificationListResponse,
    OverdueSummaryResponse,
    QuickCallLogRequest,
    QuickCallLogResponse,
)
from app.services.activity_service import (
    create_task_record,
    update_task_record,
    complete_task_record,
    postpone_task_record,
    get_task_by_id,
    list_tasks_by_scope,
    get_calendar_events,
    get_customer_timeline,
    scan_task_reminders,
    list_user_notifications,
    mark_notification_as_read,
    get_overdue_tasks_summary_for_manager,
    log_quick_call,
)


# S6-10: Ghi nhanh kết quả cuộc gọi trên điện thoại
@router.post("/quick-call", response_model=QuickCallLogResponse, status_code=status.HTTP_201_CREATED)
def quick_call_endpoint(
    payload: QuickCallLogRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    S6-10: Ghi nhanh kết quả cuộc gọi:
    - Ghi nhận kết quả, ghi chú ngắn.
    - Tự động gắn với cơ hội OPEN gần nhất nếu không chỉ định.
    - Tự động tạo Task gọi lại nếu có schedule_callback.
    """
    return log_quick_call(
        customer_id=payload.customer_id,
        result=payload.result,
        note=payload.note,
        occurred_at=payload.occurred_at,
        opportunity_id=payload.opportunity_id,
        schedule_callback=payload.schedule_callback,
        callback_note=payload.callback_note,
        current_user=current_user,
    )


# S6-06: Quản lý Công việc (Tasks)
@router.get("/tasks", response_model=TaskListResponse)
def list_tasks_endpoint(
    scope: Optional[str] = Query(None, description="MY, MY_TEAM, TEAM, ALL"),
    assignee_id: Optional[int] = Query(None, description="Lọc theo người được giao"),
    status: Optional[str] = Query(None, description="Trạng thái: PENDING, IN_PROGRESS, COMPLETED, POSTPONED"),
    priority: Optional[str] = Query(None, description="Mức ưu tiên: LOW, MEDIUM, HIGH, URGENT"),
    due_from: Optional[str] = Query(None, description="Từ hạn hoàn thành (YYYY-MM-DD)"),
    due_to: Optional[str] = Query(None, description="Đến hạn hoàn thành (YYYY-MM-DD)"),
    customer_id: Optional[int] = Query(None, description="Lọc theo khách hàng"),
    opportunity_id: Optional[int] = Query(None, description="Lọc theo cơ hội"),
    page: Optional[int] = Query(1, ge=1, description="Trang hiện tại"),
    limit: Optional[int] = Query(20, ge=1, le=100, description="Số lượng mỗi trang"),
    current_user: dict = Depends(get_current_user),
):
    """S6-06: Danh sách công việc theo bộ lọc và phân quyền."""
    import math
    effective_scope = resolve_scope(current_user, scope)
    eff_page = page or 1
    eff_limit = limit or 20
    skip = (eff_page - 1) * eff_limit

    items, total = list_tasks_by_scope(
        current_user=current_user,
        scope=effective_scope,
        assignee_id=assignee_id,
        task_status=status,
        priority=priority,
        due_from=due_from,
        due_to=due_to,
        customer_id=customer_id,
        opportunity_id=opportunity_id,
        skip=skip,
        limit=eff_limit,
    )
    total_pages = max(1, math.ceil(total / eff_limit)) if total > 0 else 1

    return {
        "total": total,
        "page": eff_page,
        "limit": eff_limit,
        "total_pages": total_pages,
        "tasks": items,
    }


@router.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task_endpoint(
    payload: TaskCreate,
    current_user: dict = Depends(get_current_user),
):
    """S6-06: Tạo và giao công việc."""
    return create_task_record(payload.model_dump(), current_user)


@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task_endpoint(
    task_id: int,
    current_user: dict = Depends(get_current_user),
):
    """S6-06: Xem chi tiết công việc."""
    from app.services.activity_service import check_task_permission
    task = get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy công việc")
    if not check_task_permission(task, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền xem công việc này")
    return task


@router.put("/tasks/{task_id}", response_model=TaskResponse)
def update_task_endpoint(
    task_id: int,
    payload: TaskUpdate,
    current_user: dict = Depends(get_current_user),
):
    """S6-06: Cập nhật thông tin công việc."""
    return update_task_record(task_id, payload.model_dump(exclude_unset=True), current_user)


@router.post("/tasks/{task_id}/complete", response_model=TaskResponse)
def complete_task_endpoint(
    task_id: int,
    payload: Optional[TaskCompleteRequest] = None,
    current_user: dict = Depends(get_current_user),
):
    """S6-06: Đánh dấu công việc hoàn thành."""
    note = payload.note if payload else None
    return complete_task_record(task_id, current_user, note=note)


@router.post("/tasks/{task_id}/postpone", response_model=TaskResponse)
def postpone_task_endpoint(
    task_id: int,
    payload: TaskPostponeRequest,
    current_user: dict = Depends(get_current_user),
):
    """S6-06: Hoãn công việc kèm lý do bắt buộc."""
    return postpone_task_record(task_id, payload.new_due_date, payload.reason, current_user)


# S6-07: Lịch làm việc cá nhân và nhóm (Calendar)
@router.get("/calendar", response_model=CalendarResponse)
def get_calendar_endpoint(
    view_type: Optional[str] = Query("DAY", description="Loại lịch: DAY, WEEK, MONTH"),
    date: Optional[str] = Query(None, description="Ngày mốc (YYYY-MM-DD), mặc định hôm nay"),
    user_id: Optional[int] = Query(None, description="Lọc theo nhân viên"),
    team_id: Optional[int] = Query(None, description="Lọc theo nhóm (chỉ Trưởng nhóm/Admin)"),
    current_user: dict = Depends(get_current_user),
):
    """
    S6-07: Lịch làm việc cá nhân và nhóm:
    - Trả về cuộc gặp đã hẹn và công việc có hạn trong khoảng thời gian.
    - Hỗ trợ kiểm tra chồng lấn thời gian (conflicts_count và has_conflict).
    - Phân quyền: Nhân viên xem lịch của mình; Trưởng nhóm xem lịch thành viên nhóm.
    """
    return get_calendar_events(
        view_type=view_type or "DAY",
        target_date=date,
        user_id=user_id,
        team_id=team_id,
        current_user=current_user,
    )


# S6-08: Dòng thời gian tương tác khách hàng (Timeline)
@router.get("/timeline/{customer_id}", response_model=TimelineResponse)
def get_customer_timeline_endpoint(
    customer_id: int,
    event_type: Optional[str] = Query(None, description="Lọc loại sự kiện: CALL, MEETING, EMAIL, NOTE, STAGE, QUOTE"),
    performer_id: Optional[int] = Query(None, description="Lọc theo người thực hiện"),
    page: Optional[int] = Query(1, ge=1, description="Trang hiện tại"),
    limit: Optional[int] = Query(20, ge=1, le=100, description="Số lượng mỗi trang"),
    current_user: dict = Depends(get_current_user),
):
    """
    S6-08: Dòng thời gian tương tác khách hàng:
    - Gộp hoạt động, thay đổi cơ hội và báo giá đã gửi.
    - Sắp xếp mới nhất trước.
    - Hỗ trợ lọc theo loại sự kiện và người thực hiện.
    """
    import math
    eff_page = page or 1
    eff_limit = limit or 20
    skip = (eff_page - 1) * eff_limit

    items, total = get_customer_timeline(
        customer_id=customer_id,
        current_user=current_user,
        event_type_filter=event_type,
        performer_id=performer_id,
        skip=skip,
        limit=eff_limit,
    )
    total_pages = max(1, math.ceil(total / eff_limit)) if total > 0 else 1

    return {
        "customer_id": customer_id,
        "total": total,
        "page": eff_page,
        "limit": eff_limit,
        "total_pages": total_pages,
        "items": items,
    }


# S6-09: Nhắc việc sắp đến hạn và quá hạn (Notifications & Reminders)
@router.post("/reminders/scan")
def trigger_reminder_scan(
    threshold_hours: int = Query(24, ge=1, le=72, description="Khoảng thời gian quét trước hạn (giờ)"),
    current_user: dict = Depends(require_roles(["ADMIN", "MANAGER"])),
):
    """S6-09: Tác vụ quét nền nhắc việc sắp đến hạn và quá hạn."""
    return scan_task_reminders(threshold_hours=threshold_hours)


@router.get("/notifications", response_model=NotificationListResponse)
def get_notifications_endpoint(
    current_user: dict = Depends(get_current_user),
):
    """S6-09: Lấy danh sách thông báo in-app của người dùng hiện tại."""
    items, unread = list_user_notifications(current_user["id"])
    return {
        "total": len(items),
        "unread_count": unread,
        "notifications": items,
    }


@router.post("/notifications/{notification_id}/read")
def mark_read_notification(
    notification_id: int,
    current_user: dict = Depends(get_current_user),
):
    """S6-09: Đánh dấu thông báo đã đọc."""
    success = mark_notification_as_read(notification_id, current_user["id"])
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy thông báo")
    return {"message": "Đã đánh dấu thông báo là đã đọc"}


@router.get("/tasks/overdue/summary", response_model=OverdueSummaryResponse)
def get_overdue_tasks_summary_endpoint(
    current_user: dict = Depends(require_roles(["ADMIN", "MANAGER"], detail="Chỉ Trưởng nhóm kinh doanh hoặc Quản trị viên mới được xem báo cáo tổng hợp công việc quá hạn")),
):
    """
    S6-09: Tổng hợp số lượng công việc quá hạn của từng thành viên để trưởng nhóm xem:
    - Chỉ tính công việc chưa hoàn thành và đã quá hạn.
    - Không tính công việc đã hoàn thành.
    """
    return get_overdue_tasks_summary_for_manager(current_user)


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

    updated = update_activity_record(activity_id, payload.model_dump(exclude_unset=True), current_user=current_user)
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

