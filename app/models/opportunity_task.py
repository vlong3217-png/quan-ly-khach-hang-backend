"""Opportunity Task Models for SQLAlchemy and compatibility."""
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.sql import func
from app.models.user import Base


class OpportunityTaskModel(Base):
    __tablename__ = "opportunity_tasks"

    id = Column(String(100), primary_key=True, index=True)
    opportunity_id = Column(String(50), nullable=True, index=True)
    opportunity_title = Column(String(255), nullable=True)
    customer_id = Column(String(50), nullable=True, index=True)
    customer_name = Column(String(255), nullable=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    assigned_to_id = Column(Integer, nullable=True, index=True)
    assigned_to_name = Column(String(255), nullable=False, default="Người dùng")
    due_date = Column(String(50), nullable=False)  # YYYY-MM-DD
    due_time = Column(String(20), nullable=True, default="17:00")
    status = Column(String(50), nullable=False, default="TODO")  # TODO, IN_PROGRESS, COMPLETED, POSTPONED, CANCELLED
    priority = Column(String(50), nullable=False, default="MEDIUM")  # LOW, MEDIUM, HIGH, URGENT
    reminder_type = Column(String(50), nullable=False, default="NONE")  # NONE, ON_DUE, 15_MIN_BEFORE, 1_HOUR_BEFORE, 1_DAY_BEFORE, 3_DAYS_BEFORE
    reminder_at = Column(String(100), nullable=True)
    is_completed = Column(Boolean, nullable=False, default=False)
    completed_at = Column(String(100), nullable=True)
    postponed_reason = Column(Text, nullable=True)
    postponed_at = Column(String(100), nullable=True)
    owner_id = Column(Integer, nullable=False, default=1, index=True)
    team_id = Column(Integer, nullable=True, index=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
