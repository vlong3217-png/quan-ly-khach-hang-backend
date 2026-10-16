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
    current_user=Depends(get_current_user),
):
    return service.get_team_activity_audit(
        start_date=start_date,
        end_date=end_date,
        activity_type=activity_type,
        user_id=user_id,
    )