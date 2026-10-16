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
    contact_person = Column(String(255), nullable=True)
    contact_id = Column(Integer, nullable=True)
    source = Column(String(100), nullable=True)
    win_probability = Column(Float, nullable=True)
    probability_notes = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    
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


class OpportunityHistoryModel(Base):
    __tablename__ = "opportunity_histories"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    opportunity_id = Column(Integer, nullable=False, index=True)
    field_name = Column(String(100), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    performed_by = Column(Integer, nullable=False, index=True)
    performer_name = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class OpportunitySavedFilterModel(Base):
    __tablename__ = "opportunity_saved_filters"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    filter_criteria = Column(Text, nullable=False)  # JSON string
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class OpportunityShareModel(Base):
    __tablename__ = "opportunity_shares"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    opportunity_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    permission = Column(String(50), default="READ_WRITE")  # READ, READ_WRITE
    shared_by = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class OpportunityAttachmentModel(Base):
    __tablename__ = "opportunity_attachments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    opportunity_id = Column(Integer, nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    original_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    content_type = Column(String(100), nullable=True)
    uploaded_by = Column(Integer, nullable=False)
    uploader_name = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=func.now())


# Legacy Pydantic models for backward compatibility if imported elsewhere
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
