from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from app.models.user import Base


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    company_name = Column(String(255), nullable=True)
    title = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(50), nullable=True, index=True)
    address = Column(String(500), nullable=True)
    source = Column(String(100), nullable=False, index=True)  # Bắt buộc có nguồn (S4-02)
    campaign_id = Column(Integer, nullable=True, index=True)   # Liên kết chiến dịch (S4-03)
    customer_id = Column(Integer, nullable=True, index=True)   # Liên kết khách hàng (S4-04)
    status = Column(String(50), default="NEW", index=True)     # NEW, CONTACTED, QUALIFIED, UNQUALIFIED, CONVERTED, MERGED
    notes = Column(Text, nullable=True)
    merged_into_id = Column(Integer, nullable=True)            # ID lead chính nếu đã bị gộp (S4-04)
    owner_id = Column(Integer, nullable=False, default=1)
    team_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())


class LeadMergeHistory(Base):
    __tablename__ = "lead_merge_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    primary_lead_id = Column(Integer, nullable=False, index=True)
    secondary_lead_id = Column(Integer, nullable=False, index=True)
    secondary_lead_name = Column(String(255), nullable=True)
    secondary_snapshot = Column(Text, nullable=True)  # JSON snapshot trước khi gộp
    merged_by = Column(String(100), nullable=True)
    merged_at = Column(DateTime, server_default=func.now())
