from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class TicketPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TicketStatus(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class SupportTicketBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    priority: TicketPriority = TicketPriority.MEDIUM
    status: TicketStatus = TicketStatus.OPEN
    assigned_to: Optional[str] = None


class SupportTicketCreate(SupportTicketBase):
    customer_id: int


class SupportTicketUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[TicketPriority] = None
    status: Optional[TicketStatus] = None
    assigned_to: Optional[str] = None
    resolution_note: Optional[str] = None


class SupportTicketResponse(SupportTicketBase):
    id: int
    customer_id: int
    customer_name: Optional[str] = None
    resolution_note: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class ChurnRiskAlert(BaseModel):
    customer_id: int
    customer_name: str
    is_at_risk: bool
    risk_level: str  # HIGH, MEDIUM, LOW
    reasons: List[str]
    unresolved_tickets_count: int
    critical_tickets_count: int
