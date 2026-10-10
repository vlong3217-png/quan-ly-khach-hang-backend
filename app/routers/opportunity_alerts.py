"""
S5-07: API cảnh báo cơ hội đình trệ / quá hạn.
Router này phải được include TRƯỚC opportunities_router để '/opportunities/flagged'
không bị khớp với '/opportunities/{opportunity_id}'.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import require_roles, resolve_scope
from app.schemas.opportunity import (
    FlaggedOpportunityListResponse,
    OpportunityScanResponse,
)
from app.services import opportunity_stagnant_service as stagnant_service

router = APIRouter(prefix="/opportunities", tags=["Opportunity Alerts"])

_ALLOWED_ROLES = ["ADMIN", "MANAGER"]
_ROLE_DETAIL = "Chỉ Trưởng nhóm kinh doanh / Quản lý / Quản trị viên mới xem được cảnh báo cơ hội"


@router.get("/flagged", response_model=FlaggedOpportunityListResponse)
def list_flagged_opportunities(
    scope: Optional[str] = Query(None, description="MY, MY_TEAM, TEAM hoặc ALL. Mặc định theo vai trò."),
    reason: Optional[str] = Query(None, description="Lọc theo lý do cờ: STAGNANT hoặc OVERDUE"),
    refresh: bool = Query(False, description="Đánh giá lại cờ trước khi trả về"),
    current_user: dict = Depends(require_roles(_ALLOWED_ROLES, detail=_ROLE_DETAIL)),
):
    reason_value = reason.strip().upper() if reason else None
    if reason_value and reason_value not in (stagnant_service.REASON_STAGNANT, stagnant_service.REASON_OVERDUE):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="reason không hợp lệ. Các giá trị hợp lệ: STAGNANT, OVERDUE",
        )
    effective_scope = resolve_scope(current_user, scope)
    items = stagnant_service.get_flagged_opportunities(
        current_user, effective_scope, reason=reason_value, refresh=refresh
    )
    return {
        "scope": effective_scope.value,
        "total": len(items),
        "opportunities": items,
    }


@router.post("/flagged/scan", response_model=OpportunityScanResponse)
def scan_flagged_opportunities(
    scope: Optional[str] = Query(None, description="Phạm vi quét. Mặc định theo vai trò."),
    as_of: Optional[date] = Query(None, description="Ngày đánh giá (mặc định hôm nay), định dạng YYYY-MM-DD"),
    current_user: dict = Depends(require_roles(_ALLOWED_ROLES, detail=_ROLE_DETAIL)),
):
    """Trigger tác vụ quét hàng ngày: cập nhật cờ đình trệ / quá hạn cho các cơ hội trong phạm vi."""
    effective_scope = resolve_scope(current_user, scope)
    return stagnant_service.scan_opportunities(current_user, effective_scope, today=as_of)
