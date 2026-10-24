"""Activity and Task Models for SQLAlchemy and compatibility."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Float
from sqlalchemy.sql import func
from app.models.user import Base


class ActivityModel(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False)  # CALL, MEETING, EMAIL, NOTE
    description = Column(Text, nullable=True)
    result = Column(Text, nullable=True)  # Kết quả hoạt động
    duration_minutes = Column(Integer, nullable=True, default=0)  # Thời lượng phút
    occurred_at = Column(DateTime, nullable=False, default=func.now())  # Thời điểm diễn ra thực tế
    customer_id = Column(Integer, nullable=True, index=True)
    contact_id = Column(Integer, nullable=True, index=True)
    opportunity_id = Column(Integer, nullable=True, index=True)
    lead_id = Column(Integer, nullable=True, index=True)
    owner_id = Column(Integer, nullable=False, index=True)  # Người thực hiện / sở hữu
    team_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class TaskModel(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    due_date = Column(DateTime, nullable=False, index=True)  # Hạn hoàn thành
    priority = Column(String(50), default="MEDIUM")  # LOW, MEDIUM, HIGH, URGENT
    status = Column(String(50), default="PENDING")  # PENDING, IN_PROGRESS, COMPLETED, POSTPONED, CANCELLED
    assignee_id = Column(Integer, nullable=False, index=True)  # Người thực hiện
    creator_id = Column(Integer, nullable=False, index=True)  # Người tạo / giao việc
    updater_id = Column(Integer, nullable=True)  # Người cập nhật gần nhất
    customer_id = Column(Integer, nullable=True, index=True)
    opportunity_id = Column(Integer, nullable=True, index=True)
    contact_id = Column(Integer, nullable=True, index=True)
    postpone_reason = Column(Text, nullable=True)  # Lý do hoãn (bắt buộc khi hoãn)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class NotificationModel(Base):
    __tablename__ = "notifications"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String(50), default="TASK_REMINDER")  # TASK_REMINDER, OVERDUE_TASK, GENERAL
    reference_id = Column(Integer, nullable=True)  # task_id
    dedup_key = Column(String(255), nullable=True, index=True)  # Khóa chống trùng thông báo
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())


class Activity(BaseModel):
    id: int
    title: str
    type: str
    description: Optional[str] = ""
    customer_id: Optional[int] = None
    lead_id: Optional[int] = None
    opportunity_id: Optional[int] = None
    owner_id: int
    team_id: Optional[int] = None

