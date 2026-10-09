"""Opportunity Schemas."""
from typing import Optional, List
from pydantic import BaseModel


class OpportunityCreate(BaseModel):
    title: str
    value: float
    stage: str = "PROSPECTING"
    customer_id: Optional[int] = None
    team_id: Optional[int] = None


class OpportunityUpdate(BaseModel):
    title: Optional[str] = None
    value: Optional[float] = None
    stage: Optional[str] = None
    customer_id: Optional[int] = None


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
    owner_id: int
    team_id: Optional[int] = None
    arr: Optional[float] = 0.0
    has_products: Optional[bool] = False
    products: Optional[List[OpportunityProductResponse]] = []


class OpportunityListResponse(BaseModel):
    scope: str
    total: int
    opportunities: List[OpportunityResponse]

