from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.sql import func
from app.models.user import Base


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    tax_code = Column(String(50), nullable=True, index=True)
    industry = Column(String(100), nullable=True)
    company_size = Column(String(100), nullable=True)
    website = Column(String(255), nullable=True)
    address = Column(String(500), nullable=True)
    status = Column(String(50), default="PROSPECT")
    parent_company_id = Column(Integer, nullable=True)
    
    # Legacy / Compatibility fields
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    company = Column(String(255), nullable=True)
    
    owner_id = Column(Integer, nullable=False, default=1)  # User who owns this customer
    team_id = Column(Integer, nullable=True)               # Team this customer belongs to
    created_at = Column(DateTime, server_default=func.now())


class CustomerMergeHistory(Base):
    __tablename__ = "customer_merge_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    primary_customer_id = Column(Integer, nullable=False, index=True)
    secondary_customer_id = Column(Integer, nullable=False, index=True)
    secondary_customer_name = Column(String(255), nullable=True)
    secondary_snapshot = Column(Text, nullable=True)  # JSON string lưu thông tin của secondary trước khi gộp
    merged_by = Column(String(100), nullable=True)
    merged_at = Column(DateTime, server_default=func.now())

