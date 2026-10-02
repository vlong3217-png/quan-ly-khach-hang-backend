"""Customer schemas for request and response validation."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class CustomerBase(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None


class CustomerCreate(CustomerBase):
    team_id: Optional[int] = None


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None


class CustomerResponse(CustomerBase):
    id: int
    owner_id: int
    team_id: Optional[int] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CustomerListResponse(BaseModel):
    scope: str
    total: int
    customers: List[CustomerResponse]
