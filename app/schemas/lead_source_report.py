from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class LeadSourceMetricItem(BaseModel):
    source_name: str
    total_leads: int
    accepted_leads: int
    acceptance_rate: float        # Tỷ lệ lead được nhận (%)
    converted_opportunities: int
    conversion_rate: float        # Tỷ lệ chuyển đổi thành cơ hội (%)
    closed_won_value: float       # Doanh thu thực tế mang lại

class CampaignEffectivenessItem(BaseModel):
    campaign_id: int
    campaign_name: str
    channel: str
    total_leads: int
    accepted_leads: int
    acceptance_rate: float
    converted_opportunities: int
    conversion_rate: float
    closed_won_value: float

class LeadEffectivenessReportResponse(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    total_leads: int
    overall_acceptance_rate: float
    overall_conversion_rate: float
    total_revenue_generated: float
    source_metrics: List[LeadSourceMetricItem]
    campaign_metrics: List[CampaignEffectivenessItem]