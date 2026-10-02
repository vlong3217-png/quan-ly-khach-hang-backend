"""Opportunity Model"""
from typing import Optional
from pydantic import BaseModel


class Opportunity(BaseModel):
    id: int
    title: str
    value: float
    stage: str
    customer_id: Optional[int] = None
    owner_id: int
    team_id: Optional[int] = None
