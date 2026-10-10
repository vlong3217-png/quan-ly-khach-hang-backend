"""Activity Schemas."""
from typing import Optional, List
from pydantic import BaseModel


class ActivityCreate(BaseModel):
    title: str
    type: str = "CALL"
    description: Optional[str] = ""
    customer_id: Optional[int] = None
    lead_id: Optional[int] = None
    opportunity_id: Optional[int] = None
    team_id: Optional[int] = None
    opportunity_id: Optional[int] = None


class ActivityUpdate(BaseModel):
    title: Optional[str] = None
    type: Optional[str] = None
    description: Optional[str] = None
    customer_id: Optional[int] = None
    lead_id: Optional[int] = None
    opportunity_id: Optional[int] = None


class ActivityResponse(BaseModel):
    id: int
    title: str
    type: str
    description: Optional[str] = ""
    customer_id: Optional[int] = None
    lead_id: Optional[int] = None
    opportunity_id: Optional[int] = None
    owner_id: int
    team_id: Optional[int] = None
    opportunity_id: Optional[int] = None
    created_at: Optional[str] = None


class ActivityListResponse(BaseModel):
    scope: str
    total: int
    activities: List[ActivityResponse]
    page: Optional[int] = 1
    limit: Optional[int] = 20
    skip: Optional[int] = 0
    total_pages: Optional[int] = 1
