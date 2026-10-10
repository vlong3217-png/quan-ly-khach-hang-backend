"""Opportunity Model"""
from typing import Optional
from pydantic import BaseModel


class Opportunity(BaseModel):
    id: int
    title: str
    value: float
    stage: str
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    contact_person: Optional[str] = None
    contact_id: Optional[int] = None
    source: Optional[str] = None
    expected_close_date: Optional[str] = None
    win_probability: Optional[float] = None
    probability_notes: Optional[str] = None
    stagnant_warning: Optional[str] = None
    description: Optional[str] = None
    owner_id: int
    team_id: Optional[int] = None
    arr: Optional[float] = 0.0


class OpportunityProduct(BaseModel):
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

