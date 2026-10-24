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
    page: Optional[int] = Query(None, ge=1, description="Trang hiện tại"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Số lượng mỗi trang"),
    current_user=Depends(get_current_user),
):
    import math
    data = service.get_team_activity_and_sla_report(team_id=team_id, start_date=start_date, end_date=end_date)
    members = data.get("members", [])
    total_members = len(members)
    effective_limit = limit if limit is not None else 20
    effective_page = page if page is not None else 1
    total_pages = max(1, math.ceil(total_members / effective_limit)) if total_members > 0 else 1

    paged_members = members[(effective_page - 1) * effective_limit : effective_page * effective_limit]
    data["members"] = paged_members
    data["page"] = effective_page
    data["limit"] = effective_limit
    data["total_pages"] = total_pages
    data["total_members"] = total_members
    return data

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