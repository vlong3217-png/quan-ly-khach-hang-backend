"""Activity, Task, Calendar, Timeline, and Notification Schemas for Sprint 6."""
from datetime import datetime
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, ConfigDict, Field


# S6-05: Activity Schemas
class ActivityCreate(BaseModel):
    title: str = Field(..., min_length=1, description="Tiêu đề hoạt động")
    type: str = Field(default="CALL", description="Loại hoạt động: CALL, MEETING, EMAIL, NOTE")
    description: Optional[str] = ""
    result: Optional[str] = None
    duration_minutes: Optional[int] = 0
    occurred_at: Optional[datetime] = None  # Cho phép ghi nhận hoạt động trong quá khứ
    customer_id: Optional[int] = None
    contact_id: Optional[int] = None
    opportunity_id: Optional[int] = None
    lead_id: Optional[int] = None
    team_id: Optional[int] = None

    model_config = ConfigDict(extra="allow")


class ActivityUpdate(BaseModel):
    title: Optional[str] = None
    type: Optional[str] = None
    description: Optional[str] = None
    result: Optional[str] = None
    duration_minutes: Optional[int] = None
    occurred_at: Optional[datetime] = None
    customer_id: Optional[int] = None
    contact_id: Optional[int] = None
    opportunity_id: Optional[int] = None
    lead_id: Optional[int] = None

    model_config = ConfigDict(extra="allow")


class ActivityResponse(BaseModel):
    id: int
    title: str
    type: str
    description: Optional[str] = ""
    result: Optional[str] = None
    duration_minutes: Optional[int] = 0
    occurred_at: Optional[Any] = None
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    contact_id: Optional[int] = None
    contact_name: Optional[str] = None
    opportunity_id: Optional[int] = None
    opportunity_title: Optional[str] = None
    lead_id: Optional[int] = None
    owner_id: int
    owner_name: Optional[str] = None
    team_id: Optional[int] = None
    created_at: Optional[Any] = None

    model_config = ConfigDict(extra="allow")


class ActivityListResponse(BaseModel):
    scope: str
    total: int
    activities: List[ActivityResponse]
    page: Optional[int] = 1
    limit: Optional[int] = 20
    skip: Optional[int] = 0
    total_pages: Optional[int] = 1


# S6-06: Task Tracking Schemas
class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, description="Tiêu đề công việc")
    description: Optional[str] = None
    due_date: datetime = Field(..., description="Hạn hoàn thành (ISO format)")
    priority: Optional[str] = Field(default="MEDIUM", description="Mức ưu tiên: LOW, MEDIUM, HIGH, URGENT")
    assignee_id: Optional[int] = Field(default=None, description="Người được giao việc (mặc định người tạo)")
    customer_id: Optional[int] = None
    opportunity_id: Optional[int] = None
    contact_id: Optional[int] = None

    model_config = ConfigDict(extra="allow")


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: Optional[str] = None
    assignee_id: Optional[int] = None
    customer_id: Optional[int] = None
    opportunity_id: Optional[int] = None
    contact_id: Optional[int] = None

    model_config = ConfigDict(extra="allow")


class TaskPostponeRequest(BaseModel):
    new_due_date: datetime = Field(..., description="Hạn mới sau khi hoãn")
    reason: str = Field(..., min_length=1, description="Lý do hoãn công việc (bắt buộc)")


class TaskCompleteRequest(BaseModel):
    note: Optional[str] = None


class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    due_date: Optional[Any] = None
    priority: str
    status: str
    assignee_id: int
    assignee_name: Optional[str] = None
    creator_id: int
    creator_name: Optional[str] = None
    updater_id: Optional[int] = None
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    opportunity_id: Optional[int] = None
    opportunity_title: Optional[str] = None
    contact_id: Optional[int] = None
    contact_name: Optional[str] = None
    postpone_reason: Optional[str] = None
    completed_at: Optional[Any] = None
    is_overdue: Optional[bool] = False
    created_at: Optional[Any] = None
    updated_at: Optional[Any] = None

    model_config = ConfigDict(extra="allow")


class TaskListResponse(BaseModel):
    total: int
    tasks: List[TaskResponse]
    page: int = 1
    limit: int = 20
    total_pages: int = 1


# S6-07: Calendar Schemas
class CalendarEventItem(BaseModel):
    id: str  # e.g. "activity_1" hoặc "task_2"
    event_type: str  # MEETING, TASK
    title: str
    start_time: Any
    end_time: Optional[Any] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    user_id: int
    user_name: Optional[str] = None
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    opportunity_id: Optional[int] = None
    opportunity_title: Optional[str] = None
    has_conflict: Optional[bool] = False

    model_config = ConfigDict(extra="allow")


class CalendarResponse(BaseModel):
    view_type: str  # DAY, WEEK, MONTH
    from_date: str
    to_date: str
    user_id: Optional[int] = None
    team_id: Optional[int] = None
    total_events: int
    conflicts_count: int = 0
    events: List[CalendarEventItem]


# S6-08: Timeline Schemas
class TimelineItem(BaseModel):
    id: str  # e.g. "activity_1", "opportunity_history_2", "quote_3"
    event_type: str  # ACTIVITY_CALL, ACTIVITY_MEETING, ACTIVITY_EMAIL, ACTIVITY_NOTE, OPPORTUNITY_STAGE_CHANGE, OPPORTUNITY_OWNER_CHANGE, QUOTE_SENT, QUOTE_ACCEPTED, etc.
    title: str
    timestamp: Any
    actor_id: int
    actor_name: Optional[str] = None
    summary: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="allow")


class TimelineResponse(BaseModel):
    customer_id: int
    total: int
    page: int = 1
    limit: int = 20
    total_pages: int = 1
    items: List[TimelineItem]


# S6-09: Notification & Overdue Summary Schemas
class NotificationResponse(BaseModel):
    id: int
    user_id: int
    title: str
    message: str
    type: str
    reference_id: Optional[int] = None
    is_read: bool = False
    created_at: Optional[Any] = None

    model_config = ConfigDict(extra="allow")


class NotificationListResponse(BaseModel):
    total: int
    unread_count: int
    notifications: List[NotificationResponse]


class OverdueMemberSummary(BaseModel):
    user_id: int
    user_name: str
    team_id: Optional[int] = None
    overdue_count: int


class OverdueSummaryResponse(BaseModel):
    total_overdue: int
    members: List[OverdueMemberSummary]


# S6-10: Quick Call Log Schemas
class QuickCallLogRequest(BaseModel):
    customer_id: int = Field(..., description="ID khách hàng")
    result: str = Field(..., min_length=1, description="Kết quả cuộc gọi")
    note: Optional[str] = Field(default="", description="Ghi chú ngắn")
    occurred_at: Optional[datetime] = None  # Thời điểm gọi (mặc định hiện tại)
    opportunity_id: Optional[int] = Field(default=None, description="Tùy chọn: tự gắn nếu bỏ trống")
    schedule_callback: Optional[datetime] = Field(default=None, description="Lịch gọi lại nếu có")
    callback_note: Optional[str] = Field(default="Gọi lại cho khách hàng", description="Tiêu đề/ghi chú cuộc gọi lại")


class QuickCallLogResponse(BaseModel):
    activity: ActivityResponse
    opportunity_auto_linked: bool
    opportunity_id: Optional[int] = None
    opportunity_title: Optional[str] = None
    callback_task: Optional[TaskResponse] = None
    message: str

