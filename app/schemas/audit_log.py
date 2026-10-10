from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, Field


class AuditLogEntry(BaseModel):
    id: int
    user_id: int
    user_name: str
    entity_type: str = Field(..., description="Loại đối tượng: ROLE, DISCOUNT, TARGET, DATA_OWNERSHIP")
    entity_id: Optional[str] = Field(None, description="ID hoặc mã định danh đối tượng bị thay đổi")
    action: str = Field(..., description="Hành động: UPDATE, ASSIGN, TRANSFER, v.v.")
    field_name: str = Field(..., description="Tên trường dữ liệu nhạy cảm bị thay đổi")
    old_value: Optional[Any] = Field(None, description="Giá trị trước khi sửa")
    new_value: Optional[Any] = Field(None, description="Giá trị sau khi sửa")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Thời điểm thực hiện")
    ip_address: Optional[str] = None


class AuditLogFilterParams(BaseModel):
    user_id: Optional[int] = None
    entity_type: Optional[str] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None


class AuditLogListResponse(BaseModel):
    total: int
    items: List[AuditLogEntry]
    page: Optional[int] = 1
    limit: Optional[int] = 50
    skip: Optional[int] = 0
    total_pages: Optional[int] = 1
