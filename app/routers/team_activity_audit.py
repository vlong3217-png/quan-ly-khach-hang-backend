from fastapi import APIRouter, Depends, Query
from typing import Optional

from app.core.dependencies import get_current_user
from app.schemas.team_activity_audit import TeamActivityAuditResponse
from app.services import team_activity_audit_service as service

router = APIRouter(prefix="/team-activity-audit", tags=["Team Activity Audit & Filter"])

@router.get("", response_model=TeamActivityAuditResponse)
def get_activity_audit(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    activity_type: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    page: Optional[int] = Query(None, ge=1, description="Trang hiện tại"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Số lượng mỗi trang"),
    current_user=Depends(get_current_user),
):
    import math
    data = service.get_team_activity_audit(
        start_date=start_date,
        end_date=end_date,
        activity_type=activity_type,
        user_id=user_id,
    )
    activities = data.get("activities", [])
    total_records = len(activities)
    effective_limit = limit if limit is not None else 20
    effective_page = page if page is not None else 1
    total_pages = max(1, math.ceil(total_records / effective_limit)) if total_records > 0 else 1

    paged_activities = activities[(effective_page - 1) * effective_limit : effective_page * effective_limit]
    data["activities"] = paged_activities
    data["page"] = effective_page
    data["limit"] = effective_limit
    data["total_pages"] = total_pages
    data["total_records"] = total_records
    return data