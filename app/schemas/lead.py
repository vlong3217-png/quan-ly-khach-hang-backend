"""
Schemas for Lead management - S4-07 Lead Response
"""
from datetime import datetime
from enum import Enum
from typing import Annotated, Optional
from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class LeadStatus(str, Enum):
    UNASSIGNED = "UNASSIGNED"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    CONVERTED = "CONVERTED"
    DISQUALIFIED = "DISQUALIFIED"


class LeadRejectSchema(BaseModel):
    """Schema cho thao tác từ chối nhận lead (bắt buộc nhập lý do)."""
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] = Field(
        ..., description="Lý do từ chối nhận lead (bắt buộc)"
    )


class LeadBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Họ và tên hoặc tên Lead")
    title: Optional[str] = Field(None, max_length=255, description="Chức danh")
    company: Optional[str] = Field(None, max_length=255, description="Tên công ty")
    email: Optional[str] = Field(None, max_length=255, description="Email")
    phone: Optional[str] = Field(None, max_length=50, description="Số điện thoại")
    source: Optional[str] = Field(None, max_length=100, description="Nguồn lead")
    status: Optional[str] = Field(default=LeadStatus.UNASSIGNED.value, description="Trạng thái lead")
    assigned_to: Optional[int] = Field(default=None, description="ID nhân viên phụ trách")
    notes: Optional[str] = Field(default=None, description="Ghi chú thêm")
    rejection_reason: Optional[str] = Field(default=None, description="Lý do từ chối tiếp nhận")
    is_overdue_sla: Optional[bool] = Field(default=False, description="Cờ đánh dấu vi phạm SLA phản hồi")
    sla_deadline: Optional[datetime] = Field(default=None, description="Thời hạn SLA phản hồi")


class LeadCreate(LeadBase):
    pass


class LeadUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    title: Optional[str] = None
    company: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = None
    assigned_to: Optional[int] = None
    notes: Optional[str] = None
    rejection_reason: Optional[str] = None
    is_overdue_sla: Optional[bool] = None
    sla_deadline: Optional[datetime] = None


class LeadResponse(LeadBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
