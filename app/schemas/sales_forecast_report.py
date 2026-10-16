from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class ForecastProgressItem(BaseModel):
    scope_type: str  # "company", "team", "user"
    scope_id: Optional[str] = None
    scope_name: str
    closed_won_amount: float
    weighted_forecast_amount: float
    quota_target_amount: float
    progress_rate: float # % closed_won / quota_target
    forecast_rate: float # % (closed_won + weighted_forecast) / quota_target

class WinLossLossAnalysisItem(BaseModel):
    category: str
    competitor: Optional[str] = None
    lost_count: int
    lost_value: float
    percentage: float

class ForecastReportResponse(BaseModel):
    period_name: str
    summary: ForecastProgressItem
    breakdown_by_team: List[ForecastProgressItem]
    breakdown_by_rep: List[ForecastProgressItem]
    loss_analysis_by_category: List[WinLossLossAnalysisItem]
    loss_analysis_by_competitor: List[WinLossLossAnalysisItem]