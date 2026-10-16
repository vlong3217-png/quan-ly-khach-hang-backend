"""
Notification API Router for In-App Notifications (S7-08 EP-09).
- Biểu tượng chuông hiển thị số thông báo chưa đọc (AC 2)
- Danh sách thông báo phân trang & lọc (AC 2)
- Đánh dấu đã đọc / đánh dấu tất cả đã đọc (AC 2)
- Mở đúng màn hình liên quan qua metadata link / entity (AC 3)
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.schemas.notification import (
    NotificationResponse,
    NotificationListResponse,
    NotificationUnreadCountResponse,
    NotificationBatchReadResponse,
    NotificationTestTriggerRequest,
)
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/unread-count", response_model=NotificationUnreadCountResponse)
def get_unread_notification_count(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Lấy số lượng thông báo chưa đọc của người dùng hiện tại (AC 2).
    Dùng để hiển thị badge số lượng đỏ trên biểu tượng chuông thông báo.
    """
    user_id = current_user.get("id")
    count = notification_service.get_user_unread_count(user_id=user_id, db=db)
    return {"unread_count": count}


@router.get("", response_model=NotificationListResponse)
def list_user_notifications(
    page: int = Query(1, ge=1, description="Số trang (bắt đầu từ 1)"),
    page_size: int = Query(20, ge=1, le=100, description="Số lượng thông báo mỗi trang"),
    is_read: Optional[bool] = Query(None, description="Lọc theo trạng thái đã đọc (true) hoặc chưa đọc (false)"),
    type: Optional[str] = Query(None, description="Lọc theo loại sự kiện thông báo"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Lấy danh sách thông báo của người dùng hiện tại có phân trang và bộ lọc (AC 2).
    """
    user_id = current_user.get("id")
    return notification_service.get_user_notifications(
        user_id=user_id,
        is_read=is_read,
        notif_type=type,
        page=page,
        page_size=page_size,
        db=db,
    )


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
def mark_single_notification_read(
    notification_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Đánh dấu 1 thông báo là đã đọc (AC 2).
    """
    user_id = current_user.get("id")
    updated = notification_service.mark_notification_as_read(
        notification_id=notification_id,
        user_id=user_id,
        db=db,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy thông báo hoặc bạn không có quyền truy cập",
        )
    return updated


@router.post("/mark-all-read", response_model=NotificationBatchReadResponse)
def mark_all_notifications_read(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Đánh dấu tất cả thông báo của người dùng hiện tại là đã đọc (AC 2).
    """
    user_id = current_user.get("id")
    updated_count = notification_service.mark_all_notifications_as_read(user_id=user_id, db=db)
    remaining_unread = notification_service.get_user_unread_count(user_id=user_id, db=db)
    return {
        "success": True,
        "updated_count": updated_count,
        "unread_count": remaining_unread,
    }


@router.delete("/{notification_id}")
def delete_single_notification(
    notification_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Xóa một thông báo khỏi hộp thư của người dùng.
    """
    user_id = current_user.get("id")
    success = notification_service.delete_notification(
        notification_id=notification_id,
        user_id=user_id,
        db=db,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy thông báo hoặc bạn không có quyền xóa",
        )
    return {"success": True, "message": "Đã xóa thông báo thành công"}


@router.post("/test-trigger", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
def trigger_test_notification(
    payload: NotificationTestTriggerRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Endpoint hỗ trợ kích hoạt nhanh sự kiện thông báo để kiểm thử hoặc dev/QA (AC 1, AC 4).
    """
    user_id = payload.recipient_id if payload.recipient_id is not None else current_user.get("id")
    data = {
        "recipient_id": user_id,
        "sender_id": current_user.get("id"),
        "sender_name": current_user.get("full_name") or "Tester",
        "title": payload.title or "Thông báo thử nghiệm",
        "message": payload.message or "Nội dung thông báo kiểm tra",
        "type": payload.type or "SYSTEM",
        "entity_type": payload.entity_type,
        "entity_id": payload.entity_id,
        "link": payload.link,
    }
    notification_service.dispatch_notification_async(data, background_tasks=background_tasks, db=db)
    # Trả về thông báo được tạo
    return notification_service.create_notification(data, db=db)
