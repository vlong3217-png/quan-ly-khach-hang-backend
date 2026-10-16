from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, UniqueConstraint
from datetime import datetime
from app.models.user import Base

class SalesQuota(Base):
    __tablename__ = "sales_quotas"

    id = Column(Integer, primary_key=True, index=True)
    quota_type = Column(String(20), nullable=False)  # month | quarter
    period_name = Column(String(20), nullable=False, index=True)  # eg: 2026-10, 2026-Q1
    year = Column(Integer, nullable=False)
    period_number = Column(Integer, nullable=False) # month 1-12, or quarter 1-4

    target_type = Column(String(20), nullable=False)  # user | team
    user_id = Column(Integer, nullable=True, index=True)
    team_id = Column(String(50), nullable=True, index=True)

    target_amount = Column(Float, default=0.0)
    achieved_amount = Column(Float, default=0.0)
    is_locked = Column(Boolean, default=False)
    lock_reason = Column(String(255), nullable=True)
    created_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "quota_type",
            "period_name",
            "target_type",
            "user_id",
            "team_id",
            name="uql_quota_target_period",
        ),
    )

class SalesQuotaAuditLog(Base):
    __tablename__ = "sales_quota_audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    quota_id = Column(Integer, index=True, nullable=False)
    action = Column(String(50), default="UPDATE")
    old_target_amount = Column(Float, nullable=True)
    new_target_amount = Column(Float, nullable=True)
    reason = Column(Text, nullable=False)
    changed_by = Column(Integer, nullable=False)
    changed_at = Column(DateTime, default=datetime.utcnow)