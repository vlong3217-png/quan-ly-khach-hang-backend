from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from app.models.user import Base


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    company = Column(String(255), nullable=True)
    owner_id = Column(Integer, nullable=False)  # User who owns this customer
    team_id = Column(Integer, nullable=True)     # Team this customer belongs to
    created_at = Column(DateTime, server_default=func.now())
