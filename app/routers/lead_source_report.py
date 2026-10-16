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
    current_user=Depends(get_current_user),
):
    return service.get_lead_source_and_campaign_report(start_date=start_date, end_date=end_date)

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