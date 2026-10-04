from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class MasterDataType(str, Enum):
    INDUSTRY = "INDUSTRY"              # Ngành nghề
    COMPANY_SIZE = "COMPANY_SIZE"      # Quy mô doanh nghiệp
    LEAD_SOURCE = "LEAD_SOURCE"        # Nguồn lead
    ACTIVITY_TYPE = "ACTIVITY_TYPE"    # Loại hoạt động


class MasterDataBase(BaseModel):
    category: MasterDataType = Field(..., description="Loại danh mục master data")
    code: str = Field(..., min_length=1, max_length=50, description="Mã danh mục (duy nhất trong category)")
    name: str = Field(..., min_length=1, max_length=255, description="Tên danh mục hiển thị")
    sort_order: int = Field(default=0, description="Thứ tự hiển thị tùy chỉnh (từ nhỏ đến lớn)")
    is_active: bool = Field(default=True, description="Trạng thái kích hoạt (Hiển thị / Ẩn)")
    description: Optional[str] = Field(None, max_length=500, description="Mô tả bổ sung")


class MasterDataCreate(MasterDataBase):
    pass


class MasterDataUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None
    description: Optional[str] = None


class MasterDataReorderItem(BaseModel):
    id: int
    sort_order: int


class MasterDataReorderRequest(BaseModel):
    items: List[MasterDataReorderItem]


class MasterDataResponse(BaseModel):
    id: int
    category: MasterDataType
    code: str
    name: str
    sort_order: int
    is_active: bool
    description: Optional[str] = None
    in_use_count: int = 0
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
