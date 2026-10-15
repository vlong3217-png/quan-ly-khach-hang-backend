"""Quote Schemas."""
from datetime import date
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field


class DiscountType(str, Enum):
    PERCENT = "PERCENT"
    AMOUNT = "AMOUNT"


class QuoteItemCreate(BaseModel):
    product_id: Optional[int] = None
    product_code: Optional[str] = None
    product_name: str
    unit: Optional[str] = "Gói"
    quantity: int = Field(default=1, ge=1)
    unit_price: float = Field(default=0.0, ge=0.0)
    floor_price: Optional[float] = None
    discount_type: DiscountType = DiscountType.PERCENT
    discount_value: float = Field(default=0.0, ge=0.0)
    vat_rate: int = Field(default=10, ge=0, le=100)


class QuoteItemResponse(QuoteItemCreate):
    id: str
    line_discount_amount: float = 0.0
    line_total: float = 0.0


class QuoteCreate(BaseModel):
    opportunity_id: Optional[int] = None
    title: Optional[str] = None
    amount: Optional[float] = None
    status: Optional[str] = None
    customer_id: Optional[int] = None
    team_id: Optional[int] = None
    product_id: Optional[int] = None
    unit_price: Optional[float] = None
    items: Optional[List[QuoteItemCreate]] = None
    overall_discount_type: DiscountType = DiscountType.PERCENT
    overall_discount_value: float = Field(default=0.0, ge=0.0)
    valid_until: Optional[date] = None
    payment_terms: Optional[str] = None
    delivery_terms: Optional[str] = None
    notes: Optional[str] = None
    is_draft: bool = True
    requires_discount_approval: Optional[bool] = False
    discount_approval_status: Optional[str] = None


class QuoteUpdate(BaseModel):
    title: Optional[str] = None
    amount: Optional[float] = None
    status: Optional[str] = None
    customer_id: Optional[int] = None
    product_id: Optional[int] = None
    unit_price: Optional[float] = None
    items: Optional[List[QuoteItemCreate]] = None
    overall_discount_type: Optional[DiscountType] = None
    overall_discount_value: Optional[float] = None
    valid_until: Optional[date] = None
    payment_terms: Optional[str] = None
    delivery_terms: Optional[str] = None
    notes: Optional[str] = None
    is_draft: Optional[bool] = None
    requires_discount_approval: Optional[bool] = None
    discount_approval_status: Optional[str] = None


class QuoteResponse(BaseModel):
    id: int
    quote_number: Optional[str] = None
    opportunity_id: Optional[int] = None
    opportunity_title: Optional[str] = None
    title: str
    amount: float
    status: str
    is_draft: bool = False
    customer_id: Optional[int] = None
    owner_id: int
    team_id: Optional[int] = None
    product_id: Optional[int] = None
    unit_price: Optional[float] = None

    # Line items & Financial calculation
    items: List[QuoteItemResponse] = []
    overall_discount_type: DiscountType = DiscountType.PERCENT
    overall_discount_value: float = 0.0
    subtotal: float = 0.0
    total_line_discount: float = 0.0
    overall_discount_amount: float = 0.0
    total_discount_amount: float = 0.0
    discount_percentage: float = 0.0
    vat_amount: float = 0.0
    grand_total: float = 0.0

    # Terms & Validity
    valid_until: Optional[str] = None
    payment_terms: Optional[str] = None
    delivery_terms: Optional[str] = None
    notes: Optional[str] = None

    # Approval (S7-01 & S7-02)
    requires_discount_approval: Optional[bool] = False
    approval_level: Optional[str] = "NONE"
    approval_reason: Optional[str] = None
    discount_approval_status: Optional[str] = None
    approval_history: List["QuoteApprovalHistoryItem"] = []

    # Dispatch / Sending (S7-02 AC 4)
    sent_at: Optional[str] = None

    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class QuoteApprovalAction(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    RETURN = "RETURN"
    SUBMITTED = "SUBMITTED"
    AUTO_APPROVED = "AUTO_APPROVED"
    SEND = "SEND"


class QuoteApprovalRequest(BaseModel):
    comments: Optional[str] = None


class QuoteApprovalActionRequest(BaseModel):
    action: QuoteApprovalAction
    comments: Optional[str] = None


class QuoteApprovalHistoryItem(BaseModel):
    id: str
    action: str
    performed_by_id: Optional[int] = None
    performed_by_name: str
    performed_by_role: str
    comments: Optional[str] = None
    previous_status: Optional[str] = None
    new_status: Optional[str] = None
    timestamp: str


class QuoteApprovalHistoryListResponse(BaseModel):
    quote_id: int
    quote_number: Optional[str] = None
    total: int
    history: List[QuoteApprovalHistoryItem]


class QuoteListResponse(BaseModel):
    scope: str
    total: int
    quotes: List[QuoteResponse]
    page: Optional[int] = 1
    limit: Optional[int] = 20
    skip: Optional[int] = 0
    total_pages: Optional[int] = 1
