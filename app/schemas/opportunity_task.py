"""Opportunity Task Schemas."""
from typing import Optional, List
from pydantic import BaseModel, Field


class OpportunityTaskCreate(BaseModel):
    id: Optional[str] = None
    opportunity_id: Optional[str] = None
    opportunity_title: Optional[str] = None
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    title: str = Field(..., min_length=1)
    description: Optional[str] = ""
    assigned_to_id: Optional[int] = None
    assigned_to_name: Optional[str] = "Người dùng"
    due_date: str
    due_time: Optional[str] = "17:00"
    status: Optional[str] = "TODO"
    priority: Optional[str] = "MEDIUM"
    reminder_type: Optional[str] = "NONE"
    reminder_at: Optional[str] = None
    is_completed: Optional[bool] = False


class OpportunityTaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    assigned_to_id: Optional[int] = None
    assigned_to_name: Optional[str] = None
    due_date: Optional[str] = None
    due_time: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    reminder_type: Optional[str] = None
    reminder_at: Optional[str] = None
    is_completed: Optional[bool] = None
    completed_at: Optional[str] = None
    postponed_reason: Optional[str] = None
    postponed_at: Optional[str] = None


class OpportunityTaskResponse(BaseModel):
    id: str
    opportunity_id: Optional[str] = None
    opportunity_title: Optional[str] = None
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    title: str
    description: Optional[str] = ""
    assigned_to_id: Optional[int] = None
    assigned_to_name: str
    due_date: str
    due_time: Optional[str] = "17:00"
    status: str
    priority: str
    reminder_type: str
    reminder_at: Optional[str] = None
    is_completed: bool
    completed_at: Optional[str] = None
    postponed_reason: Optional[str] = None
    postponed_at: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class OpportunityTaskListResponse(BaseModel):
    items: List[OpportunityTaskResponse]
    total: int
    page: int = 1
    limit: int = 10
    total_pages: int = 1
