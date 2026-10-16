from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class FunnelStageMetric(BaseModel):
    stage: str
    stage_name: str
    count: int
    value: float
    conversion_rate_to_next: float # Ty le chuyen sang stage ke tiep (%)
    drop_count: int                # So co hoi roi rung tai stage nay
    drop_rate: float               # Ty le roi rung (%)
    avg_duration_days: float       # Thoi gian trung binh o stage nay (ngay)

class FunnelBottleneckInsights(BaseModel):
    highest_drop_stage: str
    highest_drop_stage_name: str
    highest_drop_count: int
    highest_drop_rate: float
    longest_stagnant_stage: str
    longest_stagnant_stage_name: str
    longest_avg_duration_days: float

class SalesFunnelFilter(BaseModel):
    team_id: Optional[str] = None
    user_id: Optional[int] = None
    product_id: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class SalesFunnelResponse(BaseModel):
    total_opportunities: int
    total_pipeline_value: float
    stages: List[FunnelStageMetric]
    insights: FunnelBottleneckInsights
    filters_applied: SalesFunnelFilter