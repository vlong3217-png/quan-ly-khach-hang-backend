from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class CampaignChannel(str, Enum):
    EVENT = "EVENT"                     # Hội thảo / Sự kiện
    WORKSHOP = "WORKSHOP"               # Workshop chuyên đề
    FACEBOOK_ADS = "FACEBOOK_ADS"       # Quảng cáo Facebook
    GOOGLE_ADS = "GOOGLE_ADS"           # Quảng cáo Google
    EMAIL_MARKETING = "EMAIL_MARKETING" # Email Marketing
    WEBSITE = "WEBSITE"                 # Website / Inbound
    DIRECT = "DIRECT"                   # Tiếp cận trực tiếp


class CampaignStatus(str, Enum):
    PLANNING = "PLANNING"               # Lên kế hoạch
    ACTIVE = "ACTIVE"                   # Đang diễn ra
    PAUSED = "PAUSED"                   # Tạm dừng
    COMPLETED = "COMPLETED"             # Hoàn thành
    CANCELLED = "CANCELLED"             # Đã hủy


class CampaignBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Tên chiến dịch")
    code: str = Field(..., min_length=1, max_length=100, description="Mã chiến dịch (unique)")
    budget: float = Field(..., ge=0, description="Ngân sách chiến dịch")
    actual_cost: float = Field(default=0.0, ge=0, description="Chi phí thực tế")
    start_date: datetime = Field(..., description="Thời gian bắt đầu")
    end_date: Optional[datetime] = Field(None, description="Thời gian kết thúc")
    channel: str = Field(..., min_length=1, max_length=100, description="Kênh tiếp thị")
    target_leads: int = Field(default=0, ge=0, description="Mục tiêu số lead")
    expected_revenue: float = Field(default=0.0, ge=0, description="Doanh thu kỳ vọng")
    status: str = Field(default="ACTIVE", description="Trạng thái chiến dịch")
    description: Optional[str] = Field(None, description="Mô tả chiến dịch")

    @field_validator("name")
    @classmethod
    def validate_name_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Tên chiến dịch không được để trống")
        return v.strip()

    @field_validator("code")
    @classmethod
    def validate_code_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Mã chiến dịch không được để trống")
        return v.strip().upper()


class CampaignCreate(CampaignBase):
    owner_id: Optional[int] = Field(None, description="Người tạo/phụ trách")
    team_id: Optional[int] = Field(None, description="Nhóm phụ trách")


class CampaignUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    code: Optional[str] = Field(None, min_length=1, max_length=100)
    budget: Optional[float] = Field(None, ge=0)
    actual_cost: Optional[float] = Field(None, ge=0)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    channel: Optional[str] = None
    target_leads: Optional[int] = Field(None, ge=0)
    expected_revenue: Optional[float] = Field(None, ge=0)
    status: Optional[str] = None
    description: Optional[str] = None
    owner_id: Optional[int] = None
    team_id: Optional[int] = None


class CampaignResponse(CampaignBase):
    id: int
    owner_id: int
    owner_name: Optional[str] = None
    team_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CampaignListResponse(BaseModel):
    total: int
    campaigns: List[CampaignResponse]
    page: Optional[int] = 1
    limit: Optional[int] = 20
    skip: Optional[int] = 0
    total_pages: Optional[int] = 1


class CampaignMetricsResponse(BaseModel):
    campaign_id: int
    campaign_name: str
    campaign_code: str
    channel: str
    budget: float
    actual_cost: float
    target_leads: int
    total_leads: int
    total_opportunities: int
    won_opportunities: int
    closed_won_value: float
    conversion_rate_lead_to_opp: float
    conversion_rate_lead_to_won: float
    roi: float


class CampaignSummaryReportResponse(BaseModel):
    total_campaigns: int
    total_budget: float
    total_actual_cost: float
    total_leads: int
    total_opportunities: int
    total_won_opportunities: int
    total_closed_won_value: float
    average_roi: float
    campaign_metrics: List[CampaignMetricsResponse]
