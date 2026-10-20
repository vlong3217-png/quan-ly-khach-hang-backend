"""Quote Models for SQLAlchemy and Pydantic compatibility."""
import json
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean
from sqlalchemy.sql import func
from app.models.user import Base


class QuoteModel(Base):
    __tablename__ = "quotes"

    id = Column(Integer, primary_key=True, index=True)
    quote_number = Column(String(100), unique=True, index=True, nullable=False)
    opportunity_id = Column(Integer, index=True, nullable=True)
    opportunity_title = Column(String(255), nullable=True)
    title = Column(String(255), nullable=False)
    amount = Column(Float, default=0.0)
    status = Column(String(50), default="DRAFT")
    is_draft = Column(Boolean, default=True)
    customer_id = Column(Integer, index=True, nullable=True)
    customer_name = Column(String(255), nullable=True)
    owner_id = Column(Integer, index=True, nullable=False, default=1)
    team_id = Column(Integer, index=True, nullable=True)

    # Financial details
    subtotal = Column(Float, default=0.0)
    total_line_discount = Column(Float, default=0.0)
    overall_discount_type = Column(String(20), default="PERCENT")
    overall_discount_value = Column(Float, default=0.0)
    overall_discount_amount = Column(Float, default=0.0)
    total_discount_amount = Column(Float, default=0.0)
    discount_percentage = Column(Float, default=0.0)
    vat_amount = Column(Float, default=0.0)
    grand_total = Column(Float, default=0.0)

    # Dates & Terms
    valid_until = Column(String(50), nullable=True)
    payment_terms = Column(Text, nullable=True)
    delivery_terms = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    # Approval flags
    requires_discount_approval = Column(Boolean, default=False)
    approval_level = Column(String(50), default="NONE")
    approval_reason = Column(Text, nullable=True)
    discount_approval_status = Column(String(50), default="NONE")

    # Contract link
    contract_id = Column(Integer, nullable=True)
    contract_number = Column(String(100), nullable=True)
    is_converted_to_contract = Column(Boolean, default=False)

    # Raw serialized items and approval_history
    raw_data_json = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class Quote(BaseModel):
    id: int
    title: str
    amount: float
    status: str
    customer_id: Optional[int] = None
    owner_id: int
    team_id: Optional[int] = None
