from fastapi import APIRouter, Depends, Query, Response
from typing import Optional

from app.core.dependencies import get_current_user
from app.schemas.team_activity_sla import TeamActivitySLAReportResponse
from app.services import team_activity_sla_service as service

router = APIRouter(prefix="/team-activity-sla", tags=["Team Activity & SLA Report"])

@router.get("", response_model=TeamActivitySLAReportResponse)
def get_report(
    team_id: str = Query("TEAM_NORTH"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user=Depends(get_current_user),
):
    return service.get_team_activity_and_sla_report(team_id=team_id, start_date=start_date, end_date=end_date)

@router.get("/export-excel")
def export_excel(
    team_id: str = Query("TEAM_NORTH"),
    current_user=Depends(get_current_user),
):
    excel_bytes = service.export_team_activity_sla_excel(team_id=team_id)
    headers = {
        "Content-Disposition": f"attachment; filename=bao_cao_nang_suat_{team_id}.csv",
        "Content-Type": "text/csv; charset=utf-8-sig",
    }
    return Response(content=excel_bytes, headers=headers)