"""Quote Schemas."""
from typing import Optional, List
from pydantic import BaseModel


class QuoteCreate(BaseModel):
    title: str
    amount: float
    status: str = "DRAFT"
    customer_id: Optional[int] = None
    team_id: Optional[int] = None
    product_id: Optional[int] = None
    unit_price: Optional[float] = None
    requires_discount_approval: Optional[bool] = False
    discount_approval_status: Optional[str] = None


class QuoteUpdate(BaseModel):
    title: Optional[str] = None
    amount: Optional[float] = None
    status: Optional[str] = None
    customer_id: Optional[int] = None
    product_id: Optional[int] = None
    unit_price: Optional[float] = None
    requires_discount_approval: Optional[bool] = None
    discount_approval_status: Optional[str] = None


class QuoteResponse(BaseModel):
    id: int
    title: str
    amount: float
    status: str
    customer_id: Optional[int] = None
    owner_id: int
    team_id: Optional[int] = None
    product_id: Optional[int] = None
    unit_price: Optional[float] = None
    requires_discount_approval: Optional[bool] = False
    discount_approval_status: Optional[str] = None


class QuoteListResponse(BaseModel):
    scope: str
    total: int
    quotes: List[QuoteResponse]
