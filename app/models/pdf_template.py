"""PDF Template Model for SQLAlchemy & Pydantic compatibility (S7-05)."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from sqlalchemy.sql import func
from app.models.user import Base


class PDFTemplateModel(Base):
    __tablename__ = "pdf_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    template_type = Column(String(50), nullable=False, default="QUOTE")  # QUOTE, CONTRACT
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    # AC 1 & AC 2: Company branding & information
    company_name = Column(String(255), nullable=True)
    company_tax_code = Column(String(50), nullable=True)
    company_address = Column(Text, nullable=True)
    company_phone = Column(String(50), nullable=True)
    company_email = Column(String(100), nullable=True)
    company_website = Column(String(100), nullable=True)
    company_bank_info = Column(Text, nullable=True)
    logo_url = Column(String(500), nullable=True)

    # Styling & Visual Design
    primary_color = Column(String(20), default="#1E40AF")
    secondary_color = Column(String(20), default="#F3F4F6")

    # Document text & terms
    header_title = Column(String(255), nullable=True)
    terms_and_conditions = Column(Text, nullable=True)
    footer_text = Column(Text, nullable=True)
    signature_customer_label = Column(String(100), default="ĐẠI DIỆN KHÁCH HÀNG")
    signature_company_label = Column(String(100), default="ĐẠI DIỆN CÔNG TY")

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class PDFTemplate(BaseModel):
    id: int
    name: str
    template_type: str
    is_default: bool
    company_name: Optional[str] = None
    primary_color: str = "#1E40AF"
