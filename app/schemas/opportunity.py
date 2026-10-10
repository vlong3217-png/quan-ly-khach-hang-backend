from datetime import date
from typing import Optional, List, Any
from pydantic import BaseModel, ConfigDict


class OpportunityCreate(BaseModel):
    title: str
    value: float = 0.0
    stage: str = "PROSPECTING"
    customer_id: Optional[int] = None
    campaign_id: Optional[int] = None
    lead_id: Optional[int] = None
    team_id: Optional[int] = None
    expected_close_date: Optional[date] = None


class OpportunityUpdate(BaseModel):
    title: Optional[str] = None
    value: Optional[float] = None
    stage: Optional[str] = None
    customer_id: Optional[int] = None
    campaign_id: Optional[int] = None
    lead_id: Optional[int] = None
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
    campaign_id: Optional[int] = None
    lead_id: Optional[int] = None
    owner_id: int
    team_id: Optional[int] = None
    arr: Optional[float] = 0.0
    has_products: Optional[bool] = False
    products: Optional[List[OpportunityProductResponse]] = []
    stage_overridden: Optional[bool] = False
    override_reason: Optional[str] = None
    override_by: Optional[int] = None
    status: Optional[str] = "OPEN"
    expected_close_date: Optional[Any] = None
    # S5-07: cờ cảnh báo đình trệ / quá hạn
    is_flagged: Optional[bool] = False
    is_stagnant: Optional[bool] = False
    is_overdue: Optional[bool] = False
    flag_reasons: Optional[List[str]] = []
    days_inactive: Optional[int] = None
    stagnant_threshold_days: Optional[int] = None
    days_overdue: Optional[int] = None
    flagged_at: Optional[str] = None
    # S5-05: Thông tin đóng thắng/thua/mở lại
    actual_revenue: Optional[float] = None
    contract_signed_date: Optional[str] = None
    loss_reason: Optional[str] = None
    competitor: Optional[str] = None
    closed_date: Optional[str] = None
    closed_at: Optional[str] = None
    closed_by: Optional[int] = None
    reopened_at: Optional[str] = None
    reopened_by: Optional[int] = None
    reopen_reason: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class OpportunityListResponse(BaseModel):
    scope: str
    total: int
    opportunities: List[OpportunityResponse]


class FlaggedOpportunityListResponse(BaseModel):
    scope: str
    total: int
    opportunities: List[OpportunityResponse]


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
# SCHEMAS S5-05: ĐÓNG THẮNG / ĐÓNG THUA / MỞ LẠI CƠ HỘI
# ============================================================================

class OpportunityCloseWonRequest(BaseModel):
    actual_revenue: float
    contract_signed_date: str  # YYYY-MM-DD
    note: Optional[str] = None


class OpportunityCloseLostRequest(BaseModel):
    loss_reason: str
    competitor: Optional[str] = None
    note: Optional[str] = None


class OpportunityReopenRequest(BaseModel):
    reason: str
    target_stage: Optional[str] = None  # Mặc định mở lại về PROSPECTING hoặc QUALIFICATION



