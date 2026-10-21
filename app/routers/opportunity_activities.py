from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_optional_current_user

router = APIRouter(tags=["Opportunity Activities"])

opportunity_activities_db: List[Dict[str, Any]] = []


@router.get("/opportunity-activities", summary="Lấy danh sách tất cả hoạt động cơ hội")
def list_all_opportunity_activities(
    current_user: Optional[dict] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    return opportunity_activities_db


@router.get("/opportunities/{opportunity_id}/activities", summary="Lấy danh sách hoạt động của một cơ hội")
def get_opportunity_activities(
    opportunity_id: str,
    current_user: Optional[dict] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    return [a for a in opportunity_activities_db if str(a.get("opportunity_id")) == str(opportunity_id)]


@router.post("/opportunities/{opportunity_id}/activities", status_code=status.HTTP_201_CREATED, summary="Thêm hoạt động cho cơ hội")
def create_opportunity_activity(
    opportunity_id: str,
    payload: Dict[str, Any],
    current_user: Optional[dict] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    now_str = datetime.now(timezone.utc).isoformat()
    new_act = {
        "id": payload.get("id") or f"act-{int(datetime.now().timestamp() * 1000)}",
        "opportunity_id": opportunity_id,
        "opportunity_title": payload.get("opportunity_title", ""),
        "customer_id": payload.get("customer_id"),
        "customer_name": payload.get("customer_name"),
        "contact_id": payload.get("contact_id"),
        "contact_name": payload.get("contact_name"),
        "occurred_at": payload.get("occurred_at") or now_str,
        "type": payload.get("type", "NOTE"),
        "title": payload.get("title", "").strip() or "Hoạt động mới",
        "content": payload.get("content", "").strip() or "",
        "performed_by_id": payload.get("performed_by_id") or (current_user.get("id") if current_user else None),
        "performed_by_name": payload.get("performed_by_name") or (current_user.get("full_name") if current_user else "Người dùng"),
        "outcome": payload.get("outcome"),
        "duration_minutes": payload.get("duration_minutes"),
        "next_action": payload.get("next_action"),
        "next_action_due": payload.get("next_action_due"),
        "created_at": payload.get("created_at") or now_str,
        "updated_at": now_str,
    }
    opportunity_activities_db.insert(0, new_act)
    return new_act


@router.delete("/opportunity-activities/{id}", summary="Xóa một hoạt động cơ hội")
def delete_opportunity_activity(
    id: str,
    current_user: Optional[dict] = Depends(get_optional_current_user),
):
    global opportunity_activities_db
    opportunity_activities_db = [a for a in opportunity_activities_db if str(a.get("id")) != str(id)]
    return {"success": True, "message": "Xóa hoạt động thành công"}


@router.delete("/attachments/{attachment_id}", summary="Xóa tệp đính kèm cơ hội (alias)")
def delete_attachment_alias(
    attachment_id: str,
    current_user: Optional[dict] = Depends(get_optional_current_user),
):
    return {"success": True, "message": "Xóa tệp đính kèm thành công"}
