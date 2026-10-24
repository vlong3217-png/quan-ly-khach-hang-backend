from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class WeeklyActivityCount(BaseModel):
    week_label: str  # e.g. "Tuần 41", "Tuần 42"
    call_count: int
    meeting_count: int
    quote_count: int
    total: int

class TeamMemberActivityMetric(BaseModel):
    user_id: int
    user_name: str
    team_id: str
    call_count: int
    meeting_count: int
    quote_count: int
    total_activities: int
    weekly_breakdown: List[WeeklyActivityCount]
    total_leads_assigned: int
    leads_responded_in_sla: int
    sla_response_rate: float # % phản hồi trong SLA (ví dụ: < 15 phút hoặc trong SLA)

class TeamActivitySLAReportResponse(BaseModel):
    team_id: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    total_calls: int
    total_meetings: int
    total_quotes_sent: int
    overall_sla_rate: float
    members: List[TeamMemberActivityMetric]
    page: Optional[int] = 1
    limit: Optional[int] = 20
    total_pages: Optional[int] = 1
    total_members: Optional[int] = None