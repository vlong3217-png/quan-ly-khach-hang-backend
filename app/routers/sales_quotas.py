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
    current_user=Depends(get_current_user),
):
    user_dict = current_user if isinstance(current_user, dict) else {"id": getattr(current_user, "id", 1), "role": getattr(current_user, "role", "SALES")}
    items = service.list_sales_quotas(user_dict, period_name=period_name, quota_type=quota_type, team_id=team_id)
    return {"total": len(items), "quotas": items}

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