from sqlalchemy import Column, Integer, String, Boolean, DateTime, UniqueConstraint
from datetime import datetime
from app.models.user import Base

class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    notification_type = Column(String(50), nullable=False)
    in_app_enabled = Column(Boolean, default=True)
    email_enabled = Column(Boolean, default=True)
    is_mandatory = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "notification_type", name="uql_user_notif_type"),)
