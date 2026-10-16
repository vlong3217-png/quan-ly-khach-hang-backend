from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class SalesRepDashboardData(BaseModel):
    user_id: int
    quota_target: float
    quota_achieved: float
    attainment_rate: float
    open_opportunities_count: int
    open_opportunities_value: float
    today_tasks_count: int
    today_tasks: List[Dict[str, Any]]
    uncontacted_leads_count: int
    uncontacted_leads: List[Dict[str, Any]]

class TeamMemberRankItem(BaseModel):
    user_id: int
    user_name: str
    closed_won_value: float
    attainment_rate: float
    rank: int

class TeamManagerDashboardData(SalesRepDashboardData):
    team_id: str
    member_rankings: List[TeamMemberRankItem]
    stagnant_opportunities_count: int
    stagnant_opportunities: List[Dict[str, Any]]
    overdue_tasks_count: int
    overdue_tasks: List[Dict[str, Any]]

class PipelineStageValueItem(BaseModel):
    stage: str
    count: int
    value: float

class MonthlyClosedWonItem(BaseModel):
    month: str
    closed_won_value: float

class DirectorDashboardData(BaseModel):
    total_forecast_weighted: float
    total_quota_target: float
    overall_attainment_rate: float
    pipeline_by_stage: List[PipelineStageValueItem]
    closed_won_by_month: List[MonthlyClosedWonItem]
    total_closed_won_ytd: float
    load_time_ms: float

class RoleBasedDashboardResponse(BaseModel):
    role: str
    user_id: int
    data: Dict[str, Any]
    load_time_seconds: float