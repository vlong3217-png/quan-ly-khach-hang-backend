from fastapi import APIRouter, Depends, HTTPException, Query
# dont import unused
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db, SessionLocal
from app.core.dependencies import get_current_user
from app.schemas.email_marketing import (
    EmailTemplateCreate,
    EmailTemplateUpdate,
    EmailTemplateResponse,
    EmailTemplateListResponse,
    EmailSendRequest,
    EmailLogResponse,
    EmailLogListResponse,
)
from app.services import email_marketing_service as service

router = APIRouter(prefix="/email-marketing", tags=["Email Marketing"])


@router.post("/templates", response_model=EmailTemplateResponse, status_code=201)
def create_template(
    payload: EmailTemplateCreate,
    current_user=Depends(get_current_user),
):
    user_dict = current_user if isinstance(current_user, dict) else {"id": getattr(current_user, "id", 1)}
    return service.create_template(payload.model_dump(), user_dict)


@router.get("/templates", response_model=EmailTemplateListResponse)
def list_templates(
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    current_user=Depends(get_current_user),
):
    items = service.list_templates(search=search)
    if category:
        items = [t for t in items if t.get("category") == category]
    return {"total": len(items), "templates": items}


@router.get("/templates/{template_id}", response_model=EmailTemplateResponse)
def get_template(
    template_id: int,
    current_user=Depends(get_current_user),
):
    req_template = service.get_template(template_id)
    if not req_template:
        raise HTTPException(status_code=404, detail="Template not found")
    return req_template


@router.put("/templates/{template_id}", response_model=EmailTemplateResponse)
def update_template(
    template_id: int,
    payload: EmailTemplateUpdate,
    current_user=Depends(get_current_user),
):
    request_data = {k: v for k, v in payload.model_dump().items() if v is not None}
    request_template = service.update_template(template_id, request_data)
    if not request_template:
        raise HTTPException(status_code=404, detail="Template not found")
    return request_template


@router.delete("/templates/{template_id}")
def delete_template(
    template_id: int,
    current_user=Depends(get_current_user),
):
    ok = service.delete_template(template_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"message": "Template deleted successfully"}


@router.post("/send", response_model=EmailLogResponse, status_code=202)
def send_email(
    payload: EmailSendRequest,
    current_user=Depends(get_current_user),
):
    user_dict = current_user if isinstance(current_user, dict) else {"id": getattr(current_user, "id", 1)}
    return service.send_marketing_email(payload.model_dump(), user_dict)


@router.post("/logs/{log_id}/retry", response_model=EmailLogResponse)
def retry_email(
    log_id: int,
    current_user=Depends(get_current_user),
):
    user_dict = current_user if isinstance(current_user, dict) else {"id": getattr(current_user, "id", 1)}
    log = service.retry_failed_email(log_id, user_dict)
    if not log:
        raise HTTPException(status_code=404, detail="Email log not found")
    return log


@router.get("/logs", response_model=EmailLogListResponse)
def list_logs(
    customer_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    current_user=Depends(get_current_user),
):
    items = service.list_email_logs(customer_id=customer_id, status=status, skip=skip, limit=limit)
    return {"total": len(items), "logs": items}
