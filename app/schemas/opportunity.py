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


class OpportunityResponse(BaseModel):
    id: int
    title: str
    value: float
    stage: str
    customer_id: Optional[int] = None
    owner_id: int
    team_id: Optional[int] = None


class OpportunityListResponse(BaseModel):
    scope: str
    total: int
    opportunities: List[OpportunityResponse]
