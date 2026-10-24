from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class ActivityAuditItem(BaseModel):
    id: int
    title: str
    type: str # CALL, MEETING, EMAIL, TASK
    description: Optional[str] = None
    customer_id: Optional[int] = None
    owner_id: int
    owner_name: str
    status: Optional[str] = "COMPLETED"
    created_at: str

class MemberActivitySummaryItem(BaseModel):
    user_id: int
    user_name: str
    call_count: int
    meeting_count: int
    email_count: int
    task_count: int
    total_activities: int

class TeamActivityAuditResponse(BaseModel):
    total_activities: int
    member_summaries: List[MemberActivitySummaryItem]
    activities: List[ActivityAuditItem]
    page: Optional[int] = 1
    limit: Optional[int] = 20
    total_pages: Optional[int] = 1
    total_records: Optional[int] = None