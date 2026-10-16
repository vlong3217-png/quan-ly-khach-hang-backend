"""Schemas for In-App Notifications (S7-08 EP-09)."""
from datetime import datetime
from enum import Enum
from typing import Optional, List, Any
from pydantic import BaseModel, ConfigDict, Field


class NotificationType(str, Enum):
    LEAD_ASSIGNED = "LEAD_ASSIGNED"
    QUOTE_WAITING_APPROVAL = "QUOTE_WAITING_APPROVAL"
    QUOTE_CUSTOMER_RESPONSE = "QUOTE_CUSTOMER_RESPONSE"
    TASK_ASSIGNED = "TASK_ASSIGNED"
    OPPORTUNITY_STAGNANT = "OPPORTUNITY_STAGNANT"
    SYSTEM = "SYSTEM"


class NotificationCreate(BaseModel):
    recipient_id: int = Field(..., description="ID người nhận thông báo")
    title: str = Field(..., min_length=1, description="Tiêu đề thông báo")
    message: str = Field(..., min_length=1, description="Nội dung chi tiết thông báo")
    type: str = Field(default=NotificationType.SYSTEM.value, description="Loại thông báo")
    entity_type: Optional[str] = Field(default=None, description="Loại thực thể (LEAD, QUOTE, TASK, OPPORTUNITY, CONTRACT)")
    entity_id: Optional[int] = Field(default=None, description="ID của thực thể liên quan")
    link: Optional[str] = Field(default=None, description="Đường dẫn điều hướng trên frontend")
    sender_id: Optional[int] = Field(default=None, description="ID người gửi hoặc None nếu từ hệ thống")
    sender_name: Optional[str] = Field(default=None, description="Tên người gửi")

    model_config = ConfigDict(extra="allow")


class NotificationResponse(BaseModel):
    id: int
    recipient_id: int
    sender_id: Optional[int] = None
    sender_name: Optional[str] = None
    title: str
    message: str
    type: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    link: Optional[str] = None
    is_read: bool = False
    read_at: Optional[Any] = None
    created_at: Optional[Any] = None
    updated_at: Optional[Any] = None

    model_config = ConfigDict(from_attributes=True, extra="allow")


class NotificationListResponse(BaseModel):
    total: int
    unread_count: int
    page: int
    page_size: int
    total_pages: int
    notifications: List[NotificationResponse]

    model_config = ConfigDict(extra="allow")


class NotificationUnreadCountResponse(BaseModel):
    unread_count: int

    model_config = ConfigDict(extra="allow")


class NotificationBatchReadResponse(BaseModel):
    success: bool = True
    updated_count: int
    unread_count: int

    model_config = ConfigDict(extra="allow")


class NotificationTestTriggerRequest(BaseModel):
    recipient_id: Optional[int] = None
    type: Optional[str] = "SYSTEM"
    title: Optional[str] = "Thông báo thử nghiệm"
    message: Optional[str] = "Nội dung kiểm tra hệ thống thông báo"
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    link: Optional[str] = None

    model_config = ConfigDict(extra="allow")
