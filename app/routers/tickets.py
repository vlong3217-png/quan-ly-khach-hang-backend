from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import get_current_user
from app.schemas.ticket import ChurnRiskAlert, SupportTicketCreate, SupportTicketResponse, SupportTicketUpdate
from app.services import ticket_service

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.get("", response_model=List[SupportTicketResponse])
def get_tickets(
    customer_id: Optional[int] = Query(None, description="Lọc theo khách hàng"),
    status: Optional[str] = Query(None, description="Lọc theo trạng thái"),
    page: Optional[int] = Query(None, ge=1, description="Trang hiện tại (bắt đầu từ 1)"),
    skip: Optional[int] = Query(None, ge=0, description="Vị trí bắt đầu"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Số lượng tối đa mỗi trang"),
    current_user: dict = Depends(get_current_user),
):
    """AC S3-08: Danh sách ticket hỗ trợ khách hàng sau bán có phân trang."""
    items = ticket_service.list_tickets(customer_id=customer_id, status=status)
    if limit is not None:
        effective_skip = (page - 1) * limit if page is not None else (skip or 0)
        return items[effective_skip : effective_skip + limit]
    elif skip is not None:
        return items[skip:]
    return items


@router.get("/churn-risk-alerts", response_model=List[ChurnRiskAlert])
def get_churn_risk_alerts(
    current_user: dict = Depends(get_current_user),
):
    """AC S3-08: Cảnh báo danh sách các khách hàng có rủi ro rời bỏ (churn risk)."""
    return ticket_service.list_churn_risk_alerts()


@router.get("/churn-risk/{customer_id}", response_model=ChurnRiskAlert)
def check_customer_churn_risk(
    customer_id: int,
    current_user: dict = Depends(get_current_user),
):
    """AC S3-08: Đánh giá chi tiết nguy cơ rời bỏ của một khách hàng cụ thể."""
    try:
        return ticket_service.evaluate_churn_risk(customer_id=customer_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{ticket_id}", response_model=SupportTicketResponse)
def get_ticket_detail(
    ticket_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Xem chi tiết ticket hỗ trợ."""
    ticket = ticket_service.get_ticket_by_id(ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket #{ticket_id} không tồn tại",
        )
    return ticket


@router.post("", response_model=SupportTicketResponse, status_code=status.HTTP_201_CREATED)
def create_new_ticket(
    payload: SupportTicketCreate,
    current_user: dict = Depends(get_current_user),
):
    """Tạo ticket hỗ trợ mới cho khách hàng."""
    try:
        return ticket_service.create_ticket(ticket_data=payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{ticket_id}", response_model=SupportTicketResponse)
def update_ticket_status(
    ticket_id: int,
    payload: SupportTicketUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Cập nhật tiến độ xử lý ticket hỗ trợ."""
    updated = ticket_service.update_ticket(ticket_id=ticket_id, update_data=payload)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket #{ticket_id} không tồn tại",
        )
    return updated
