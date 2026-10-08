from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime
from app.models.user import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    product_type = Column(String(50), nullable=False)  # ONE_TIME, SUBSCRIPTION
    unit = Column(String(50), nullable=False)
    list_price = Column(Float, nullable=False)
    floor_price = Column(Float, nullable=False)
    cost_price = Column(Float, nullable=True)
    status = Column(String(50), default="ACTIVE")  # ACTIVE, DISCONTINUED
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
