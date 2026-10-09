from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ReasonType(str, Enum):
    WIN = "WIN"    # Lý do thắng thầu
    LOSS = "LOSS"  # Lý do thất bại/thua thầu


class ReasonBase(BaseModel):
    reason_type: ReasonType = Field(..., description="Loại: WIN hoặc LOSS")
    code: str = Field(..., min_length=1, max_length=50, description="Mã lý do")
    name: str = Field(..., min_length=1, max_length=255, description="Nội dung lý do")
    requires_competitor: bool = Field(
        default=False,
        description="Có bắt buộc phải chọn đối thủ cạnh tranh khi chọn lý do này không (ví dụ thua vì đối thủ giá rẻ hơn)",
    )
    is_active: bool = Field(default=True, description="Trạng thái kích hoạt")
    sort_order: int = Field(default=0, description="Thứ tự hiển thị")


class ReasonCreate(ReasonBase):
    pass


class ReasonUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    requires_competitor: Optional[bool] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class ReasonResponse(BaseModel):
    id: int
    reason_type: ReasonType
    code: str
    name: str
    requires_competitor: bool
    is_active: bool
    sort_order: int
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CompetitorBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=50, description="Mã định danh đối thủ")
    name: str = Field(..., min_length=1, max_length=255, description="Tên đối thủ cạnh tranh")
    strengths: Optional[str] = Field(None, description="Điểm mạnh của đối thủ")
    weaknesses: Optional[str] = Field(None, description="Điểm yếu của đối thủ")
    pricing_strategy: Optional[str] = Field(None, description="Chiến lược giá (VD: Giá rẻ, Cao cấp, Cạnh tranh)")
    is_active: bool = Field(default=True)


class CompetitorCreate(CompetitorBase):
    pass


class CompetitorUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    strengths: Optional[str] = None
    weaknesses: Optional[str] = None
    pricing_strategy: Optional[str] = None
    is_active: Optional[bool] = None


class CompetitorResponse(BaseModel):
    id: int
    code: str
    name: str
    strengths: Optional[str] = None
    weaknesses: Optional[str] = None
    pricing_strategy: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CloseOpportunityValidationRequest(BaseModel):
    status: str = Field(..., description="Trạng thái đóng: WON hoặc LOST")
    reason_id: int = Field(..., description="ID lý do thắng/thua")
    competitor_id: Optional[int] = Field(None, description="ID đối thủ cạnh tranh (nếu có)")
    note: Optional[str] = Field(None, description="Ghi chú chi tiết khi đóng")


class CloseOpportunityValidationResponse(BaseModel):
    is_valid: bool
    message: str
