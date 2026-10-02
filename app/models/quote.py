"""Quote Model"""
from typing import Optional
from pydantic import BaseModel


class Quote(BaseModel):
    id: int
    title: str
    amount: float
    status: str
    customer_id: Optional[int] = None
    owner_id: int
    team_id: Optional[int] = None
