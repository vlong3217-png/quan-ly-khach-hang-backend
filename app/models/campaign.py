from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.sql import func
from app.models.user import Base


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    code = Column(String(100), nullable=False, unique=True, index=True)
    budget = Column(Float, nullable=False, default=0.0)
    actual_cost = Column(Float, default=0.0)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=True)
    channel = Column(String(100), nullable=False)  # EVENT, WORKSHOP, FB_ADS, GOOGLE_ADS, EMAIL, WEBSITE...
    target_leads = Column(Integer, default=0)
    expected_revenue = Column(Float, default=0.0)
    status = Column(String(50), default="ACTIVE")   # PLANNING, ACTIVE, COMPLETED, PAUSED, CANCELLED
    description = Column(Text, nullable=True)
    owner_id = Column(Integer, nullable=False, default=1)
    team_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())
