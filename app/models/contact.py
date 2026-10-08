from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.user import Base


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    position = Column(String(255), nullable=True)
    decision_role = Column(String(50), default="INFLUENCER")
    is_primary = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), server_default=func.now())
    updated_at = Column(DateTime, nullable=True, onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    history = relationship(
        "ContactCompanyHistory",
        back_populates="contact",
        cascade="all, delete-orphan",
        order_by="ContactCompanyHistory.id",
    )


class ContactCompanyHistory(Base):
    __tablename__ = "contact_company_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(String(50), nullable=False)  # CREATE, UPDATE, TRANSFER, MERGE
    from_customer_id = Column(Integer, nullable=True)
    to_customer_id = Column(Integer, nullable=True)
    note = Column(Text, nullable=True)
    performed_by = Column(String(100), nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), server_default=func.now())

    contact = relationship("Contact", back_populates="history")
