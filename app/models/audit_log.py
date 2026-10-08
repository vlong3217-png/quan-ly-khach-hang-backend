from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from app.models.user import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    user_name = Column(String(255), nullable=False)
    entity_type = Column(String(50), nullable=False, index=True)  # ROLE, DISCOUNT, TARGET, DATA_OWNERSHIP
    entity_id = Column(String(100), nullable=True)
    action = Column(String(100), nullable=False)
    field_name = Column(String(100), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    timestamp = Column(DateTime, server_default=func.now(), index=True)
    ip_address = Column(String(50), nullable=True)
