from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List

from app.core.dependencies import get_current_user
from app.schemas.sales_quota import (
    SalesQuotaCreate,
    SalesQuotaUpdate,
    SalesQuotaResponse,
    SalesQuotaListResponse,
    SalesQuotaAuditLogResponse,
    TeamQuotaValidationResponse,
)
from app.services import sales_quota_service as service

router = APIRouter(prefix="/sales-quotas", tags=["Sales Quotas"])

@router.post("", response_model=SalesQuotaResponse, status_code=201)
def create_quota(payload: SalesQuotaCreate, current_user=Depends(get_current_user)):
    user_dict = current_user if isinstance(current_user, dict) else {"id": getattr(current_user, "id", 1), "role": getattr(current_user, "role", "ADMIN")}
    return service.create_sales_quota(payload.model_dump(), user_dict)

@router.get("", response_model=SalesQuotaListResponse)
def list_quotas(
    period_name: Optional[str] = Query(None),
    quota_type: Optional[str] = Query(None),
    team_id: Optional[str] = Query(None),
    page: Optional[int] = Query(None, ge=1, description="Trang hiện tại"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Số lượng mỗi trang"),
    current_user=Depends(get_current_user),
):
    import math
    user_dict = current_user if isinstance(current_user, dict) else {"id": getattr(current_user, "id", 1), "role": getattr(current_user, "role", "SALES")}
    items = service.list_sales_quotas(user_dict, period_name=period_name, quota_type=quota_type, team_id=team_id)
    total = len(items)
    effective_limit = limit if limit is not None else 20
    effective_page = page if page is not None else 1
    total_pages = max(1, math.ceil(total / effective_limit)) if total > 0 else 1

    paged_items = items[(effective_page - 1) * effective_limit : effective_page * effective_limit]
    return {
        "total": total,
        "quotas": paged_items,
        "page": effective_page,
        "limit": effective_limit,
        "total_pages": total_pages,
    }

@router.put("/{quota_id}", response_model=SalesQuotaResponse)
def update_quota(
    quota_id: int,
    payload: SalesQuotaUpdate,
    current_user=Depends(get_current_user),
):
    user_dict = current_user if isinstance(current_user, dict) else {"id": getattr(current_user, "id", 1), "role": getattr(current_user, "role", "ADMIN")}
    return service.update_sales_quota(quota_id, payload.model_dump(), user_dict)

@router.get("/validate-team", response_model=TeamQuotaValidationResponse)
def validate_team_quota(
    team_id: str = Query(...),
    period_name: str = Query(...),
    current_user=Depends(get_current_user),
):
    return service.validate_team_quota(team_id, period_name)

@router.get("/{quota_id}/audit-logs", response_model=List[SalesQuotaAuditLogResponse])
def get_quota_audit_logs(
    quota_id: int,
    current_user=Depends(get_current_user),
):
    return service.get_quota_audit_logs(quota_id)