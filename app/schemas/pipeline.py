from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class PipelineStageBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=50, description="Mã giai đoạn (duy nhất)")
    name: str = Field(..., min_length=1, max_length=100, description="Tên hiển thị của giai đoạn")
    win_probability: float = Field(..., ge=0, le=100, description="Xác suất thành công tương ứng (%) từ 0 đến 100")
    order_index: int = Field(default=0, description="Thứ tự xuất hiện trên quy trình bán hàng")
    required_exit_fields: List[str] = Field(
        default_factory=list,
        description="Danh sách các trường thông tin bắt buộc phải hoàn thành trước khi chuyển sang giai đoạn tiếp theo (exit criteria)",
    )
    is_won_stage: bool = Field(default=False, description="Đánh dấu giai đoạn Chốt thắng (Won)")
    is_lost_stage: bool = Field(default=False, description="Đánh dấu giai đoạn Đóng thất bại (Lost)")
    description: Optional[str] = Field(None, max_length=500)


class PipelineStageCreate(PipelineStageBase):
    pass


class PipelineStageUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    win_probability: Optional[float] = Field(None, ge=0, le=100)
    order_index: Optional[int] = None
    required_exit_fields: Optional[List[str]] = None
    description: Optional[str] = None


class PipelineStageResponse(BaseModel):
    id: int
    code: str
    name: str
    win_probability: float
    order_index: int
    required_exit_fields: List[str]
    is_won_stage: bool
    is_lost_stage: bool
    description: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class StageTransitionCheckRequest(BaseModel):
    from_stage_id: int
    to_stage_id: int
    opportunity_data: dict = Field(..., description="Dữ liệu hiện tại của cơ hội bán hàng")


class StageTransitionCheckResponse(BaseModel):
    can_transition: bool
    missing_fields: List[str] = []
    message: str
