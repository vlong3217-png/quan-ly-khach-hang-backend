from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, EmailStr


class DecisionRole(str, Enum):
    DECISION_MAKER = "DECISION_MAKER"  # Người quyết định
    INFLUENCER = "INFLUENCER"          # Người ảnh hưởng
    END_USER = "END_USER"              # Người dùng cuối
    BLOCKER = "BLOCKER"                # Rào cản / Người phản đối


class ContactHistoryItem(BaseModel):
    action: str
    from_customer_id: Optional[int] = None
    to_customer_id: Optional[int] = None
    note: Optional[str] = None
    performed_by: Optional[str] = None
    timestamp: datetime


class ContactBase(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    position: Optional[str] = None
    decision_role: Optional[DecisionRole] = DecisionRole.INFLUENCER
    is_primary: bool = False
    notes: Optional[str] = None


class ContactCreate(ContactBase):
    customer_id: int


class ContactUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    position: Optional[str] = None
    decision_role: Optional[DecisionRole] = None
    is_primary: Optional[bool] = None
    notes: Optional[str] = None


class ContactTransfer(BaseModel):
    to_customer_id: int
    note: Optional[str] = None


class ContactResponse(ContactBase):
    id: int
    customer_id: int
    history: List[ContactHistoryItem] = []
    created_at: datetime
    updated_at: Optional[datetime] = None
