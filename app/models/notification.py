"""Notification model for SQLAlchemy (S7-08)."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime
from sqlalchemy.sql import func
from app.models.user import Base


class NotificationModel(Base):
    __tablename__ = "notifications"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    recipient_id = Column(Integer, index=True, nullable=False)
    sender_id = Column(Integer, nullable=True)
    sender_name = Column(String(255), nullable=True)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String(64), nullable=False)  # LEAD_ASSIGNED, QUOTE_WAITING_APPROVAL, etc.
    entity_type = Column(String(64), nullable=True)  # LEAD, QUOTE, TASK, OPPORTUNITY, CONTRACT
    entity_id = Column(Integer, nullable=True)
    link = Column(String(500), nullable=True)
    is_read = Column(Boolean, default=False, index=True)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
