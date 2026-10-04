from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class OrganizationUnitBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=50, description="Mã phòng ban / đội ngũ")
    name: str = Field(..., min_length=1, max_length=255, description="Tên phòng ban / đội nhóm")
    parent_id: Optional[int] = Field(None, description="ID đơn vị cấp trên (cấu trúc hình cây đa cấp)")
    manager_id: Optional[int] = Field(None, description="ID trưởng nhóm / trưởng phòng")
    territories: List[str] = Field(default_factory=list, description="Khu vực địa lý phụ trách (ví dụ: ['Hà Nội', 'Đà Nẵng'])")
    description: Optional[str] = Field(None, description="Mô tả nhiệm vụ phòng ban")


class OrganizationUnitCreate(OrganizationUnitBase):
    pass


class OrganizationUnitUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    parent_id: Optional[int] = None
    manager_id: Optional[int] = None
    territories: Optional[List[str]] = None
    description: Optional[str] = None


class OrganizationUnitResponse(BaseModel):
    id: int
    code: str
    name: str
    parent_id: Optional[int] = None
    manager_id: Optional[int] = None
    manager_name: Optional[str] = None
    territories: List[str] = []
    description: Optional[str] = None
    level: int = 1
    children: List["OrganizationUnitResponse"] = []
    member_count: int = 0
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class OrganizationMoveRequest(BaseModel):
    target_parent_id: Optional[int] = Field(None, description="ID cấp trên mới, hoặc None nếu đưa lên cấp cao nhất")
