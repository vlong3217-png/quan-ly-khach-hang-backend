"""
Lead Router - Task S4-07: Lead Response
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import ALGORITHM, SECRET_KEY
from app.models.lead import Lead
from app.schemas.lead import (
    LeadCreate,
    LeadRejectSchema,
    LeadResponse,
    LeadUpdate,
)
from app.services import lead_service

router = APIRouter(prefix="/leads", tags=["leads"])
security_optional = HTTPBearer(auto_error=False)


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_optional),
) -> Optional[dict]:
    """Lấy thông tin người dùng hiện tại nếu có Authorization header."""
    if not credentials:
        return None
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


@router.post("", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
def create_lead_endpoint(
    payload: LeadCreate,
    db: Session = Depends(get_db),
):
    """Tạo một lead mới."""
    return lead_service.create_lead(lead_data=payload, db=db)


@router.get("", response_model=List[LeadResponse])
def get_leads_endpoint(
    status: Optional[str] = Query(None, description="Lọc theo trạng thái"),
    is_overdue_sla: Optional[bool] = Query(None, description="Lọc theo quá hạn SLA"),
    assigned_to: Optional[int] = Query(None, description="Lọc theo ID người phụ trách"),
    db: Session = Depends(get_db),
):
    """Danh sách lead."""
    return lead_service.list_leads(
        status_filter=status,
        is_overdue_sla=is_overdue_sla,
        assigned_to=assigned_to,
        db=db,
    )


@router.get("/{id}", response_model=LeadResponse)
def get_lead_endpoint(
    id: int,
    db: Session = Depends(get_db),
):
    """Lấy thông tin chi tiết lead."""
    lead = lead_service.get_lead_by_id(lead_id=id, db=db)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead với ID {id} không tồn tại",
        )
    return lead


@router.put("/{id}", response_model=LeadResponse)
def update_lead_endpoint(
    id: int,
    payload: LeadUpdate,
    db: Session = Depends(get_db),
):
    """Cập nhật thông tin lead."""
    return lead_service.update_lead(lead_id=id, lead_data=payload, db=db)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lead_endpoint(
    id: int,
    db: Session = Depends(get_db),
):
    """Xóa lead."""
    lead_service.delete_lead(lead_id=id, db=db)
    return None


@router.post("/{id}/accept", response_model=LeadResponse)
def accept_lead_endpoint(
    id: int,
    current_user: Optional[dict] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    Task S4-07: Tiếp nhận lead
    - Chuyển trạng thái sang IN_PROGRESS.
    - Gán người phụ trách nếu chưa có.
    """
    user_id = current_user.get("id") if current_user else None
    return lead_service.accept_lead(lead_id=id, user_id=user_id, db=db)


@router.post("/{id}/reject", response_model=LeadResponse)
def reject_lead_endpoint(
    id: int,
    payload: LeadRejectSchema,
    current_user: Optional[dict] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    Task S4-07: Từ chối tiếp nhận lead
    - Bắt buộc nhập lý do (reason).
    - Chuyển trạng thái sang UNASSIGNED.
    - Gán assigned_to = None.
    - Lưu lý do từ chối (rejection_reason).
    """
    user_id = current_user.get("id") if current_user else None
    return lead_service.reject_lead(
        lead_id=id,
        reason=payload.reason,
        user_id=user_id,
        db=db,
    )


@router.post("/sla/check", response_model=List[LeadResponse])
def check_sla_endpoint(
    sla_minutes: Optional[int] = Query(None, description="Thời gian SLA tối đa tính theo phút"),
    db: Session = Depends(get_db),
):
    """Kiểm tra và cập nhật các lead vi phạm SLA phản hồi."""
    return lead_service.check_sla_violations(sla_minutes=sla_minutes, db=db)
