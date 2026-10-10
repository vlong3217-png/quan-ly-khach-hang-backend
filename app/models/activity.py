"""Activity Model"""
from typing import Optional
from pydantic import BaseModel


class Activity(BaseModel):
    id: int
    title: str
    type: str
    description: Optional[str] = ""
    customer_id: Optional[int] = None
    lead_id: Optional[int] = None
    opportunity_id: Optional[int] = None
    owner_id: int
    team_id: Optional[int] = None
