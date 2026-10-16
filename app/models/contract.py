"""Contract Models for SQLAlchemy and Pydantic compatibility (S7-04)."""
from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Date
from sqlalchemy.sql import func
from app.models.user import Base


class ContractModel(Base):
    __tablename__ = "contracts"

    id = Column(Integer, primary_key=True, index=True)
    contract_number = Column(String(100), unique=True, index=True, nullable=False)
    title = Column(String(255), nullable=False)
    quote_id = Column(Integer, index=True, nullable=False)
    quote_number = Column(String(100), nullable=True)
    customer_id = Column(Integer, index=True, nullable=False)
    customer_name = Column(String(255), nullable=True)
    opportunity_id = Column(Integer, index=True, nullable=True)
    opportunity_title = Column(String(255), nullable=True)
    owner_id = Column(Integer, index=True, nullable=False, default=1)
    team_id = Column(Integer, index=True, nullable=True)
    status = Column(String(50), default="ACTIVE")  # DRAFT, ACTIVE, EXPIRED, TERMINATED
    
    # Legal terms & dates (S7-04 AC 2)
    signed_date = Column(Date, nullable=False)
    effective_date = Column(Date, nullable=False)
    expiration_date = Column(Date, nullable=False)
    payment_terms = Column(Text, nullable=True)
    delivery_terms = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    # Financial details inherited from Quote (S7-04 AC 1)
    subtotal = Column(Float, default=0.0)
    total_line_discount = Column(Float, default=0.0)
    overall_discount_type = Column(String(20), default="PERCENT")
    overall_discount_value = Column(Float, default=0.0)
    overall_discount_amount = Column(Float, default=0.0)
    total_discount_amount = Column(Float, default=0.0)
    discount_percentage = Column(Float, default=0.0)
    vat_amount = Column(Float, default=0.0)
    grand_total = Column(Float, default=0.0)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class ContractItemModel(Base):
    __tablename__ = "contract_items"

    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, nullable=False, index=True)
    product_id = Column(Integer, nullable=True, index=True)
    product_code = Column(String(100), nullable=False)
    product_name = Column(String(255), nullable=False)
    unit = Column(String(50), default="Gói")
    quantity = Column(Integer, default=1)
    unit_price = Column(Float, default=0.0)
    floor_price = Column(Float, nullable=True)
    discount_type = Column(String(20), default="PERCENT")
    discount_value = Column(Float, default=0.0)
    line_discount_amount = Column(Float, default=0.0)
    vat_rate = Column(Integer, default=10)
    line_vat_amount = Column(Float, default=0.0)
    line_total = Column(Float, default=0.0)
    notes = Column(Text, nullable=True)


class Contract(BaseModel):
    id: int
    contract_number: str
    title: str
    quote_id: int
    customer_id: int
    owner_id: int
    grand_total: float
    status: str
