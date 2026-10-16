from datetime import date
from typing import Optional, List, Any
from pydantic import BaseModel, ConfigDict, Field, field_validator


class OpportunityCreate(BaseModel):
    title: str = Field(..., min_length=1, description="Tên cơ hội bán hàng")
    value: float = Field(default=0.0, ge=0, description="Giá trị dự kiến")
    stage: str = Field(default="PROSPECTING", description="Giai đoạn bán hàng")
    customer_id: Optional[int] = Field(default=None, description="Mã khách hàng")
    contact_person: Optional[str] = Field(default=None, description="Người liên hệ chính")
    contact_id: Optional[int] = Field(default=None, description="Mã người liên hệ")
    source: Optional[str] = Field(default=None, description="Nguồn cơ hội")
    expected_close_date: Optional[date] = Field(default=None, description="Ngày dự kiến chốt")
    win_probability: Optional[float] = Field(default=None, ge=0, le=100, description="Xác suất thắng (%)")
    probability_notes: Optional[str] = Field(default=None, description="Ghi chú khi sửa tay xác suất thắng")
    campaign_id: Optional[int] = None
    lead_id: Optional[int] = None
    team_id: Optional[int] = None
    description: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class OpportunityUpdate(BaseModel):
    title: Optional[str] = None
    value: Optional[float] = Field(default=None, ge=0)
    stage: Optional[str] = None
    customer_id: Optional[int] = None
    contact_person: Optional[str] = None
    contact_id: Optional[int] = None
    source: Optional[str] = None
    expected_close_date: Optional[date] = None
    win_probability: Optional[float] = Field(default=None, ge=0, le=100)
    probability_notes: Optional[str] = None
    campaign_id: Optional[int] = None
    lead_id: Optional[int] = None
    team_id: Optional[int] = None
    description: Optional[str] = None
    override: Optional[bool] = False
    override_reason: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class OpportunityProductCreate(BaseModel):
    product_id: int
    quantity: float = 1.0
    unit_price: Optional[float] = None  # Mặc định lấy từ bảng giá (list_price)
    discount_percent: Optional[float] = 0.0
    billing_cycle: Optional[str] = None  # MONTHLY, QUARTERLY, ANNUALLY (cho dịch vụ thuê bao)
    number_of_cycles: Optional[int] = None  # Số kỳ (cho dịch vụ thuê bao)


class OpportunityProductUpdate(BaseModel):
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    discount_percent: Optional[float] = None
    billing_cycle: Optional[str] = None
    number_of_cycles: Optional[int] = None


class OpportunityProductResponse(BaseModel):
    id: int
    opportunity_id: int
    product_id: int
    product_code: str
    product_name: str
    product_type: str  # ONE_TIME, SUBSCRIPTION
    quantity: float
    unit_price: float
    floor_price: float
    discount_percent: float = 0.0
    billing_cycle: Optional[str] = None
    number_of_cycles: Optional[int] = None
    term_months: Optional[int] = None
    arr: Optional[float] = None
    mrr: Optional[float] = None
    amount: float


class OpportunityResponse(BaseModel):
    id: int
    title: str
    value: float
    stage: str
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    contact_person: Optional[str] = None
    contact_id: Optional[int] = None
    source: Optional[str] = None
    win_probability: Optional[float] = None
    probability_notes: Optional[str] = None
    description: Optional[str] = None
    campaign_id: Optional[int] = None
    lead_id: Optional[int] = None
    owner_id: int
    owner_name: Optional[str] = None
    team_id: Optional[int] = None
    team_name: Optional[str] = None
    arr: Optional[float] = 0.0
    has_products: Optional[bool] = False
    products: Optional[List[OpportunityProductResponse]] = []
    stage_overridden: Optional[bool] = False
    override_reason: Optional[str] = None
    override_by: Optional[int] = None
    status: Optional[str] = "OPEN"
    expected_close_date: Optional[Any] = None
    # S5-07 & S5-02: cờ cảnh báo đình trệ / quá hạn trên thẻ Kanban
    is_flagged: Optional[bool] = False
    is_stagnant: Optional[bool] = False
    is_overdue: Optional[bool] = False
    flag_reasons: Optional[List[str]] = []
    stagnant_warning: Optional[str] = None
    days_inactive: Optional[int] = None
    stagnant_threshold_days: Optional[int] = None
    days_overdue: Optional[int] = None
    flagged_at: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class OpportunityStageMoveRequest(BaseModel):
    new_stage: str
    probability: Optional[float] = None
    probability_notes: Optional[str] = None


class KanbanColumnResponse(BaseModel):
    stage_id: int
    stage_code: str
    stage_name: str
    order_index: int
    default_win_probability: float
    count: int
    total_value: float
    opportunities: List[OpportunityResponse]


class KanbanBoardResponse(BaseModel):
    scope: str
    total_opportunities: int
    total_pipeline_value: float
    columns: List[KanbanColumnResponse]


class OpportunityListResponse(BaseModel):
    scope: str
    total: int
    opportunities: List[OpportunityResponse]
    page: Optional[int] = 1
    limit: Optional[int] = 20
    skip: Optional[int] = 0
    total_pages: Optional[int] = 1


class FlaggedOpportunityListResponse(BaseModel):
    scope: str
    total: int
    opportunities: List[OpportunityResponse]
    page: Optional[int] = 1
    limit: Optional[int] = 20
    skip: Optional[int] = 0
    total_pages: Optional[int] = 1


class OpportunityScanResponse(BaseModel):
    scanned: int
    flagged: int
    stagnant: int
    overdue: int
    scan_date: str


class OpportunityReassignRequest(BaseModel):
    opportunity_ids: List[int]
    new_owner_id: int
    reason: str


class OpportunityReassignResponse(BaseModel):
    success: bool
    reassigned_count: int
    reassigned_opportunity_ids: List[int]
    new_owner_id: int
    new_owner_name: str
    reason: str
    message: str


# ============================================================================
# SPRINT 6 SCHEMAS
# ============================================================================

# S6-01: Opportunity Change History
class OpportunityHistoryItem(BaseModel):
    id: int
    opportunity_id: int
    field_name: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    performed_by: int
    performer_name: Optional[str] = None
    created_at: Optional[Any] = None

    model_config = ConfigDict(extra="allow")


class OpportunityHistoryListResponse(BaseModel):
    total: int
    page: int = 1
    limit: int = 20
    total_pages: int = 1
    items: List[OpportunityHistoryItem]


# S6-02: Saved Filters & Multi-criteria Search
class OpportunitySavedFilterCreate(BaseModel):
    name: str = Field(..., min_length=1, description="Tên bộ lọc")
    filter_criteria: dict = Field(..., description="Tiêu chí lọc")


class OpportunitySavedFilterUpdate(BaseModel):
    name: Optional[str] = None
    filter_criteria: Optional[dict] = None


class OpportunitySavedFilterResponse(BaseModel):
    id: int
    user_id: int
    name: str
    filter_criteria: dict
    created_at: Optional[Any] = None
    updated_at: Optional[Any] = None

    model_config = ConfigDict(extra="allow")


# S6-03: Opportunity Shares
class OpportunityShareCreate(BaseModel):
    user_id: int = Field(..., description="Mã người dùng được chia sẻ")
    permission: Optional[str] = Field(default="READ_WRITE", description="Quyền: READ hoặc READ_WRITE")


class OpportunityShareResponse(BaseModel):
    id: int
    opportunity_id: int
    user_id: int
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    permission: str
    shared_by: int
    shared_by_name: Optional[str] = None
    created_at: Optional[Any] = None

    model_config = ConfigDict(extra="allow")


class OpportunityTransferOwnershipRequest(BaseModel):
    new_owner_id: int = Field(..., description="ID người sở hữu mới")
    reason: Optional[str] = Field(default="Chuyển quyền sở hữu cơ hội", description="Lý do chuyển quyền")


# S6-04: Opportunity Attachments
class OpportunityAttachmentResponse(BaseModel):
    id: int
    opportunity_id: int
    filename: str
    original_name: str
    file_size_bytes: int
    content_type: Optional[str] = None
    uploaded_by: int
    uploader_name: Optional[str] = None
    created_at: Optional[Any] = None
    download_url: Optional[str] = None

    model_config = ConfigDict(extra="allow")



