from fastapi import APIRouter, Depends, Query, Response
from typing import Optional

from app.core.dependencies import get_current_user
from app.schemas.lead_source_report import LeadEffectivenessReportResponse
from app.services import lead_source_report_service as service

router = APIRouter(prefix="/lead-source-effectiveness", tags=["Lead Source Effectiveness Report"])

@router.get("", response_model=LeadEffectivenessReportResponse)
def get_report(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    page: Optional[int] = Query(None, ge=1, description="Trang hiện tại"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Số lượng mỗi trang"),
    current_user=Depends(get_current_user),
):
    import math
    data = service.get_lead_source_and_campaign_report(start_date=start_date, end_date=end_date)
    sources = data.get("source_metrics", [])
    campaigns = data.get("campaign_metrics", [])
    total_sources = len(sources)
    total_campaigns = len(campaigns)
    effective_limit = limit if limit is not None else 20
    effective_page = page if page is not None else 1
    total_pages = max(1, math.ceil(max(total_sources, total_campaigns) / effective_limit)) if max(total_sources, total_campaigns) > 0 else 1

    paged_sources = sources[(effective_page - 1) * effective_limit : effective_page * effective_limit]
    paged_campaigns = campaigns[(effective_page - 1) * effective_limit : effective_page * effective_limit]
    data["source_metrics"] = paged_sources
    data["campaign_metrics"] = paged_campaigns
    data["page"] = effective_page
    data["limit"] = effective_limit
    data["total_pages"] = total_pages
    data["total_sources"] = total_sources
    data["total_campaigns"] = total_campaigns
    return data

@router.get("/export-excel")
def export_excel(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user=Depends(get_current_user),
):
    excel_bytes = service.export_lead_effectiveness_excel(start_date=start_date, end_date=end_date)
    headers = {
        "Content-Disposition": "attachment; filename=bao_cao_nguon_lead_va_chien_dich.csv",
        "Content-Type": "text/csv; charset=utf-8-sig",
    }
    return Response(content=excel_bytes, headers=headers)