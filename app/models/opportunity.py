"""Opportunity Models for SQLAlchemy and compatibility."""
from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, Date
from sqlalchemy.sql import func
from app.models.user import Base


class OpportunityModel(Base):
    __tablename__ = "opportunities"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    value = Column(Float, default=0.0)
    stage = Column(String(50), default="PROSPECTING")
    customer_id = Column(Integer, nullable=True, index=True)
    campaign_id = Column(Integer, nullable=True, index=True)
    lead_id = Column(Integer, nullable=True, index=True)
    owner_id = Column(Integer, nullable=False, default=1, index=True)
    team_id = Column(Integer, nullable=True, index=True)
    arr = Column(Float, default=0.0)
    status = Column(String(50), default="OPEN")
    expected_close_date = Column(Date, nullable=True)
    
    # Exit criteria & override
    stage_overridden = Column(Boolean, default=False)
    override_reason = Column(Text, nullable=True)
    override_by = Column(Integer, nullable=True)
    
    # S5-07 Stagnant flags
    is_flagged = Column(Boolean, default=False)
    is_stagnant = Column(Boolean, default=False)
    is_overdue = Column(Boolean, default=False)
    flagged_at = Column(DateTime, nullable=True)
    last_activity_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class OpportunityProductModel(Base):
    __tablename__ = "opportunity_products"

    id = Column(Integer, primary_key=True, index=True)
    opportunity_id = Column(Integer, nullable=False, index=True)
    product_id = Column(Integer, nullable=False, index=True)
    product_code = Column(String(100), nullable=False)
    product_name = Column(String(255), nullable=False)
    product_type = Column(String(50), default="ONE_TIME")  # ONE_TIME, SUBSCRIPTION
    quantity = Column(Float, default=1.0)
    unit_price = Column(Float, default=0.0)
    floor_price = Column(Float, default=0.0)
    discount_percent = Column(Float, default=0.0)
    billing_cycle = Column(String(50), nullable=True)
    number_of_cycles = Column(Integer, nullable=True)
    term_months = Column(Integer, nullable=True)
    arr = Column(Float, nullable=True)
    mrr = Column(Float, nullable=True)
    amount = Column(Float, default=0.0)
    created_at = Column(DateTime, server_default=func.now())


# Legacy Pydantic models for backward compatibility if imported elsewhere
class Opportunity(BaseModel):
    id: int
    title: str
    value: float
    stage: str
    customer_id: Optional[int] = None
    owner_id: int
    team_id: Optional[int] = None
    arr: Optional[float] = 0.0


class OpportunityProduct(BaseModel):
    id: int
    opportunity_id: int
    product_id: int
    product_code: str
    product_name: str
    product_type: str
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
