from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func
from app.models.user import Base


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    title = Column(String(255), nullable=True)
    company = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    source = Column(String(100), nullable=True)
    status = Column(String(50), default="UNASSIGNED", nullable=False)
    assigned_to = Column(Integer, nullable=True)
    
    # Task S4-07 requirements
    rejection_reason = Column(String(500), nullable=True)
    is_overdue_sla = Column(Boolean, default=False, nullable=False)

    sla_deadline = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), server_default=func.now())
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "title": self.title,
            "company": self.company,
            "email": self.email,
            "phone": self.phone,
            "source": self.source,
            "status": self.status,
            "assigned_to": self.assigned_to,
            "rejection_reason": self.rejection_reason,
            "is_overdue_sla": self.is_overdue_sla,
            "sla_deadline": self.sla_deadline,
            "notes": self.notes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
